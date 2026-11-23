using System;

namespace EchoLostAndFound.Shared.Json
{
    /// <summary>
    /// Raised when a JSON document is syntactically invalid, violates the declared
    /// contract (unknown field, wrong type, unknown enum value) or does not match
    /// the persisted content version. The message is safe to show to developers
    /// and never contains story content that the player has not seen.
    /// </summary>
    public sealed class JsonDataException : Exception
    {
        public JsonDataException(string message, string jsonPath, int line, int column, string errorCode)
            : base(message)
        {
            JsonPath = jsonPath ?? "$";
            Line = line;
            Column = column;
            ErrorCode = errorCode ?? "VALIDATION_ERROR";
        }

        public JsonDataException(string message, string jsonPath)
            : this(message, jsonPath, 0, 0, "VALIDATION_ERROR")
        {
        }

        public JsonDataException(string message, string jsonPath, string errorCode)
            : this(message, jsonPath, 0, 0, errorCode)
        {
        }

        public string JsonPath { get; }

        /// <summary>1-based source line, or 0 when the error is not positional.</summary>
        public int Line { get; }

        /// <summary>1-based source column, or 0 when the error is not positional.</summary>
        public int Column { get; }

        /// <summary>DataSchema error code, default VALIDATION_ERROR.</summary>
        public string ErrorCode { get; }

        public override string ToString()
        {
            var location = Line > 0 ? " (line " + Line + ", column " + Column + ")" : string.Empty;
            return "JsonDataException[" + ErrorCode + "] at " + JsonPath + location + ": " + Message;
        }
    }
}
