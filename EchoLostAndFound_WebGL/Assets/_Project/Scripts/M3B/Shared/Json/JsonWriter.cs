using System.Globalization;
using System.Text;

namespace EchoLostAndFound.Shared.Json
{
    /// <summary>
    /// Deterministic JSON writer. Member order follows insertion order, non-ASCII
    /// characters are emitted as UTF-8 text (no \u escaping beyond the required
    /// control characters), and numbers are formatted invariantly.
    /// </summary>
    public static class JsonWriter
    {
        public static string Serialize(JsonValue value, bool pretty = false)
        {
            var builder = new StringBuilder(256);
            Write(value, builder, pretty, 0);
            if (pretty) builder.Append('\n');
            return builder.ToString();
        }

        private static void Write(JsonValue value, StringBuilder builder, bool pretty, int depth)
        {
            switch (value)
            {
                case null:
                case JsonNull _:
                    builder.Append("null");
                    return;
                case JsonBool boolean:
                    builder.Append(boolean.Value ? "true" : "false");
                    return;
                case JsonNumber number:
                    WriteNumber(number, builder);
                    return;
                case JsonString str:
                    WriteString(str.Value, builder);
                    return;
                case JsonArray array:
                    WriteArray(array, builder, pretty, depth);
                    return;
                case JsonObject obj:
                    WriteObject(obj, builder, pretty, depth);
                    return;
                default:
                    throw new JsonDataException("Unsupported JSON value type '" + value.GetType().Name + "'.", "$");
            }
        }

        private static void WriteNumber(JsonNumber number, StringBuilder builder)
        {
            if (number.IsInteger)
                builder.Append(((long)number.Value).ToString(CultureInfo.InvariantCulture));
            else
                builder.Append(number.Value.ToString("R", CultureInfo.InvariantCulture));
        }

        private static void WriteArray(JsonArray array, StringBuilder builder, bool pretty, int depth)
        {
            builder.Append('[');
            for (var i = 0; i < array.Items.Count; i++)
            {
                if (i > 0) builder.Append(',');
                if (pretty)
                {
                    builder.Append('\n');
                    Indent(builder, depth + 1);
                }

                Write(array.Items[i], builder, pretty, depth + 1);
            }

            if (pretty && array.Items.Count > 0)
            {
                builder.Append('\n');
                Indent(builder, depth);
            }

            builder.Append(']');
        }

        private static void WriteObject(JsonObject obj, StringBuilder builder, bool pretty, int depth)
        {
            builder.Append('{');
            for (var i = 0; i < obj.Members.Count; i++)
            {
                if (i > 0) builder.Append(',');
                if (pretty)
                {
                    builder.Append('\n');
                    Indent(builder, depth + 1);
                }

                WriteString(obj.Members[i].Key, builder);
                builder.Append(':');
                if (pretty) builder.Append(' ');
                Write(obj.Members[i].Value, builder, pretty, depth + 1);
            }

            if (pretty && obj.Members.Count > 0)
            {
                builder.Append('\n');
                Indent(builder, depth);
            }

            builder.Append('}');
        }

        private static void Indent(StringBuilder builder, int depth)
        {
            builder.Append(' ', depth * 2);
        }

        private static void WriteString(string text, StringBuilder builder)
        {
            builder.Append('"');
            for (var i = 0; i < text.Length; i++)
            {
                var c = text[i];
                switch (c)
                {
                    case '"': builder.Append("\\\""); break;
                    case '\\': builder.Append("\\\\"); break;
                    case '\b': builder.Append("\\b"); break;
                    case '\f': builder.Append("\\f"); break;
                    case '\n': builder.Append("\\n"); break;
                    case '\r': builder.Append("\\r"); break;
                    case '\t': builder.Append("\\t"); break;
                    default:
                        if (c < 0x20)
                            builder.Append("\\u").Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                        else
                            builder.Append(c);
                        break;
                }
            }

            builder.Append('"');
        }
    }
}
