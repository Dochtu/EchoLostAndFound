using System;
using EchoLostAndFound.Shared.Ai;

namespace EchoLostAndFound.MockAi
{
    /// <summary>
    /// Transport boundary for a future real LLM service. M3-B ships no network
    /// implementation and no API key: the backend team implements this interface and passes
    /// it to <see cref="LlmBackedNpcAiProvider"/>; until then every call falls back.
    /// </summary>
    public interface ILlmNpcReplyTransport
    {
        /// <summary>
        /// Sends one turn to the model service. Implementations must honour
        /// <see cref="NpcAiRequest.TimeoutMilliseconds"/> and must not send secrets from the
        /// client (API keys stay in server environment variables).
        /// </summary>
        LlmTransportResponse Send(NpcAiRequest request);
    }

    public sealed class LlmTransportResponse
    {
        private LlmTransportResponse(bool isSuccess, string rawContent, string errorCode)
        {
            IsSuccess = isSuccess;
            RawContent = rawContent;
            ErrorCode = errorCode;
        }

        public bool IsSuccess { get; }

        public string RawContent { get; }

        /// <summary>"timeout", "transport_error", "http_4xx", "http_5xx", ...</summary>
        public string ErrorCode { get; }

        public static LlmTransportResponse Success(string rawContent)
        {
            return new LlmTransportResponse(true, rawContent, null);
        }

        public static LlmTransportResponse Failure(string errorCode)
        {
            return new LlmTransportResponse(false, null, errorCode ?? "transport_error");
        }
    }

    /// <summary>
    /// Adapter that turns a real model transport into an <see cref="INpcAiProvider"/>.
    /// All output passes the same validator as the mock provider; fallback mapping follows
    /// DataSchema §5 fallback_reason values. The adapter performs no network calls itself and
    /// reports <c>transport_not_configured</c> when no transport was supplied.
    /// </summary>
    public sealed class LlmBackedNpcAiProvider : INpcAiProvider
    {
        public const string DefaultProviderId = "external-llm";

        private readonly ILlmNpcReplyTransport transport;

        public LlmBackedNpcAiProvider(ILlmNpcReplyTransport transport, string providerId = null)
        {
            this.transport = transport;
            ProviderId = string.IsNullOrWhiteSpace(providerId) ? DefaultProviderId : providerId;
        }

        public string ProviderId { get; }

        public NpcAiReply Generate(NpcAiRequest request)
        {
            if (request == null) throw new ArgumentNullException(nameof(request));

            if (transport == null)
            {
                return NpcAiReply.Failed(NpcAiOutcome.ModelUnavailable, ProviderId, "transport_not_configured");
            }

            LlmTransportResponse response;
            try
            {
                response = transport.Send(request);
            }
            catch (TimeoutException)
            {
                return NpcAiReply.Failed(NpcAiOutcome.TimedOut, ProviderId, "transport_timeout");
            }
            catch (Exception ex)
            {
                return NpcAiReply.Failed(NpcAiOutcome.ModelUnavailable, ProviderId, "transport_fault: " + ex.GetType().Name);
            }

            if (response == null)
            {
                return NpcAiReply.Failed(NpcAiOutcome.InvalidOutput, ProviderId, "null_transport_response");
            }

            if (!response.IsSuccess)
            {
                if (string.Equals(response.ErrorCode, "timeout", StringComparison.Ordinal))
                {
                    return NpcAiReply.Failed(NpcAiOutcome.TimedOut, ProviderId, "transport_timeout");
                }

                return NpcAiReply.Failed(NpcAiOutcome.ModelUnavailable, ProviderId, response.ErrorCode);
            }

            NpcAiReply reply;
            NpcReplyValidation.TryValidate(
                response.RawContent,
                request.NpcId,
                request.AvailableTopicIds,
                ProviderId,
                false,
                out reply);
            return reply;
        }
    }
}
