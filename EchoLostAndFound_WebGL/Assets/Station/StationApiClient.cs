using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using EchoLostAndFound.Shared.Json;
using UnityEngine;
using UnityEngine.Networking;

namespace EchoStation
{
    /// <summary>
    /// One HTTP call's outcome. The server contract (API_CONTRACT.md section 1.1) wraps every
    /// reply in <c>{request_id, data, error}</c>; <see cref="Data"/> is that envelope's data
    /// object and <see cref="ErrorCode"/> is its error code when the call failed.
    /// </summary>
    public sealed class StationApiResult
    {
        public bool Ok;
        public int Status;
        public string RequestId;
        public string ErrorCode;
        public string ErrorMessage;
        public bool TimedOut;
        public JsonObject Data;

        public bool IsNetworkFailure =>
            TimedOut || string.Equals(ErrorCode, StationApiClient.NetworkErrorCode, StringComparison.Ordinal);
    }

    /// <summary>
    /// Thin UnityWebRequest wrapper for the M4-B FastAPI contract. Coroutine based so WebGL
    /// never blocks; there is no model key and no provider logic on this side.
    /// </summary>
    public sealed class StationApiClient
    {
        public const string ContentVersion = "story-v1.0-phase2";
        public const string NetworkErrorCode = "network_unavailable";
        public const string ClientTimeoutCode = "client_timeout";
        public const int DefaultTimeoutMs = 15000;
        public const int DefaultTurnTimeoutMs = 12000;

        readonly string baseUrl;

        public StationApiClient(string baseUrl)
        {
            this.baseUrl = TrimSlash(string.IsNullOrWhiteSpace(baseUrl) ? "http://127.0.0.1:8787" : baseUrl.Trim());
        }

        public string BaseUrl => baseUrl;

        /// <summary>
        /// WebGL/desktop player: same origin as the page that served the build. Editor and
        /// headless runs: the documented local server. <c>?api=http://host:port</c> overrides
        /// both, which is how a ModelScope space can be exercised from another origin.
        /// </summary>
        public static string ResolveBaseUrl()
        {
            var overrideUrl = QueryValue(Application.absoluteURL, "api");
            if (!string.IsNullOrEmpty(overrideUrl)) return TrimSlash(overrideUrl);

            var absolute = Application.absoluteURL;
            if (!string.IsNullOrEmpty(absolute)
                && (absolute.StartsWith("http://", StringComparison.OrdinalIgnoreCase)
                    || absolute.StartsWith("https://", StringComparison.OrdinalIgnoreCase)))
            {
                return TrimSlash(Origin(absolute));
            }

            return "http://127.0.0.1:8787";
        }

        public IEnumerator GetMeta(Action<StationApiResult> done)
        {
            return Send("GET", "/api/v1/meta", null, DefaultTimeoutMs, done);
        }

        public IEnumerator CreateSession(
            string npcId,
            IEnumerable<string> evidenceIds,
            IEnumerable<string> observedFieldIds,
            Action<StationApiResult> done)
        {
            var body = new JsonObject()
                .Add("npc_id", npcId)
                .AddStringArray("evidence_ids", evidenceIds)
                .AddStringArray("observed_field_ids", observedFieldIds);
            return Send("POST", "/api/v1/sessions", body, DefaultTimeoutMs, done);
        }

        public IEnumerator TakeTurn(
            string conversationId,
            string text,
            IEnumerable<string> evidenceIds,
            IEnumerable<string> observedFieldIds,
            int timeoutMs,
            Action<StationApiResult> done)
        {
            if (string.IsNullOrEmpty(conversationId))
            {
                done(Failure(ClientTimeoutCode, "会话尚未建立。"));
                return Empty();
            }

            var body = new JsonObject()
                .Add("text", text)
                .Add("timeout_ms", Mathf.Clamp(timeoutMs, 100, 30000))
                .AddStringArray("evidence_ids", evidenceIds)
                .AddStringArray("observed_field_ids", observedFieldIds);
            return Send("POST", "/api/v1/sessions/" + Escape(conversationId) + "/turns", body, timeoutMs + 3000, done);
        }

        public IEnumerator PresentEvidence(
            string conversationId,
            IReadOnlyList<string> evidenceIds,
            IEnumerable<string> observedFieldIds,
            Action<StationApiResult> done)
        {
            if (string.IsNullOrEmpty(conversationId) || evidenceIds == null || evidenceIds.Count == 0)
            {
                done(Failure(NetworkErrorCode, "没有可出示的证据。"));
                return Empty();
            }

            var body = new JsonObject()
                .AddStringArray("evidence_ids", evidenceIds)
                .AddStringArray("observed_field_ids", observedFieldIds);
            return Send("POST", "/api/v1/sessions/" + Escape(conversationId) + "/evidence", body, DefaultTimeoutMs, done);
        }

        public IEnumerator Cancel(string conversationId, Action<StationApiResult> done)
        {
            if (string.IsNullOrEmpty(conversationId))
            {
                done(Failure(NetworkErrorCode, "没有会话可取消。"));
                return Empty();
            }

            return Send("POST", "/api/v1/sessions/" + Escape(conversationId) + "/cancel", null, DefaultTimeoutMs, done);
        }

        // ------------------------------------------------------------ transport

        IEnumerator Send(string method, string path, JsonObject body, int timeoutMs, Action<StationApiResult> done)
        {
            var result = new StationApiResult();
            var url = baseUrl + path;
            var request = new UnityWebRequest(url, method)
            {
                downloadHandler = new DownloadHandlerBuffer()
            };
            request.SetRequestHeader("Accept", "application/json");
            request.SetRequestHeader("X-Request-ID", Guid.NewGuid().ToString("N"));
            if (body != null)
            {
                request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(body.ToJson()));
                request.SetRequestHeader("Content-Type", "application/json");
            }

            var operation = request.SendWebRequest();
            var deadline = Time.realtimeSinceStartup + Mathf.Max(1, timeoutMs) / 1000f;
            while (!operation.isDone)
            {
                if (Time.realtimeSinceStartup >= deadline)
                {
                    result.TimedOut = true;
                    result.ErrorCode = ClientTimeoutCode;
                    result.ErrorMessage = "请求超时。";
                    request.Abort();
                    break;
                }

                yield return null;
            }

            if (result.TimedOut)
            {
                request.Dispose();
                Debug.LogWarning("M4C api timeout " + method + " " + path);
                done(result);
                yield break;
            }

            result.Status = (int)request.responseCode;
            var transportFailed = request.result == UnityWebRequest.Result.ConnectionError
                                  || request.result == UnityWebRequest.Result.DataProcessingError;
            var protocolFailed = request.result == UnityWebRequest.Result.ProtocolError;
            var text = request.downloadHandler != null ? request.downloadHandler.text : null;
            request.Dispose();

            var envelope = ParseObject(text);
            if (envelope != null)
            {
                result.RequestId = TryString(envelope, "request_id");
                if (envelope["error"] is JsonObject error)
                {
                    result.ErrorCode = TryString(error, "code");
                    result.ErrorMessage = TryString(error, "message");
                }

                result.Data = envelope["data"] as JsonObject;
            }

            result.Ok = !transportFailed && !protocolFailed
                        && result.Status >= 200 && result.Status < 300 && result.Data != null;
            if (!result.Ok)
            {
                if (string.IsNullOrEmpty(result.ErrorCode))
                    result.ErrorCode = transportFailed ? NetworkErrorCode : "http_" + result.Status;
                if (string.IsNullOrEmpty(result.ErrorMessage))
                    result.ErrorMessage = transportFailed ? "无法连接服务。" : "服务返回了错误。";
                Debug.LogWarning("M4C api " + method + " " + path + " -> " + result.Status + " " + result.ErrorCode);
            }

            done(result);
        }

        static IEnumerator Empty()
        {
            yield break;
        }

        static StationApiResult Failure(string code, string message)
        {
            return new StationApiResult { ErrorCode = code, ErrorMessage = message };
        }

        internal static JsonObject ParseObject(string text)
        {
            if (string.IsNullOrEmpty(text)) return null;
            try
            {
                return JsonValue.Parse(text) as JsonObject;
            }
            catch (Exception error)
            {
                Debug.LogWarning("M4C api json: " + error.Message);
                return null;
            }
        }

        /// <summary>Null-safe member read; Schema-strict parsing is not needed here.</summary>
        public static string TryString(JsonObject obj, string name)
        {
            var value = obj?[name];
            return value is JsonString text ? text.Value : null;
        }

        public static bool TryBool(JsonObject obj, string name, bool fallback = false)
        {
            var value = obj?[name];
            return value is JsonBool flag ? flag.Value : fallback;
        }

        public static JsonArray TryArray(JsonObject obj, string name)
        {
            return obj?[name] as JsonArray;
        }

        public static JsonObject TryObject(JsonObject obj, string name)
        {
            return obj?[name] as JsonObject;
        }

        public static IReadOnlyList<string> StringArray(JsonArray array)
        {
            var values = new List<string>();
            if (array == null) return values;
            foreach (var item in array.Items)
            {
                if (item is JsonString text) values.Add(text.Value);
            }

            return values;
        }

        static string QueryValue(string url, string key)
        {
            if (string.IsNullOrEmpty(url)) return null;
            var question = url.IndexOf('?');
            if (question < 0 || question == url.Length - 1) return null;
            var query = url.Substring(question + 1);
            var hash = query.IndexOf('#');
            if (hash >= 0) query = query.Substring(0, hash);
            foreach (var pair in query.Split('&'))
            {
                var equals = pair.IndexOf('=');
                if (equals <= 0) continue;
                if (!string.Equals(pair.Substring(0, equals), key, StringComparison.OrdinalIgnoreCase)) continue;
                return Uri.UnescapeDataString(pair.Substring(equals + 1));
            }

            return null;
        }

        static string Origin(string url)
        {
            var scheme = url.IndexOf("://", StringComparison.Ordinal);
            if (scheme < 0) return url;
            var hostStart = scheme + 3;
            var slash = url.IndexOfAny(new[] { '/', '?', '#' }, hostStart);
            return slash < 0 ? url : url.Substring(0, slash);
        }

        static string TrimSlash(string value)
        {
            return value.EndsWith("/", StringComparison.Ordinal) ? value.Substring(0, value.Length - 1) : value;
        }

        static string Escape(string value)
        {
            return Uri.EscapeDataString(value);
        }
    }
}
