using System;
using System.Collections.Generic;

namespace EchoLostAndFound.Shared.Json
{
    /// <summary>
    /// Typed accessors with JSON-path aware errors and a strict unknown-field policy.
    /// DataSchema §1: "未知字段一律拒绝" — every object decode must call
    /// <see cref="RejectUnknownFields"/>.
    /// </summary>
    public static class JsonContract
    {
        public static string MemberPath(string parentPath, string name)
        {
            if (string.IsNullOrEmpty(parentPath) || parentPath == "$") return "$." + name;
            return parentPath + "." + name;
        }

        public static string IndexPath(string parentPath, int index)
        {
            return parentPath + "[" + index + "]";
        }

        public static JsonObject RequireObject(JsonValue value, string path)
        {
            if (value is JsonObject obj) return obj;
            throw new JsonDataException("Expected an object but found " + Describe(value) + ".", path);
        }

        public static JsonArray RequireArray(JsonValue value, string path)
        {
            if (value is JsonArray array) return array;
            throw new JsonDataException("Expected an array but found " + Describe(value) + ".", path);
        }

        public static string RequireString(JsonObject obj, string name, string path)
        {
            var memberPath = MemberPath(path, name);
            var value = obj[name];
            if (value == null) throw new JsonDataException("Missing required member '" + name + "'.", memberPath);
            if (value is JsonString str)
            {
                if (string.IsNullOrEmpty(str.Value))
                    throw new JsonDataException("Member '" + name + "' must not be empty.", memberPath);
                return str.Value;
            }

            throw new JsonDataException("Member '" + name + "' must be a string but found " + Describe(value) + ".", memberPath);
        }

        public static string OptionalString(JsonObject obj, string name, string path)
        {
            var value = obj[name];
            if (value == null || value is JsonNull) return null;
            return value.AsString(MemberPath(path, name));
        }

        public static bool RequireBool(JsonObject obj, string name, string path)
        {
            var memberPath = MemberPath(path, name);
            var value = obj[name];
            if (value == null) throw new JsonDataException("Missing required member '" + name + "'.", memberPath);
            if (value is JsonBool boolean) return boolean.Value;
            throw new JsonDataException("Member '" + name + "' must be a boolean but found " + Describe(value) + ".", memberPath);
        }

        public static bool OptionalBool(JsonObject obj, string name, string path, bool fallback)
        {
            var value = obj[name];
            if (value == null || value is JsonNull) return fallback;
            if (value is JsonBool boolean) return boolean.Value;
            throw new JsonDataException("Member '" + name + "' must be a boolean but found " + Describe(value) + ".", MemberPath(path, name));
        }

        public static int RequireInt(JsonObject obj, string name, string path)
        {
            var memberPath = MemberPath(path, name);
            var value = obj[name];
            if (value == null) throw new JsonDataException("Missing required member '" + name + "'.", memberPath);
            if (value is JsonNumber number) return number.ToInt32(memberPath);
            throw new JsonDataException("Member '" + name + "' must be a number but found " + Describe(value) + ".", memberPath);
        }

        public static int OptionalInt(JsonObject obj, string name, string path, int fallback)
        {
            var value = obj[name];
            if (value == null || value is JsonNull) return fallback;
            if (value is JsonNumber number) return number.ToInt32(MemberPath(path, name));
            throw new JsonDataException("Member '" + name + "' must be a number but found " + Describe(value) + ".", MemberPath(path, name));
        }

        public static IReadOnlyList<string> RequireStringArray(JsonObject obj, string name, string path)
        {
            var memberPath = MemberPath(path, name);
            var value = obj[name];
            if (value == null) throw new JsonDataException("Missing required member '" + name + "'.", memberPath);
            return ReadStringArray(value, memberPath);
        }

        public static IReadOnlyList<string> OptionalStringArray(JsonObject obj, string name, string path)
        {
            var memberPath = MemberPath(path, name);
            var value = obj[name];
            if (value == null || value is JsonNull) return Array.Empty<string>();
            return ReadStringArray(value, memberPath);
        }

        public static IReadOnlyList<string> ReadStringArray(JsonValue value, string path)
        {
            var array = RequireArray(value, path);
            var result = new List<string>(array.Count);
            for (var i = 0; i < array.Count; i++)
            {
                var itemPath = IndexPath(path, i);
                if (!(array[i] is JsonString str))
                    throw new JsonDataException("Expected a string array element but found " + Describe(array[i]) + ".", itemPath);
                if (string.IsNullOrEmpty(str.Value))
                    throw new JsonDataException("String array elements must not be empty.", itemPath);
                result.Add(str.Value);
            }

            return result;
        }

        public static JsonArray RequireArrayMember(JsonObject obj, string name, string path)
        {
            var memberPath = MemberPath(path, name);
            var value = obj[name];
            if (value == null) throw new JsonDataException("Missing required member '" + name + "'.", memberPath);
            return RequireArray(value, memberPath);
        }

        /// <summary>
        /// Rejects any member that is not part of the declared contract. Call this
        /// before reading fields so unknown-field errors point at the offending key.
        /// </summary>
        public static void RejectUnknownFields(JsonObject obj, string path, params string[] allowed)
        {
            var allowedSet = new HashSet<string>(allowed, StringComparer.Ordinal);
            foreach (var member in obj.Members)
            {
                if (!allowedSet.Contains(member.Key))
                    throw new JsonDataException("Unknown field '" + member.Key + "'.", MemberPath(path, member.Key));
            }
        }

        public static T ParseEnum<T>(string raw, string path, Func<string, T?> resolver, string allowedDescription)
            where T : struct
        {
            var resolved = resolver(raw);
            if (!resolved.HasValue)
                throw new JsonDataException("Unknown value '" + raw + "'. Allowed: " + allowedDescription + ".", path);
            return resolved.Value;
        }

        public static string Describe(JsonValue value)
        {
            if (value == null) return "nothing";
            switch (value.Kind)
            {
                case JsonKind.Null: return "null";
                case JsonKind.Bool: return "a boolean";
                case JsonKind.Number: return "a number";
                case JsonKind.String: return "a string";
                case JsonKind.Array: return "an array";
                case JsonKind.Object: return "an object";
                default: return value.Kind.ToString();
            }
        }
    }
}
