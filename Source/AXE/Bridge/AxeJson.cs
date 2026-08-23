using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace RPAxe.Bridge
{
    /// <summary>
    /// A very small JSON writer. Hand-rolled on purpose: KSP does not reliably ship a JSON
    /// library, and taking a dependency for forty lines of string building is how a plugin
    /// starts failing to load on someone else's install.
    ///
    /// Two rules that matter more than they look. Every number is written with the invariant
    /// culture — on a machine with a comma decimal separator, <c>1,5</c> silently becomes two
    /// array elements and the reader on the other end gets a plausible wrong answer. And JSON
    /// has no NaN or Infinity literal, so those become <c>null</c> rather than something a
    /// parser will reject halfway through a 30 kB body.
    /// </summary>
    public sealed class AxeJson
    {
        private readonly StringBuilder _sb = new StringBuilder(4096);
        private readonly Stack<bool> _first = new Stack<bool>();

        public static string Num(double v)
        {
            if (double.IsNaN(v) || double.IsInfinity(v)) return "null";
            return v.ToString("R", CultureInfo.InvariantCulture);
        }

        public static string Str(string s)
        {
            if (s == null) return "null";
            var sb = new StringBuilder(s.Length + 2);
            sb.Append('"');
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < ' ') sb.Append("\\u").Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                        else sb.Append(c);
                        break;
                }
            }
            sb.Append('"');
            return sb.ToString();
        }

        private void Sep()
        {
            if (_first.Count == 0) return;
            if (_first.Peek()) { _first.Pop(); _first.Push(false); }
            else _sb.Append(',');
        }

        public AxeJson Obj() { Sep(); _sb.Append('{'); _first.Push(true); return this; }
        public AxeJson EndObj() { _sb.Append('}'); _first.Pop(); return this; }
        public AxeJson Arr() { Sep(); _sb.Append('['); _first.Push(true); return this; }
        public AxeJson EndArr() { _sb.Append(']'); _first.Pop(); return this; }

        public AxeJson Key(string k) { Sep(); _sb.Append(Str(k)).Append(':'); _first.Push(true); return this; }
        private void EndKey() { if (_first.Count > 0) _first.Pop(); }

        public AxeJson Obj(string k) { Key(k); _sb.Append('{'); EndKey(); _first.Push(true); return this; }
        public AxeJson Arr(string k) { Key(k); _sb.Append('['); EndKey(); _first.Push(true); return this; }

        public AxeJson Val(string k, double v) { Key(k); _sb.Append(Num(v)); EndKey(); return this; }
        public AxeJson Val(string k, string v) { Key(k); _sb.Append(Str(v)); EndKey(); return this; }
        public AxeJson Val(string k, bool v) { Key(k); _sb.Append(v ? "true" : "false"); EndKey(); return this; }
        public AxeJson Val(string k, int v) { Key(k); _sb.Append(v.ToString(CultureInfo.InvariantCulture)); EndKey(); return this; }
        public AxeJson Raw(string k, string rawJson) { Key(k); _sb.Append(rawJson); EndKey(); return this; }

        public AxeJson Item(double v) { Sep(); _sb.Append(Num(v)); return this; }
        public AxeJson Item(string v) { Sep(); _sb.Append(Str(v)); return this; }

        /// <summary>A 3-vector as [x, y, z]. Always right-handed z-up (Planetarium.Zup).</summary>
        public AxeJson Vec(string k, Vector3d v)
        {
            Key(k);
            _sb.Append('[').Append(Num(v.x)).Append(',').Append(Num(v.y)).Append(',').Append(Num(v.z)).Append(']');
            EndKey();
            return this;
        }

        public override string ToString() { return _sb.ToString(); }
    }
}
