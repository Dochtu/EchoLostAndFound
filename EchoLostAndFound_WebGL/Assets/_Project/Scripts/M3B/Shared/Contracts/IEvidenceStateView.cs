using System;

namespace EchoLostAndFound.Shared.Contracts
{
    /// <summary>
    /// Opaque identifier source. The backend issues UUIDs for event_id, conversation_id,
    /// turn_id and similar opaque IDs (DataSchema §1); tests inject a deterministic
    /// implementation so assertion output is stable and reviewable.
    /// </summary>
    public interface IIdGenerator
    {
        string CreateId();
    }

    public sealed class GuidIdGenerator : IIdGenerator
    {
        public static readonly GuidIdGenerator Instance = new GuidIdGenerator();

        public string CreateId()
        {
            return Guid.NewGuid().ToString("D");
        }
    }

    /// <summary>
    /// Read-only view of the player's evidence state, as required by the dialogue
    /// module for conditional branches. Implemented by EvidenceSystem's registry;
    /// defined here so DialogueSystem and MockAIProvider do not depend on the
    /// evidence assembly (keeps the module graph acyclic).
    /// </summary>
    public interface IEvidenceStateView
    {
        /// <summary>True when the evidence card has been registered.</summary>
        bool HasEvidence(string evidenceId);

        /// <summary>True when every required field of the evidence has been observed.</summary>
        bool IsComplete(string evidenceId);

        /// <summary>Observed field IDs in observation order; empty when unknown or unobserved.</summary>
        System.Collections.Generic.IReadOnlyList<string> GetObservedFieldIds(string evidenceId);

        /// <summary>True when the field is observed. Unknown fields return false.</summary>
        bool IsFieldObserved(string fieldId);

        /// <summary>Registered evidence IDs in acquisition order (used to build AI context).</summary>
        System.Collections.Generic.IReadOnlyList<string> AcquiredEvidenceIds { get; }
    }
}
