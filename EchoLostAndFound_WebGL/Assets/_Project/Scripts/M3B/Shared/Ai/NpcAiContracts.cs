using System;
using System.Collections.Generic;

namespace EchoLostAndFound.Shared.Ai
{
    /// <summary>
    /// How a reply was produced. Mock and ExternalModel are mutually exclusive:
    /// a mock reply is always marked synthetic and must never be presented as real
    /// model reasoning (Docs/Architecture.md §9.5).
    /// </summary>
    public enum NpcAiProviderKind
    {
        Mock,
        ExternalModel,
        Fallback
    }

    /// <summary>
    /// Normalized provider outcome. These map one-to-one onto DataSchema §5
    /// fallback_reason values; the provider layer never invents new enum values.
    /// </summary>
    public enum NpcAiOutcome
    {
        Completed,
        TimedOut,
        ModelUnavailable,
        InvalidOutput,
        UnsafeOutput,
        UnknownIntent
    }

    public static class NpcAiFallbackReasons
    {
        public const string ModelUnavailable = "model_unavailable";
        public const string Timeout = "timeout";
        public const string InvalidOutput = "invalid_output";
        public const string UnsafeOutput = "unsafe_output";
        public const string UnknownIntent = "unknown_intent";

        /// <summary>Returns null for Completed, otherwise the DataSchema fallback_reason.</summary>
        public static string ForOutcome(NpcAiOutcome outcome)
        {
            switch (outcome)
            {
                case NpcAiOutcome.Completed: return null;
                case NpcAiOutcome.TimedOut: return Timeout;
                case NpcAiOutcome.ModelUnavailable: return ModelUnavailable;
                case NpcAiOutcome.InvalidOutput: return InvalidOutput;
                case NpcAiOutcome.UnsafeOutput: return UnsafeOutput;
                case NpcAiOutcome.UnknownIntent: return UnknownIntent;
                default: return ModelUnavailable;
            }
        }
    }

    /// <summary>
    /// Input to one non-critical NPC bridge request. Deliberately narrow: the provider
    /// never receives hidden truths, internal NPC state, save IDs or rule commands.
    /// </summary>
    public sealed class NpcAiRequest
    {
        public NpcAiRequest(
            string requestId,
            string npcId,
            string playerInput,
            IReadOnlyList<string> acquiredEvidenceIds,
            IReadOnlyList<string> availableTopicIds,
            int timeoutMilliseconds,
            string contentVersion)
        {
            if (string.IsNullOrWhiteSpace(requestId)) throw new ArgumentException("request_id is required.", nameof(requestId));
            if (string.IsNullOrWhiteSpace(npcId)) throw new ArgumentException("npc_id is required.", nameof(npcId));
            if (timeoutMilliseconds <= 0) throw new ArgumentOutOfRangeException(nameof(timeoutMilliseconds));

            RequestId = requestId;
            NpcId = npcId;
            PlayerInput = playerInput ?? string.Empty;
            AcquiredEvidenceIds = acquiredEvidenceIds ?? Array.Empty<string>();
            AvailableTopicIds = availableTopicIds ?? Array.Empty<string>();
            TimeoutMilliseconds = timeoutMilliseconds;
            ContentVersion = contentVersion;
        }

        public string RequestId { get; }

        public string NpcId { get; }

        public string PlayerInput { get; }

        public IReadOnlyList<string> AcquiredEvidenceIds { get; }

        public IReadOnlyList<string> AvailableTopicIds { get; }

        public int TimeoutMilliseconds { get; }

        public string ContentVersion { get; }
    }

    /// <summary>
    /// Structured NPC reply. Contains only display text and a suggested topic: there is
    /// no field that could grant evidence, set a flag, change relationship or execute a
    /// rule command (DataSchema §5: no rule_commands, no revealed_fact_ids).
    /// </summary>
    public sealed class NpcAiReply
    {
        private NpcAiReply(
            NpcAiOutcome outcome,
            NpcAiProviderKind providerKind,
            string providerId,
            bool isSynthetic,
            string text,
            string suggestedTopicId,
            string fallbackReason,
            string failureDetail)
        {
            Outcome = outcome;
            ProviderKind = providerKind;
            ProviderId = providerId;
            IsSynthetic = isSynthetic;
            Text = text;
            SuggestedTopicId = suggestedTopicId;
            FallbackReason = fallbackReason;
            FailureDetail = failureDetail;
        }

        public NpcAiOutcome Outcome { get; }

        public NpcAiProviderKind ProviderKind { get; }

        public string ProviderId { get; }

        /// <summary>True for rule-based fixtures; must never be displayed as real reasoning.</summary>
        public bool IsSynthetic { get; }

        public string Text { get; }

        public string SuggestedTopicId { get; }

        /// <summary>Null when Outcome == Completed, otherwise a DataSchema fallback_reason.</summary>
        public string FallbackReason { get; }

        /// <summary>Sanitized diagnostic category only; never contains the player's raw text or secrets.</summary>
        public string FailureDetail { get; }

        public bool IsSuccess => Outcome == NpcAiOutcome.Completed && !string.IsNullOrEmpty(Text);

        public static NpcAiReply Completed(string providerId, bool isSynthetic, string text, string suggestedTopicId = null)
        {
            return new NpcAiReply(NpcAiOutcome.Completed, isSynthetic ? NpcAiProviderKind.Mock : NpcAiProviderKind.ExternalModel,
                providerId, isSynthetic, text, suggestedTopicId, null, null);
        }

        public static NpcAiReply Failed(NpcAiOutcome outcome, string providerId, string failureDetail = null)
        {
            if (outcome == NpcAiOutcome.Completed)
                throw new ArgumentException("Failed() requires a non-completed outcome.", nameof(outcome));
            return new NpcAiReply(outcome, NpcAiProviderKind.Fallback, providerId, true, null, null,
                NpcAiFallbackReasons.ForOutcome(outcome), failureDetail);
        }
    }

    /// <summary>
    /// Adapter boundary for NPC reply generation. Implementations: the deterministic
    /// MockProvider in this delivery, and future real-model adapters behind the
    /// backend's LLMProvider (Docs/Architecture.md §9.2). Client modules consume the
    /// interface synchronously so WebGL builds do not depend on background threads.
    /// </summary>
    public interface INpcAiProvider
    {
        NpcAiReply Generate(NpcAiRequest request);
    }
}
