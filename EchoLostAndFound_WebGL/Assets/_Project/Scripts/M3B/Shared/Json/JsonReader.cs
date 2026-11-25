using System;
using System.Globalization;
using System.Text;

namespace EchoLostAndFound.Shared.Json
{
    /// <summary>
    /// Strict JSON parser: no comments, no trailing commas, no duplicate member names,
    /// no NaN/Infinity, no unescaped control characters, bounded nesting depth.
    /// Errors carry the 1-based source position and the JSON path being parsed.
    /// </summary>
    public static class JsonReader
    {
        public const int MaxDepth = 64;
        public const int MaxDocumentLength = 4 * 1024 * 1024;

        public static JsonValue Parse(string json)
        {
            if (json == null) throw new ArgumentNullException(nameof(json));
            if (json.Length == 0) throw new JsonDataException("JSON document is empty.", "$");
            if (json.Length > MaxDocumentLength)
                throw new JsonDataException("JSON document exceeds " + MaxDocumentLength + " characters.", "$");
            if (json[0] == '\uFEFF') json = json.Substring(1);

            var state = new ParserState(json);
            state.SkipWhitespace();
            var value = state.ParseValue("$", 0);
            state.SkipWhitespace();
            if (!state.AtEnd)
                throw state.Error("Unexpected trailing content.");
            return value;
        }

        private sealed class ParserState
        {
            private readonly string text;
            private int index;

            public ParserState(string text)
            {
                this.text = text;
            }

            public bool AtEnd => index >= text.Length;

            public JsonDataException Error(string message)
            {
                var position = Translate(index);
                return new JsonDataException(message, "$", position.Line, position.Column, "VALIDATION_ERROR");
            }

            public JsonDataException Error(string message, string path)
            {
                var position = Translate(index);
                return new JsonDataException(message, path, position.Line, position.Column, "VALIDATION_ERROR");
            }

            private (int Line, int Column) Translate(int charIndex)
            {
                var line = 1;
                var column = 1;
                var limit = Math.Min(charIndex, text.Length);
                for (var i = 0; i < limit; i++)
                {
                    if (text[i] == '\n')
                    {
                        line++;
                        column = 1;
                    }
                    else
                    {
                        column++;
                    }
                }

                return (line, column);
            }

            public void SkipWhitespace()
            {
                while (!AtEnd)
                {
                    var c = text[index];
                    if (c == ' ' || c == '\t' || c == '\n' || c == '\r')
                    {
                        index++;
                        continue;
                    }

                    break;
                }
            }

            public JsonValue ParseValue(string path, int depth)
            {
                if (depth > MaxDepth) throw Error("JSON nesting exceeds " + MaxDepth + " levels.", path);
                if (AtEnd) throw Error("Unexpected end of JSON document.", path);

                var c = text[index];
                switch (c)
                {
                    case '{':
                        return ParseObject(path, depth);
                    case '[':
                        return ParseArray(path, depth);
                    case '"':
                        return new JsonString(ParseString(path));
                    case 't':
                        ExpectLiteral("true", path);
                        return JsonBool.True;
                    case 'f':
                        ExpectLiteral("false", path);
                        return JsonBool.False;
                    case 'n':
                        ExpectLiteral("null", path);
                        return JsonNull.Instance;
                    default:
                        if (c == '-' || (c >= '0' && c <= '9')) return ParseNumber(path);
                        throw Error("Unexpected character '" + c + "'.", path);
                }
            }

            private void ExpectLiteral(string literal, string path)
            {
                if (index + literal.Length > text.Length ||
                    string.CompareOrdinal(text, index, literal, 0, literal.Length) != 0)
                    throw Error("Expected literal '" + literal + "'.", path);
                index += literal.Length;
            }

            private JsonObject ParseObject(string path, int depth)
            {
                var obj = new JsonObject();
                index++; // '{'
                SkipWhitespace();
                if (!AtEnd && text[index] == '}')
                {
                    index++;
                    return obj;
                }

                while (true)
                {
                    SkipWhitespace();
                    if (AtEnd || text[index] != '"')
                        throw Error("Expected a member name string.", path);
                    var line = Translate(index).Line;
                    var column = Translate(index).Column;
                    var name = ParseString(path);
                    var memberPath = path == "$" ? "$." + name : path + "." + name;
                    if (obj.ContainsKey(name))
                        throw new JsonDataException("Duplicate member '" + name + "'.", memberPath, line, column, "VALIDATION_ERROR");

                    SkipWhitespace();
                    if (AtEnd || text[index] != ':') throw Error("Expected ':' after member name.", memberPath);
                    index++;
                    SkipWhitespace();
                    obj.Add(name, ParseValue(memberPath, depth + 1));
                    SkipWhitespace();
                    if (AtEnd) throw Error("Unterminated JSON object.", path);
                    if (text[index] == ',')
                    {
                        index++;
                        SkipWhitespace();
                        if (!AtEnd && text[index] == '}')
                            throw Error("Trailing comma is not valid JSON.", path);
                        continue;
                    }

                    if (text[index] == '}')
                    {
                        index++;
                        return obj;
                    }

                    throw Error("Expected ',' or '}' in object.", path);
                }
            }

            private JsonArray ParseArray(string path, int depth)
            {
                var array = new JsonArray();
                index++; // '['
                SkipWhitespace();
                if (!AtEnd && text[index] == ']')
                {
                    index++;
                    return array;
                }

                var itemIndex = 0;
                while (true)
                {
                    SkipWhitespace();
                    array.Add(ParseValue(path + "[" + itemIndex + "]", depth + 1));
                    itemIndex++;
                    SkipWhitespace();
                    if (AtEnd) throw Error("Unterminated JSON array.", path);
                    if (text[index] == ',')
                    {
                        index++;
                        SkipWhitespace();
                        if (!AtEnd && text[index] == ']')
                            throw Error("Trailing comma is not valid JSON.", path);
                        continue;
                    }

                    if (text[index] == ']')
                    {
                        index++;
                        return array;
                    }

                    throw Error("Expected ',' or ']' in array.", path);
                }
            }

            private string ParseString(string path)
            {
                index++; // opening quote
                var builder = new StringBuilder();
                while (true)
                {
                    if (AtEnd) throw Error("Unterminated string.", path);
                    var c = text[index++];
                    if (c == '"') return builder.ToString();
                    if (c == '\\')
                    {
                        if (AtEnd) throw Error("Unterminated escape sequence.", path);
                        var escape = text[index++];
                        switch (escape)
                        {
                            case '"': builder.Append('"'); break;
                            case '\\': builder.Append('\\'); break;
                            case '/': builder.Append('/'); break;
                            case 'b': builder.Append('\b'); break;
                            case 'f': builder.Append('\f'); break;
                            case 'n': builder.Append('\n'); break;
                            case 'r': builder.Append('\r'); break;
                            case 't': builder.Append('\t'); break;
                            case 'u':
                                if (index + 4 > text.Length) throw Error("Truncated \\u escape.", path);
                                var hex = text.Substring(index, 4);
                                if (!int.TryParse(hex, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var code))
                                    throw Error("Invalid \\u escape '" + hex + "'.", path);
                                builder.Append((char)code);
                                index += 4;
                                break;
                            default:
                                throw Error("Invalid escape '\\" + escape + "'.", path);
                        }

                        continue;
                    }

                    if (c < 0x20) throw Error("Unescaped control character in string.", path);
                    builder.Append(c);
                }
            }

            private JsonNumber ParseNumber(string path)
            {
                var start = index;
                if (text[index] == '-') index++;
                if (AtEnd) throw Error("Truncated number.", path);
                if (text[index] == '0')
                {
                    index++;
                    if (!AtEnd && text[index] >= '0' && text[index] <= '9')
                        throw Error("Numbers must not have leading zeros.", path);
                }
                else if (text[index] >= '1' && text[index] <= '9')
                {
                    while (!AtEnd && text[index] >= '0' && text[index] <= '9') index++;
                }
                else
                {
                    throw Error("Invalid number.", path);
                }

                if (!AtEnd && text[index] == '.')
                {
                    index++;
                    if (AtEnd || text[index] < '0' || text[index] > '9')
                        throw Error("Number requires digits after '.'.", path);
                    while (!AtEnd && text[index] >= '0' && text[index] <= '9') index++;
                }

                if (!AtEnd && (text[index] == 'e' || text[index] == 'E'))
                {
                    index++;
                    if (!AtEnd && (text[index] == '+' || text[index] == '-')) index++;
                    if (AtEnd || text[index] < '0' || text[index] > '9')
                        throw Error("Number exponent requires digits.", path);
                    while (!AtEnd && text[index] >= '0' && text[index] <= '9') index++;
                }

                var literal = text.Substring(start, index - start);
                if (!double.TryParse(literal, NumberStyles.Float, CultureInfo.InvariantCulture, out var value) ||
                    double.IsNaN(value) || double.IsInfinity(value))
                    throw Error("Number '" + literal + "' is out of range.", path);
                return new JsonNumber(value);
            }
        }
    }
}
