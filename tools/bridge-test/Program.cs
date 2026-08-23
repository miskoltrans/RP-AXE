using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using RPAxe.Bridge;

namespace RPAxe.BridgeTest
{
    /// <summary>
    /// Assertions over the bridge transport. Each one exists because the failure it catches would
    /// otherwise show up as a wrong burn rather than as an error.
    /// </summary>
    public static class Program
    {
        private static int _pass, _fail;

        public static int Main(string[] args)
        {
            JsonWriter();
            JsonReader();
            JsonRoundTrip();
            LocaleInvariance();
            RequestFields();
            HttpFraming();
            Concurrency();

            Console.WriteLine();
            Console.WriteLine(_fail == 0
                ? $"OK  {_pass} checks passed"
                : $"FAILED  {_fail} of {_pass + _fail} checks");
            return _fail == 0 ? 0 : 1;
        }

        // --- checks ----------------------------------------------------------
        private static void JsonWriter()
        {
            Section("json writer");
            Eq("null for NaN", AxeJson.Num(double.NaN), "null");
            Eq("null for +inf", AxeJson.Num(double.PositiveInfinity), "null");
            Eq("null for -inf", AxeJson.Num(double.NegativeInfinity), "null");
            Eq("escapes quotes", AxeJson.Str("a\"b"), "\"a\\\"b\"");
            Eq("escapes newline", AxeJson.Str("a\nb"), "\"a\\nb\"");
            Eq("escapes control chars", AxeJson.Str("\u0001"), "\"\\u0001\"");
            Eq("null string", AxeJson.Str(null), "null");

            var j = new AxeJson().Obj();
            j.Val("ok", true);
            j.Vec("r", new Vector3d(1.5, -2.0, 3.25));
            j.Arr("xs"); j.Item(1.0); j.Item("two"); j.EndArr();
            Eq("nested shape", j.EndObj().ToString(),
               "{\"ok\":true,\"r\":[1.5,-2,3.25],\"xs\":[1,\"two\"]}");
        }

        private static void JsonReader()
        {
            Section("json reader");
            var d = AxeJsonReader.ParseObject("{\"a\":1,\"b\":\"x\",\"c\":true,\"d\":null}");
            Eq("number", AxeJsonReader.Num(d, "a", -1), 1.0);
            Eq("string", AxeJsonReader.Str(d, "b"), "x");
            Eq("bool", AxeJsonReader.Bool(d, "c", false), true);
            Eq("explicit null is present", AxeJsonReader.Has(d, "d"), true);
            Eq("missing key defaults", AxeJsonReader.Num(d, "zz", 42.0), 42.0);

            // Keys are matched case-insensitively, matching the query parser, so a client that
            // sends "UT" is not silently ignored while the response still says ok.
            Eq("keys are case-insensitive", AxeJsonReader.Num(
                AxeJsonReader.ParseObject("{\"UT\":7}"), "ut", -1), 7.0);

            // A quoted number is accepted: quoting a UT to dodge float formatting is careful,
            // not wrong, and a type error there would be pure friction.
            Eq("quoted number", AxeJsonReader.Num(
                AxeJsonReader.ParseObject("{\"ut\":\"1.25e3\"}"), "ut", -1), 1250.0);

            var arr = AxeJsonReader.Arr(AxeJsonReader.ParseObject(
                "{\"nodes\":[{\"ut\":1},{\"ut\":2},{\"ut\":3}]}"), "nodes");
            Eq("array keeps every element", arr.Count, 3);
            Eq("array element is an object",
               AxeJsonReader.Num(AxeJsonReader.AsObj(arr[2]), "ut", -1), 3.0);

            Eq("escapes decoded", AxeJsonReader.Str(
                AxeJsonReader.ParseObject("{\"s\":\"a\\\"b\\n\\u0041\"}"), "s"), "a\"b\nA");
            Eq("empty object", AxeJsonReader.ParseObject("{}").Count, 0);
            Eq("whitespace tolerated",
               AxeJsonReader.Num(AxeJsonReader.ParseObject(" {\n \"a\" : 1 \n} "), "a", -1), 1.0);

            Throws("trailing garbage rejected", () => AxeJsonReader.Parse("{\"a\":1} junk"));
            Throws("unterminated object rejected", () => AxeJsonReader.Parse("{\"a\":1"));
            Throws("unterminated string rejected", () => AxeJsonReader.Parse("{\"a\":\"x}"));
            Throws("bare array is not an object", () => AxeJsonReader.ParseObject("[1,2]"));
            Throws("NumRequired names the field",
                   () => AxeJsonReader.NumRequired(AxeJsonReader.ParseObject("{}"), "ut"));
        }

        private static void JsonRoundTrip()
        {
            Section("round trip");
            // Doubles must survive writer -> reader bit-exact. A node UT is ~5e8 seconds and a
            // dV component matters to the millimetre; "R" formatting is what makes that hold.
            double[] samples =
            {
                0.0, -0.0, 1.0, -1.0, 0.1, 1.0 / 3.0, Math.PI,
                496651291.4382913, 1e-12, -1e-12, 1.7976931348623157e308,
                4.9406564584124654e-324, 6378136.6, -2943.8271828182845,
            };
            int bad = 0;
            foreach (double v in samples)
            {
                var j = new AxeJson().Obj();
                j.Val("v", v);
                double back = AxeJsonReader.Num(AxeJsonReader.ParseObject(j.EndObj().ToString()), "v", double.NaN);
                if (BitConverter.DoubleToInt64Bits(back) != BitConverter.DoubleToInt64Bits(v)
                    && !(v == 0.0 && back == 0.0))
                {
                    Console.WriteLine($"    {v:R} -> {back:R}");
                    bad++;
                }
            }
            Eq($"{samples.Length} doubles round-trip bit-exact", bad, 0);
        }

        private static void LocaleInvariance()
        {
            Section("locale");
            CultureInfo saved = CultureInfo.CurrentCulture;
            try
            {
                // On a comma-decimal machine an un-pinned writer emits 1,5 -- which a JSON reader
                // splits into two array elements, producing a plausible wrong number rather than
                // an error. Both halves have to be pinned, so both halves are tested.
                var de = new CultureInfo("de-DE");
                CultureInfo.CurrentCulture = de;
                Thread.CurrentThread.CurrentCulture = de;

                Eq("writer ignores the locale", AxeJson.Num(1.5), "1.5");
                var j = new AxeJson().Obj();
                j.Val("v", 1234.5);
                Eq("no thousands separator", j.EndObj().ToString(), "{\"v\":1234.5}");
                Eq("reader ignores the locale",
                   AxeJsonReader.Num(AxeJsonReader.ParseObject("{\"v\":1.5}"), "v", -1), 1.5);
            }
            finally
            {
                CultureInfo.CurrentCulture = saved;
                Thread.CurrentThread.CurrentCulture = saved;
            }
        }

        private static void RequestFields()
        {
            Section("request fields");
            var req = new AxeBridgeServer.Request
            {
                Method = "POST",
                Path = "/node",
                Query = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                        { { "ut", "111" }, { "vessel", "from-query" } },
                Body = "{\"ut\":222,\"replace\":false}",
            };
            Eq("POST is a write", req.IsWrite, true);
            // The body wins over the query. Preferring a stale query parameter over a body the
            // client deliberately sent is how a burn ends up at the wrong UT with an ok response.
            Eq("body beats query", req.FieldNum("ut", -1), 222.0);
            Eq("query fills the gap", req.Field("vessel"), "from-query");
            Eq("bool from body", req.FieldBool("replace", true), false);
            Eq("bool default", req.FieldBool("allow_past", false), false);

            var get = new AxeBridgeServer.Request
            {
                Method = "GET",
                Query = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                        { { "replace", "" }, { "horizon", "12.5" } },
            };
            Eq("GET is not a write", get.IsWrite, false);
            Eq("bare flag reads true", get.FieldBool("replace", false), true);
            Eq("numeric query", get.FieldNum("horizon", -1), 12.5);
            Eq("no body parses to null", get.Json == null, true);
        }

        private static void HttpFraming()
        {
            Section("http framing");
            var server = new AxeBridgeServer(0, Echo);
            int port = StartOnFreePort(server, out server);
            try
            {
                var pump = new Thread(() => { while (!_stop) { server.Pump(); Thread.Sleep(2); } })
                           { IsBackground = true };
                pump.Start();

                string body = "{\"ut\":123.5,\"nodes\":[{\"ut\":1},{\"ut\":2}]}";
                string resp = Send(port, "POST", "/node", body);
                var d = AxeJsonReader.ParseObject(BodyOf(resp));
                Eq("POST body arrives intact", AxeJsonReader.Str(d, "body"), body);
                Eq("method arrives", AxeJsonReader.Str(d, "method"), "POST");
                Eq("path arrives", AxeJsonReader.Str(d, "path"), "/node");

                d = AxeJsonReader.ParseObject(BodyOf(Send(port, "GET", "/nodes?vessel=Perun%201", null)));
                Eq("query is url-decoded", AxeJsonReader.Str(d, "vessel"), "Perun 1");
                Eq("GET has no body", AxeJsonReader.Str(d, "body"), "");

                // A trailing slash must not make /node a different route than /node/.
                d = AxeJsonReader.ParseObject(BodyOf(Send(port, "GET", "/nodes/", null)));
                Eq("trailing slash trimmed", AxeJsonReader.Str(d, "path"), "/nodes");

                // A body split across two writes is the normal case for anything over one segment.
                // A single unchecked Read would truncate it into a SHORTER, still-valid node list.
                string big = "{\"pad\":\"" + new string('x', 200000) + "\"}";
                d = AxeJsonReader.ParseObject(BodyOf(SendSplit(port, "POST", "/node", big)));
                Eq("split body is fully read", AxeJsonReader.Str(d, "body").Length, big.Length);

                Eq("chunked is refused, not half-read",
                   StatusOf(SendChunked(port, "/node")), 411);
                Eq("oversized body is refused",
                   StatusOf(SendOversizeHeader(port, "/node")), 413);
                Eq("a throwing handler is a 500, not a dead server",
                   StatusOf(Send(port, "GET", "/boom", null)), 500);
                Eq("server still answers after the throw",
                   StatusOf(Send(port, "GET", "/nodes", null)), 200);
            }
            finally
            {
                _stop = true;
                server.Stop();
            }
        }

        private static void Concurrency()
        {
            Section("concurrency");
            var server = new AxeBridgeServer(0, Echo);
            int port = StartOnFreePort(server, out server);
            try
            {
                _stop = false;
                var pump = new Thread(() => { while (!_stop) { server.Pump(); Thread.Sleep(1); } })
                           { IsBackground = true };
                pump.Start();

                const int threads = 6, each = 15;
                int ok = 0;
                var workers = new List<Thread>();
                for (int t = 0; t < threads; t++)
                {
                    int id = t;
                    var th = new Thread(() =>
                    {
                        for (int i = 0; i < each; i++)
                        {
                            try
                            {
                                string r = Send(port, "POST", "/node",
                                                "{\"ut\":" + (id * 1000 + i) + "}");
                                var d = AxeJsonReader.ParseObject(BodyOf(r));
                                double got = AxeJsonReader.Num(
                                    AxeJsonReader.ParseObject(AxeJsonReader.Str(d, "body")), "ut", -1);
                                // Not just "did it answer" -- did THIS request get ITS OWN answer.
                                // A queue that crossed responses would still pass a status check.
                                if (got == id * 1000 + i) Interlocked.Increment(ref ok);
                            }
                            catch (Exception) { }
                        }
                    });
                    workers.Add(th);
                    th.Start();
                }
                foreach (Thread th in workers) th.Join(30000);
                Eq($"{threads * each} concurrent requests each get their own answer", ok, threads * each);
            }
            finally
            {
                _stop = true;
                server.Stop();
            }
        }

        // --- harness ---------------------------------------------------------
        private static volatile bool _stop;

        private static string Echo(AxeBridgeServer.Request req)
        {
            if (req.Path == "/boom") throw new InvalidOperationException("deliberate");
            var j = new AxeJson().Obj();
            j.Val("ok", true);
            j.Val("method", req.Method);
            j.Val("path", req.Path);
            j.Val("body", req.Body);
            j.Val("vessel", req.Get("vessel"));
            return j.EndObj().ToString();
        }

        private static int StartOnFreePort(AxeBridgeServer unused, out AxeBridgeServer started)
        {
            // Port 0 would let the OS choose, but AxeBridgeServer does not report back what it
            // chose, so scan instead. Ports it cannot bind are skipped rather than failing the run.
            for (int port = 18300; port < 18400; port++)
            {
                var s = new AxeBridgeServer(port, Echo);
                try { s.Start(); started = s; _stop = false; return port; }
                catch (Exception) { }
            }
            throw new InvalidOperationException("no free port in 18300-18399");
        }

        private static string Send(int port, string method, string target, string body)
        {
            using var c = new TcpClient("127.0.0.1", port);
            using NetworkStream s = c.GetStream();
            var sb = new StringBuilder();
            sb.Append(method).Append(' ').Append(target).Append(" HTTP/1.1\r\n");
            sb.Append("Host: 127.0.0.1\r\n");
            if (body != null)
            {
                sb.Append("Content-Type: application/json\r\n");
                sb.Append("Content-Length: ").Append(Encoding.UTF8.GetByteCount(body)).Append("\r\n");
            }
            sb.Append("Connection: close\r\n\r\n");
            if (body != null) sb.Append(body);
            byte[] payload = Encoding.UTF8.GetBytes(sb.ToString());
            s.Write(payload, 0, payload.Length);
            return ReadAll(s);
        }

        private static string SendSplit(int port, string method, string target, string body)
        {
            using var c = new TcpClient("127.0.0.1", port);
            using NetworkStream s = c.GetStream();
            byte[] bodyBytes = Encoding.UTF8.GetBytes(body);
            string head = method + " " + target + " HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                        + "Content-Length: " + bodyBytes.Length + "\r\nConnection: close\r\n\r\n";
            byte[] h = Encoding.ASCII.GetBytes(head);
            s.Write(h, 0, h.Length);
            s.Flush();
            int half = bodyBytes.Length / 2;
            s.Write(bodyBytes, 0, half);
            s.Flush();
            Thread.Sleep(30);                       // force the reader to see a short first Read
            s.Write(bodyBytes, half, bodyBytes.Length - half);
            s.Flush();
            return ReadAll(s);
        }

        private static string SendChunked(int port, string target)
        {
            using var c = new TcpClient("127.0.0.1", port);
            using NetworkStream s = c.GetStream();
            string req = "POST " + target + " HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                       + "Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n"
                       + "4\r\n{\"a\"\r\n0\r\n\r\n";
            byte[] b = Encoding.ASCII.GetBytes(req);
            s.Write(b, 0, b.Length);
            return ReadAll(s);
        }

        private static string SendOversizeHeader(int port, string target)
        {
            using var c = new TcpClient("127.0.0.1", port);
            using NetworkStream s = c.GetStream();
            // Declare far more than the cap without sending it: the refusal must come from the
            // header, before anything is allocated or read.
            string req = "POST " + target + " HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                       + "Content-Length: 99999999\r\nConnection: close\r\n\r\n";
            byte[] b = Encoding.ASCII.GetBytes(req);
            s.Write(b, 0, b.Length);
            return ReadAll(s);
        }

        private static string ReadAll(Stream s)
        {
            var ms = new MemoryStream();
            var buf = new byte[8192];
            try
            {
                int n;
                while ((n = s.Read(buf, 0, buf.Length)) > 0) ms.Write(buf, 0, n);
            }
            catch (IOException)
            {
                // A reset mid-read is itself a result worth reporting: it means the server closed
                // on us with data still queued. Return what arrived so the assertion names the
                // real failure instead of the harness crashing on it.
            }
            return Encoding.UTF8.GetString(ms.ToArray());
        }

        private static string BodyOf(string response)
        {
            int i = response.IndexOf("\r\n\r\n", StringComparison.Ordinal);
            return i < 0 ? "" : response.Substring(i + 4);
        }

        private static int StatusOf(string response)
        {
            string[] parts = response.Split(' ');
            int code;
            return parts.Length > 1 && int.TryParse(parts[1], out code) ? code : -1;
        }

        // --- assertions ------------------------------------------------------
        private static void Section(string name)
        {
            Console.WriteLine();
            Console.WriteLine("-- " + name);
        }

        private static void Eq<T>(string what, T got, T want)
        {
            bool ok = EqualityComparer<T>.Default.Equals(got, want);
            if (ok) { _pass++; Console.WriteLine("  ok    " + what); }
            else { _fail++; Console.WriteLine($"  FAIL  {what}: got {got}, want {want}"); }
        }

        private static void Throws(string what, Action a)
        {
            try
            {
                a();
                _fail++;
                Console.WriteLine("  FAIL  " + what + ": no exception");
            }
            catch (Exception)
            {
                _pass++;
                Console.WriteLine("  ok    " + what);
            }
        }
    }
}
