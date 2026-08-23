using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

namespace RPAxe.Bridge
{
    /// <summary>
    /// A tiny localhost HTTP server so an outside tool can ask the running game what it thinks.
    ///
    /// Two deliberate choices:
    ///
    /// A raw <see cref="TcpListener"/> rather than <c>HttpListener</c>. HttpListener goes through
    /// http.sys on Windows, which needs a <c>netsh http add urlacl</c> registration or an elevated
    /// process; a plain socket bind needs neither. The HTTP we speak is small enough to write out
    /// by hand.
    ///
    /// Accept and I/O happen off the main thread, but every handler runs ON it. Nothing in the KSP
    /// or Unity API is thread-safe, and touching <c>FlightGlobals</c> from a socket thread is the
    /// kind of bug that shows up as a native crash in Player.log with no managed stack. So a worker
    /// parses the request, hands it to the main thread through a queue, and blocks until Update()
    /// has filled in the response. This mirrors what KSPTOT Connect does for the same reason.
    /// </summary>
    public sealed class AxeBridgeServer
    {
        public sealed class Request
        {
            public string Path;
            public Dictionary<string, string> Query;
            public string Response;
            public int Status = 200;
            public readonly ManualResetEvent Done = new ManualResetEvent(false);

            public string Get(string key, string dflt = null)
            {
                string v;
                return Query != null && Query.TryGetValue(key, out v) ? v : dflt;
            }

            public double GetNum(string key, double dflt)
            {
                string v = Get(key);
                double d;
                return v != null && double.TryParse(v, System.Globalization.NumberStyles.Float,
                    System.Globalization.CultureInfo.InvariantCulture, out d) ? d : dflt;
            }
        }

        private TcpListener _listener;
        private Thread _accept;
        private volatile bool _running;
        private readonly ConcurrentQueue<Request> _pending = new ConcurrentQueue<Request>();
        private readonly Func<Request, string> _handler;
        private readonly int _port;

        public bool Running { get { return _running; } }
        public int Port { get { return _port; } }

        public AxeBridgeServer(int port, Func<Request, string> handler)
        {
            _port = port;
            _handler = handler;
        }

        public void Start()
        {
            if (_running) return;
            // Loopback only, never IPAddress.Any: this hands out save contents and there is no
            // reason for it to be reachable from anywhere but this machine.
            _listener = new TcpListener(IPAddress.Loopback, _port);
            _listener.Start();
            _running = true;
            _accept = new Thread(AcceptLoop) { IsBackground = true, Name = "AxeBridge" };
            _accept.Start();
        }

        public void Stop()
        {
            _running = false;
            try { if (_listener != null) _listener.Stop(); } catch (Exception) { }
            _listener = null;
            // Release anything blocked waiting for a main-thread response we will never produce.
            Request req;
            while (_pending.TryDequeue(out req))
            {
                req.Status = 503;
                req.Response = "{\"ok\":false,\"error\":\"bridge shutting down\"}";
                req.Done.Set();
            }
        }

        private void AcceptLoop()
        {
            while (_running)
            {
                TcpClient client = null;
                try
                {
                    client = _listener.AcceptTcpClient();
                }
                catch (Exception)
                {
                    if (!_running) return;      // Stop() closed the listener; that is not an error
                    Thread.Sleep(50);
                    continue;
                }
                TcpClient c = client;
                ThreadPool.QueueUserWorkItem(delegate { Serve(c); });
            }
        }

        private void Serve(TcpClient client)
        {
            try
            {
                client.ReceiveTimeout = 5000;
                client.SendTimeout = 5000;
                using (NetworkStream stream = client.GetStream())
                {
                    string line = ReadLine(stream);
                    if (string.IsNullOrEmpty(line)) return;
                    // "GET /path?a=b HTTP/1.1" -- headers are read and discarded
                    string[] parts = line.Split(' ');
                    string target = parts.Length > 1 ? parts[1] : "/";
                    while (true)
                    {
                        string h = ReadLine(stream);
                        if (string.IsNullOrEmpty(h)) break;
                    }

                    var req = new Request();
                    int q = target.IndexOf('?');
                    req.Path = (q >= 0 ? target.Substring(0, q) : target).TrimEnd('/');
                    if (req.Path.Length == 0) req.Path = "/";
                    req.Query = ParseQuery(q >= 0 ? target.Substring(q + 1) : "");

                    _pending.Enqueue(req);
                    if (!req.Done.WaitOne(20000))
                    {
                        req.Status = 504;
                        req.Response = "{\"ok\":false,\"error\":\"the game did not answer in 20 s "
                                     + "(is it paused at a modal dialog, or loading?)\"}";
                    }
                    Write(stream, req.Status, req.Response ?? "{\"ok\":false}");
                }
            }
            catch (Exception)
            {
                // A client that hangs up mid-request is normal; never let it reach the game.
            }
            finally
            {
                try { client.Close(); } catch (Exception) { }
            }
        }

        /// <summary>Run pending handlers. MUST be called from the Unity main thread.</summary>
        public void Pump(int maxPerFrame = 8)
        {
            Request req;
            int n = 0;
            while (n++ < maxPerFrame && _pending.TryDequeue(out req))
            {
                try
                {
                    req.Response = _handler(req);
                }
                catch (Exception e)
                {
                    req.Status = 500;
                    req.Response = "{\"ok\":false,\"error\":" + AxeJson.Str(e.GetType().Name + ": " + e.Message) + "}";
                }
                req.Done.Set();
            }
        }

        private static Dictionary<string, string> ParseQuery(string qs)
        {
            var d = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            if (string.IsNullOrEmpty(qs)) return d;
            foreach (string pair in qs.Split('&'))
            {
                if (pair.Length == 0) continue;
                int eq = pair.IndexOf('=');
                string k = eq < 0 ? pair : pair.Substring(0, eq);
                string v = eq < 0 ? "" : pair.Substring(eq + 1);
                d[Uri.UnescapeDataString(k)] = Uri.UnescapeDataString(v.Replace('+', ' '));
            }
            return d;
        }

        private static string ReadLine(Stream s)
        {
            var sb = new StringBuilder(128);
            int b;
            while ((b = s.ReadByte()) >= 0)
            {
                if (b == '\n') break;
                if (b != '\r') sb.Append((char)b);
                if (sb.Length > 8192) break;
            }
            return sb.ToString();
        }

        private static void Write(Stream s, int status, string body)
        {
            byte[] payload = Encoding.UTF8.GetBytes(body);
            string head = "HTTP/1.1 " + status + " " + (status == 200 ? "OK" : "Error") + "\r\n"
                        + "Content-Type: application/json; charset=utf-8\r\n"
                        + "Content-Length: " + payload.Length + "\r\n"
                        + "Access-Control-Allow-Origin: *\r\n"
                        + "Connection: close\r\n\r\n";
            byte[] h = Encoding.ASCII.GetBytes(head);
            s.Write(h, 0, h.Length);
            s.Write(payload, 0, payload.Length);
            s.Flush();
        }
    }
}
