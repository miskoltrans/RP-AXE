using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace RPAxe.Bridge
{
    /// <summary>
    /// The reading half of <see cref="AxeJson"/>, for the write endpoints.
    ///
    /// Query strings were enough while the bridge only answered questions. A write is not
    /// shaped like a query: placing four maneuver nodes means four repeated groups, and
    /// <c>ParseQuery</c> puts pairs in a Dictionary, so a repeated key silently keeps only the
    /// last one — three nodes vanish and the response looks fine. A body with a real array in
    /// it cannot lose an element that way.
    ///
    /// Hand-rolled for the same reason the writer is: KSP ships no dependable JSON library, and
    /// a plugin that fails to load on someone else's install is worse than 150 lines of parser.
    ///
    /// Shapes returned: object -> Dictionary&lt;string, object&gt;, array -> List&lt;object&gt;,
    /// number -> double, string -> string, true/false -> bool, null -> null. Numbers parse with
    /// the invariant culture, which is the mirror of the writer's rule: a comma-decimal machine
    /// must not read <c>1.5</c> as <c>15</c>.
    /// </summary>
    public static class AxeJsonReader
    {
        public sealed class JsonError : Exception
        {
            public JsonError(string msg) : base(msg) { }
        }

        public static object Parse(string s)
        {
            if (s == null) throw new JsonError("empty body");
            int i = 0;
            object v = ParseValue(s, ref i);
            SkipWs(s, ref i);
            if (i < s.Length)
                throw new JsonError("trailing text after the JSON value at offset " + i);
            return v;
        }

        /// <summary>Parse and require an object at the top level, which every write endpoint wants.</summary>
        public static Dictionary<string, object> ParseObject(string s)
        {
            object v = Parse(s);
            var d = v as Dictionary<string, object>;
            if (d == null)
                throw new JsonError("expected a JSON object at the top level, got "
                                    + (v == null ? "null" : v.GetType().Name));
            return d;
        }

        // --- typed accessors -------------------------------------------------
        // Written as statics over Dictionary rather than a wrapper type so callers can keep
        // passing the plain dictionaries around, and so a missing key reads as a default
        // rather than as a NullReferenceException three frames away from the cause.

        public static object Get(Dictionary<string, object> d, string key)
        {
            object v;
            return d != null && d.TryGetValue(key, out v) ? v : null;
        }

        public static bool Has(Dictionary<string, object> d, string key)
        {
            return d != null && d.ContainsKey(key);
        }

        /// <summary>
        /// A number, accepting a JSON string that contains one. A client that quotes a UT to
        /// dodge float rounding is being careful, not wrong, and should not get a type error.
        /// </summary>
        public static double Num(Dictionary<string, object> d, string key, double dflt)
        {
            object v = Get(d, key);
            if (v is double) return (double)v;
            if (v is string)
            {
                double p;
                if (double.TryParse((string)v, NumberStyles.Float, CultureInfo.InvariantCulture, out p))
                    return p;
            }
            if (v is bool) return (bool)v ? 1.0 : 0.0;
            return dflt;
        }

        public static double NumRequired(Dictionary<string, object> d, string key)
        {
            double v = Num(d, key, double.NaN);
            if (double.IsNaN(v))
                throw new JsonError("\"" + key + "\" is required and must be a number");
            return v;
        }

        public static string Str(Dictionary<string, object> d, string key, string dflt = null)
        {
            object v = Get(d, key);
            if (v == null) return dflt;
            if (v is string) return (string)v;
            if (v is double) return AxeJson.Num((double)v);
            if (v is bool) return (bool)v ? "true" : "false";
            return dflt;
        }

        public static bool Bool(Dictionary<string, object> d, string key, bool dflt)
        {
            object v = Get(d, key);
            if (v is bool) return (bool)v;
            if (v is double) return (double)v != 0.0;
            if (v is string)
            {
                string s = ((string)v).Trim();
                if (s.Equals("true", StringComparison.OrdinalIgnoreCase) || s == "1") return true;
                if (s.Equals("false", StringComparison.OrdinalIgnoreCase) || s == "0") return false;
            }
            return dflt;
        }

        public static List<object> Arr(Dictionary<string, object> d, string key)
        {
            return Get(d, key) as List<object>;
        }

        public static Dictionary<string, object> AsObj(object v)
        {
            return v as Dictionary<string, object>;
        }

        // --- the parser ------------------------------------------------------
        private static void SkipWs(string s, ref int i)
        {
            while (i < s.Length)
            {
                char c = s[i];
                if (c == ' ' || c == '\t' || c == '\n' || c == '\r') i++;
                else break;
            }
        }

        private static object ParseValue(string s, ref int i)
        {
            SkipWs(s, ref i);
            if (i >= s.Length) throw new JsonError("unexpected end of input");
            char c = s[i];
            switch (c)
            {
                case '{': return ParseObj(s, ref i);
                case '[': return ParseArr(s, ref i);
                case '"': return ParseStr(s, ref i);
                case 't': Expect(s, ref i, "true"); return true;
                case 'f': Expect(s, ref i, "false"); return false;
                case 'n': Expect(s, ref i, "null"); return null;
                default: return ParseNum(s, ref i);
            }
        }

        private static void Expect(string s, ref int i, string word)
        {
            if (i + word.Length > s.Length || string.CompareOrdinal(s, i, word, 0, word.Length) != 0)
                throw new JsonError("expected " + word + " at offset " + i);
            i += word.Length;
        }

        private static Dictionary<string, object> ParseObj(string s, ref int i)
        {
            var d = new Dictionary<string, object>(StringComparer.OrdinalIgnoreCase);
            i++;                                        // '{'
            SkipWs(s, ref i);
            if (i < s.Length && s[i] == '}') { i++; return d; }
            while (true)
            {
                SkipWs(s, ref i);
                if (i >= s.Length || s[i] != '"')
                    throw new JsonError("expected a quoted key at offset " + i);
                string k = ParseStr(s, ref i);
                SkipWs(s, ref i);
                if (i >= s.Length || s[i] != ':')
                    throw new JsonError("expected ':' after key \"" + k + "\"");
                i++;
                d[k] = ParseValue(s, ref i);
                SkipWs(s, ref i);
                if (i >= s.Length) throw new JsonError("unterminated object");
                if (s[i] == ',') { i++; continue; }
                if (s[i] == '}') { i++; return d; }
                throw new JsonError("expected ',' or '}' at offset " + i);
            }
        }

        private static List<object> ParseArr(string s, ref int i)
        {
            var list = new List<object>();
            i++;                                        // '['
            SkipWs(s, ref i);
            if (i < s.Length && s[i] == ']') { i++; return list; }
            while (true)
            {
                list.Add(ParseValue(s, ref i));
                SkipWs(s, ref i);
                if (i >= s.Length) throw new JsonError("unterminated array");
                if (s[i] == ',') { i++; continue; }
                if (s[i] == ']') { i++; return list; }
                throw new JsonError("expected ',' or ']' at offset " + i);
            }
        }

        private static string ParseStr(string s, ref int i)
        {
            var sb = new StringBuilder();
            i++;                                        // opening quote
            while (i < s.Length)
            {
                char c = s[i++];
                if (c == '"') return sb.ToString();
                if (c != '\\') { sb.Append(c); continue; }
                if (i >= s.Length) break;
                char e = s[i++];
                switch (e)
                {
                    case '"': sb.Append('"'); break;
                    case '\\': sb.Append('\\'); break;
                    case '/': sb.Append('/'); break;
                    case 'b': sb.Append('\b'); break;
                    case 'f': sb.Append('\f'); break;
                    case 'n': sb.Append('\n'); break;
                    case 'r': sb.Append('\r'); break;
                    case 't': sb.Append('\t'); break;
                    case 'u':
                        if (i + 4 > s.Length) throw new JsonError("truncated \\u escape");
                        sb.Append((char)int.Parse(s.Substring(i, 4), NumberStyles.HexNumber,
                                                  CultureInfo.InvariantCulture));
                        i += 4;
                        break;
                    default: throw new JsonError("bad escape \\" + e);
                }
            }
            throw new JsonError("unterminated string");
        }

        private static double ParseNum(string s, ref int i)
        {
            int start = i;
            if (i < s.Length && (s[i] == '-' || s[i] == '+')) i++;
            while (i < s.Length)
            {
                char c = s[i];
                if ((c >= '0' && c <= '9') || c == '.' || c == 'e' || c == 'E' || c == '+' || c == '-') i++;
                else break;
            }
            string tok = s.Substring(start, i - start);
            double v;
            if (!double.TryParse(tok, NumberStyles.Float, CultureInfo.InvariantCulture, out v))
                throw new JsonError("not a number: \"" + tok + "\" at offset " + start);
            return v;
        }
    }
}
