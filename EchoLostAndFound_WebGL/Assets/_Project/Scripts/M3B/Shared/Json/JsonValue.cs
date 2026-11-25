using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;

namespace EchoLostAndFound.Shared.Json
{
    public enum JsonKind
    {
        Null,
        Bool,
        Number,
        String,
        Array,
        Object
    }

    /// <summary>
    /// Minimal, allocation-friendly JSON DOM. Deliberately hand written: the client
    /// targets netstandard2.1 / Unity 6.3 where System.Text.Json is not available, and
    /// the project has no approved third-party JSON dependency (DataSchema §9.3 notes
    /// Newtonsoft remains a candidate but is not installed or approved).
    /// </summary>
    public abstract class JsonValue
    {
        public abstract JsonKind Kind { get; }

        public static JsonValue Parse(string json)
        {
            return JsonReader.Parse(json);
        }

        public string ToJson(bool pretty = false)
        {
            return JsonWriter.Serialize(this, pretty);
        }

        public JsonObject AsObject(string jsonPath)
        {
            if (this is JsonObject obj) return obj;
            throw new JsonDataException("Expected a JSON object but found " + Kind + ".", jsonPath);
        }

        public JsonArray AsArray(string jsonPath)
        {
            if (this is JsonArray array) return array;
            throw new JsonDataException("Expected a JSON array but found " + Kind + ".", jsonPath);
        }

        public string AsString(string jsonPath)
        {
            if (this is JsonString str) return str.Value;
            throw new JsonDataException("Expected a JSON string but found " + Kind + ".", jsonPath);
        }

        public bool AsBool(string jsonPath)
        {
            if (this is JsonBool boolean) return boolean.Value;
            throw new JsonDataException("Expected a JSON boolean but found " + Kind + ".", jsonPath);
        }

        public double AsDouble(string jsonPath)
        {
            if (this is JsonNumber number) return number.Value;
            throw new JsonDataException("Expected a JSON number but found " + Kind + ".", jsonPath);
        }

        public override string ToString()
        {
            return ToJson();
        }
    }

    public sealed class JsonNull : JsonValue
    {
        public static readonly JsonNull Instance = new JsonNull();

        private JsonNull()
        {
        }

        public override JsonKind Kind => JsonKind.Null;
    }

    public sealed class JsonBool : JsonValue
    {
        public static readonly JsonBool True = new JsonBool(true);
        public static readonly JsonBool False = new JsonBool(false);

        public JsonBool(bool value)
        {
            Value = value;
        }

        public bool Value { get; }

        public override JsonKind Kind => JsonKind.Bool;

        public static JsonBool From(bool value)
        {
            return value ? True : False;
        }
    }

    public sealed class JsonNumber : JsonValue
    {
        public JsonNumber(double value)
        {
            if (double.IsNaN(value) || double.IsInfinity(value))
                throw new JsonDataException("JSON numbers must not be NaN or Infinity.", "$");
            Value = value;
        }

        public double Value { get; }

        public override JsonKind Kind => JsonKind.Number;

        public bool IsInteger => Math.Floor(Value) == Value && Math.Abs(Value) <= 9007199254740991d;

        public int ToInt32(string jsonPath)
        {
            if (!IsInteger || Value < int.MinValue || Value > int.MaxValue)
                throw new JsonDataException("Expected a 32-bit integer but found " + Value.ToString(CultureInfo.InvariantCulture) + ".", jsonPath);
            return (int)Value;
        }
    }

    public sealed class JsonString : JsonValue
    {
        public JsonString(string value)
        {
            Value = value ?? throw new ArgumentNullException(nameof(value));
        }

        public string Value { get; }

        public override JsonKind Kind => JsonKind.String;
    }

    public sealed class JsonArray : JsonValue, IEnumerable<JsonValue>
    {
        private readonly List<JsonValue> items = new List<JsonValue>();

        public IReadOnlyList<JsonValue> Items => items;

        public int Count => items.Count;

        public override JsonKind Kind => JsonKind.Array;

        public JsonArray Add(JsonValue value)
        {
            items.Add(value ?? JsonNull.Instance);
            return this;
        }

        public JsonArray Add(string value)
        {
            return Add(value == null ? JsonNull.Instance : new JsonString(value));
        }

        public JsonArray Add(bool value)
        {
            return Add(JsonBool.From(value));
        }

        public JsonArray Add(double value)
        {
            return Add(new JsonNumber(value));
        }

        public JsonValue this[int index] => items[index];

        public string GetString(int index, string jsonPath)
        {
            if (index < 0 || index >= items.Count)
                throw new JsonDataException("Array index out of range.", jsonPath + "[" + index + "]");
            return items[index].AsString(jsonPath + "[" + index + "]");
        }

        public IEnumerator<JsonValue> GetEnumerator()
        {
            return items.GetEnumerator();
        }

        IEnumerator IEnumerable.GetEnumerator()
        {
            return GetEnumerator();
        }
    }

    /// <summary>
    /// Insertion ordered object. Strict parsers reject duplicate member names, and the
    /// writer preserves insertion order so snapshots are byte-for-byte reproducible.
    /// </summary>
    public sealed class JsonObject : JsonValue, IEnumerable<KeyValuePair<string, JsonValue>>
    {
        private readonly List<KeyValuePair<string, JsonValue>> members = new List<KeyValuePair<string, JsonValue>>();

        public IReadOnlyList<KeyValuePair<string, JsonValue>> Members => members;

        public int Count => members.Count;

        public override JsonKind Kind => JsonKind.Object;

        public bool ContainsKey(string name)
        {
            return IndexOf(name) >= 0;
        }

        public JsonValue this[string name]
        {
            get
            {
                var index = IndexOf(name);
                return index < 0 ? null : members[index].Value;
            }
        }

        public JsonObject Add(string name, JsonValue value)
        {
            if (string.IsNullOrEmpty(name)) throw new ArgumentException("Member name is required.", nameof(name));
            if (IndexOf(name) >= 0) throw new ArgumentException("Duplicate member '" + name + "'.", nameof(name));
            members.Add(new KeyValuePair<string, JsonValue>(name, value ?? JsonNull.Instance));
            return this;
        }

        public JsonObject Add(string name, string value)
        {
            return Add(name, value == null ? (JsonValue)JsonNull.Instance : new JsonString(value));
        }

        public JsonObject Add(string name, bool value)
        {
            return Add(name, JsonBool.From(value));
        }

        public JsonObject Add(string name, double value)
        {
            return Add(name, new JsonNumber(value));
        }

        public JsonObject Add(string name, int value)
        {
            return Add(name, new JsonNumber(value));
        }

        public JsonObject Add(string name, JsonArray value)
        {
            return Add(name, (JsonValue)value);
        }

        public JsonObject Add(string name, JsonObject value)
        {
            return Add(name, (JsonValue)value);
        }

        public JsonObject AddStringArray(string name, IEnumerable<string> values)
        {
            var array = new JsonArray();
            if (values != null)
            {
                foreach (var value in values) array.Add(value);
            }

            return Add(name, array);
        }

        private int IndexOf(string name)
        {
            for (var i = 0; i < members.Count; i++)
            {
                if (string.Equals(members[i].Key, name, StringComparison.Ordinal)) return i;
            }

            return -1;
        }

        public IEnumerator<KeyValuePair<string, JsonValue>> GetEnumerator()
        {
            return members.GetEnumerator();
        }

        IEnumerator IEnumerable.GetEnumerator()
        {
            return GetEnumerator();
        }
    }
}
