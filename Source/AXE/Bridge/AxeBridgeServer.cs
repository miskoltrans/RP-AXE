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
            public string Method = "GET";
            public string Path;
            public Dictionary<string, string> Query;
            /// <summary>Raw request body, UTF-8 decoded. Empty for a GET.</summary>
            public string Body = "";
            public string Response;
            public int Status = 200;
            public readonly ManualResetEvent Done = new ManualResetEvent(false);

            private Dictionary<string, object> _json;
            private bool _jsonParsed;

            /// <summary>
            /// The body as a JSON object, or null if there is no body. Parsed once, on the main
            /// thread, so a malformed body surfaces as a handler exception (HTTP 500 with the
            /// parser's message) rather than killing the socket worker.
            /// </summary>
            public Dictionary<string, object> Json
            {
                get
                {
                    if (!_jsonParsed)
                    {
                        _jsonParsed = true;
                        _json = string.IsNullOrEmpty(Body) ? null : AxeJsonReader.ParseObject(Body);
                    }
                    return _json;
                }
            }

            public bool IsWrite
            {
                get
                {
                    return !string.Equals(Method, "GET", StringComparison.OrdinalIgnoreCase)
                        && !string.Equals(Method, "HEAD", StringComparison.OrdinalIgnoreCase);
                }
            }

            /// <summary>Query parameter only. Write endpoints should prefer <see cref="Field"/>.</summary>
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

            /// <summary>
            /// A scalar from the JSON body, falling back to the query string. Body wins: a client
            /// that sent a body meant it, and silently preferring a stale query parameter is the
            /// kind of thing that only shows up as a burn placed at the wrong UT.
            /// </summary>
            public string Field(string key, string dflt = null)
            {
                Dictionary<string, object> j = Json;
                if (j != null && AxeJsonReader.Has(j, key))
                {
                    string s = AxeJsonReader.Str(j, key);
                    if (s != null) return s;
                }
                return Get(key, dflt);
            }

            public double FieldNum(string key, double dflt)
            {
                Dictionary<string, object> j = Json;
                if (j != null && AxeJsonReader.Has(j, key)) return AxeJsonReader.Num(j, key, dflt);
                return GetNum(key, dflt);
            }

            public bool FieldBool(string key, bool dflt)
            {
                Dictionary<string, object> j = Json;
                if (j != null && AxeJsonReader.Has(j, key)) return AxeJsonReader.Bool(j, key, dflt);
                string v = Get(key);
                if (v == null) return dflt;
                if (v.Length == 0) return true;                 // bare "?replace" reads as true
                if (v.Equals("true", StringComparison.OrdinalIgnoreCase) || v == "1") return true;
                if (v.Equals("false", StringComparison.OrdinalIgnoreCase) || v == "0") return false;
                return dflt;
            }
        }

        /// <summary>Cap on a request body. Generous for a node list, small enough that a stray
        /// client cannot make the game allocate.</summary>
        private const int MaxBody = 1 << 20;

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
                    // "POST /path?a=b HTTP/1.1"
                    string[] parts = line.Split(' ');
                    string method = parts.Length > 0 && parts[0].Length > 0 ? parts[0] : "GET";
                    string target = parts.Length > 1 ? parts[1] : "/";

                    // Only Content-Length is honoured. Chunked bodies are refused rather than
                    // half-read: a truncated body would parse as a SHORTER node list, which is a
                    // silently wrong write. No client of this bridge has any reason to chunk.
                    int contentLength = 0;
                    bool chunked = false;
                    while (true)
                    {
                        string h = ReadLine(stream);
                        if (string.IsNullOrEmpty(h)) break;
                        int colon = h.IndexOf(':');
                        if (colon <= 0) continue;
                        string name = h.Substring(0, colon).Trim();
                        string value = h.Substring(colon + 1).Trim();
                        if (name.Equals("Content-Length", StringComparison.OrdinalIgnoreCase))
                            int.TryParse(value, System.Globalization.NumberStyles.Integer,
                                         System.Globalization.CultureInfo.InvariantCulture, out contentLength);
                        else if (name.Equals("Transfer-Encoding", StringComparison.OrdinalIgnoreCase)
                                 && value.IndexOf("chunked", StringComparison.OrdinalIgnoreCase) >= 0)
                            chunked = true;
                    }

                    var req = new Request();
                    req.Method = method;
                    int q = target.IndexOf('?');
                    req.Path = (q >= 0 ? target.Substring(0, q) : target).TrimEnd('/');
                    if (req.Path.Length == 0) req.Path = "/";
                    req.Query = ParseQuery(q >= 0 ? target.Substring(q + 1) : "");

                    if (chunked)
                    {
                        Write(stream, 411, "{\"ok\":false,\"error\":\"chunked request bodies are not "
                                         + "supported; send Content-Length\"}");
                        return;
                    }
                    if (contentLength > MaxBody)
                    {
                        Write(stream, 413, "{\"ok\":false,\"error\":\"request body over " + MaxBody + " bytes\"}");
                        return;
                    }
                    if (contentLength > 0)
                    {
                        req.Body = ReadBody(stream, contentLength);
                        if (req.Body == null)
                        {
                            Write(stream, 400, "{\"ok\":false,\"error\":\"request body ended before "
                                             + "Content-Length bytes arrived\"}");
                            return;
                        }
                    }

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
                Close(client);
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

        /// <summary>
        /// Close, but drain whatever the client is still sending first.
        ///
        /// This is not politeness. Closing a socket that still has unread bytes in its receive
        /// buffer makes Windows send an RST, and an RST discards data already queued in the other
        /// direction -- including the response just written. The visible symptom is that every
        /// refusal WITH a body attached (a chunked request, an oversized Content-Length, a body on
        /// a path that ignores it) reaches the client as "connection reset by peer" instead of as
        /// the carefully worded reason it was refused. Draining first turns those back into
        /// readable errors.
        /// </summary>
        private static void Close(TcpClient client)
        {
            try
            {
                Socket sock = client.Client;
                if (sock != null && sock.Connected)
                {
                    sock.Shutdown(SocketShutdown.Send);
                    // Bounded on both time and volume: a client that keeps talking must not be
                    // able to hold a socket thread open.
                    sock.ReceiveTimeout = 250;
                    var sink = new byte[4096];
                    int drained = 0;
                    while (drained < MaxBody)
                    {
                        int n = sock.Receive(sink);
                        if (n <= 0) break;
                        drained += n;
                    }
                }
            }
            catch (Exception) { }
            try { client.Close(); } catch (Exception) { }
        }

        /// <summary>
        /// Read exactly <paramref name="length"/> bytes. Stream.Read is free to return fewer than
        /// asked for, and a single unchecked Read is how a body over one TCP segment turns into a
        /// truncated node list that still parses.
        /// </summary>
        private static string ReadBody(Stream s, int length)
        {
            var buf = new byte[length];
            int got = 0;
            while (got < length)
            {
                int n = s.Read(buf, got, length - got);
                if (n <= 0) break;
                got += n;
            }
            if (got < length) return null;              // caller answers 400; see Serve
            return Encoding.UTF8.GetString(buf, 0, got);
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
