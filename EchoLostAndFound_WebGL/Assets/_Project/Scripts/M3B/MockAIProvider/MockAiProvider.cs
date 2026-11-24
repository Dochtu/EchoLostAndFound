using System;
using System.Collections.Generic;
using EchoLostAndFound.Shared.Ai;
using EchoLostAndFound.Shared.Contracts;
using EchoLostAndFound.Shared.Json;

namespace EchoLostAndFound.MockAi
{
    /// <summary>
    /// Validates the structured reply produced by an AI provider before it can reach the
    /// player. The validator is deliberately deterministic and offline: it is the layer that
    /// guarantees a provider can never grant evidence, emit commands, or pass unsafe text.
    /// </summary>
    public static class NpcReplyValidation
    {
        public const int MaxTextLength = 400;

        private static readonly string[] ForbiddenFragments =
        {
            "系统提示",
            "忽略上面",
            "忽略以上",
            "api key",
            "apikey",
            "sk-"
        };

        /// <summary>
        /// Parses and validates a raw provider payload. Returns true when a usable reply was
        /// produced; when false, <paramref name="reply"/> is a fallback reply whose
        /// <see cref="NpcAiReply.FallbackReason"/> is invalid_output or unsafe_output.
        /// </summary>
        public static bool TryValidate(
            string rawContent,
            string expectedNpcId,
            IReadOnlyList<string> availableTopicIds,
            string providerId,
            bool isSynthetic,
            out NpcAiReply reply)
        {
            reply = null;
            if (string.IsNullOrWhiteSpace(rawContent))
            {
                reply = NpcAiReply.Failed(NpcAiOutcome.InvalidOutput, providerId, "empty_payload");
                return false;
            }

            JsonObject root;
            try
            {
                root = JsonContract.RequireObject(JsonValue.Parse(rawContent), "$");
                JsonContract.RejectUnknownFields(root, "$", "npc_id", "text", "suggested_topic_id");
            }
            catch (JsonDataException ex)
            {
                reply = NpcAiReply.Failed(NpcAiOutcome.InvalidOutput, providerId, "invalid_json: " + ex.JsonPath);
                return false;
            }
            catch (GameContractException ex)
            {
                reply = NpcAiReply.Failed(NpcAiOutcome.InvalidOutput, providerId, "invalid_json: " + ex.Code);
                return false;
            }

            string npcId;
            string text;
            string suggestedTopicId;
            try
            {
                npcId = JsonContract.RequireString(root, "npc_id", "$");
                text = JsonContract.RequireString(root, "text", "$");
                suggestedTopicId = JsonContract.OptionalString(root, "suggested_topic_id", "$");
            }
            catch (JsonDataException ex)
            {
                reply = NpcAiReply.Failed(NpcAiOutcome.InvalidOutput, providerId, "missing_field: " + ex.JsonPath);
                return false;
            }

            if (!string.Equals(npcId, expectedNpcId, StringComparison.Ordinal))
            {
                reply = NpcAiReply.Failed(NpcAiOutcome.InvalidOutput, providerId, "npc_id_mismatch");
                return false;
            }

            if (string.IsNullOrWhiteSpace(text))
            {
                reply = NpcAiReply.Failed(NpcAiOutcome.InvalidOutput, providerId, "empty_text");
                return false;
            }

            if (text.Length > MaxTextLength)
            {
                reply = NpcAiReply.Failed(NpcAiOutcome.InvalidOutput, providerId, "text_too_long");
                return false;
            }

            if (ContainsUnsafeMarkup(text))
            {
                reply = NpcAiReply.Failed(NpcAiOutcome.UnsafeOutput, providerId, "markup_detected");
                return false;
            }

            foreach (var fragment in ForbiddenFragments)
            {
                if (text.IndexOf(fragment, StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    reply = NpcAiReply.Failed(NpcAiOutcome.UnsafeOutput, providerId, "forbidden_fragment");
                    return false;
                }
            }

            if (!string.IsNullOrEmpty(suggestedTopicId) && !Contains(availableTopicIds, suggestedTopicId))
            {
                // A harmless suggestion that the NPC does not actually offer is dropped, not fatal.
                suggestedTopicId = null;
            }

            reply = NpcAiReply.Completed(providerId, isSynthetic, text, suggestedTopicId);
            return true;
        }

        private static bool ContainsUnsafeMarkup(string text)
        {
            return text.IndexOf('<') >= 0 || text.IndexOf('>') >= 0;
        }

        private static bool Contains(IReadOnlyList<string> values, string value)
        {
            if (values == null) return false;
            foreach (var item in values)
            {
                if (string.Equals(item, value, StringComparison.Ordinal)) return true;
            }

            return false;
        }
    }

    /// <summary>
    /// Deterministic, offline AI stand-in. It never calls a network service and never claims
    /// to be a real model: every successful reply is marked IsSynthetic=true and carries
    /// provider id "mock-deterministic". Failure behaviour (timeout / transport error /
    /// validation rejection) is selected by fixture, so tests are reproducible.
    /// </summary>
    public sealed class MockAiProvider : INpcAiProvider
    {
        public const string DefaultProviderId = "mock-deterministic";

        private readonly MockAiScenarioSet scenarios;

        public MockAiProvider(MockAiScenarioSet scenarios, string providerId = null)
        {
            if (scenarios == null) throw new ArgumentNullException(nameof(scenarios));
            this.scenarios = scenarios;
            ProviderId = string.IsNullOrWhiteSpace(providerId) ? scenarios.ProviderId : providerId;
            if (string.IsNullOrWhiteSpace(ProviderId)) throw GameContractException.Validation("mock provider id 不能为空。");
        }

        public string ProviderId { get; }

        public MockAiScenarioSet Scenarios => scenarios;

        public static MockAiProvider FromJson(string json, string providerId = null)
        {
            return new MockAiProvider(MockAiScenarioJson.Parse(json), providerId);
        }

        public NpcAiReply Generate(NpcAiRequest request)
        {
            if (request == null) throw new ArgumentNullException(nameof(request));

            if (!string.Equals(scenarios.ContentVersion, request.ContentVersion, StringComparison.Ordinal))
            {
                return NpcAiReply.Failed(NpcAiOutcome.ModelUnavailable, ProviderId, "content_version_mismatch");
            }

            var scenario = scenarios.FindMatch(request);
            if (scenario == null)
            {
                return NpcAiReply.Failed(NpcAiOutcome.UnknownIntent, ProviderId, "no_fixture_match");
            }

            switch (scenario.Behavior)
            {
                case MockAiBehavior.Timeout:
                    return NpcAiReply.Failed(NpcAiOutcome.TimedOut, ProviderId, "simulated_timeout");
                case MockAiBehavior.TransportError:
                    return NpcAiReply.Failed(NpcAiOutcome.ModelUnavailable, ProviderId, "simulated_transport_error");
                default:
                    break;
            }

            NpcAiReply reply;
            NpcReplyValidation.TryValidate(
                scenario.RawReplyJson,
                request.NpcId,
                request.AvailableTopicIds,
                ProviderId,
                true,
                out reply);
            return reply;
        }
    }
}
