using System;
using System.Collections.Generic;

namespace EchoLostAndFound.Evidence
{
    /// <summary>
    /// Deterministic acquisition state for one card. UI must never infer "全部观察即已获得";
    /// it reads this value, which the registry derives from the same rules the tests assert.
    /// </summary>
    public enum EvidenceStatus
    {
        /// <summary>No field of the card has been observed.</summary>
        NotObserved,

        /// <summary>Some, but not all, required fields have been observed.</summary>
        PartiallyObserved,

        /// <summary>Every required field is observed; the card is ready to be acquired.</summary>
        ReadyToAcquire,

        /// <summary>The card is part of the player's evidence records.</summary>
        Acquired
    }

    /// <summary>One observed field, as shown in the journal detail view.</summary>
    public sealed class ObservedFieldView
    {
        public ObservedFieldView(
            string evidenceId,
            string fieldId,
            string itemId,
            string partId,
            string label,
            string displayText,
            IReadOnlyList<string> mediaRefs)
        {
            EvidenceId = evidenceId;
            FieldId = fieldId;
            ItemId = itemId;
            PartId = partId;
            Label = label;
            DisplayText = displayText;
            MediaRefs = mediaRefs ?? Array.Empty<string>();
        }

        public string EvidenceId { get; }

        public string FieldId { get; }

        public string ItemId { get; }

        public string PartId { get; }

        public string Label { get; }

        public string DisplayText { get; }

        public IReadOnlyList<string> MediaRefs { get; }
    }

    /// <summary>
    /// Player-facing evidence record (DataSchema PlayerStateView.visible_evidence_records).
    /// It contains only content the player has already observed: the fixed text is the
    /// complete approved card, the field list is limited to observed fields.
    /// </summary>
    public sealed class VisibleEvidenceRecord
    {
        public VisibleEvidenceRecord(
            string evidenceId,
            string title,
            string sourceKind,
            string sourceId,
            string sourceLabel,
            string areaId,
            string itemId,
            string provenanceRootId,
            string fixedText,
            IReadOnlyList<string> proofLimits,
            IReadOnlyList<string> mediaRefs,
            IReadOnlyList<string> observedFieldIds,
            string contentVersion)
        {
            EvidenceId = evidenceId;
            Title = title;
            SourceKind = sourceKind;
            SourceId = sourceId;
            SourceLabel = sourceLabel;
            AreaId = areaId;
            ItemId = itemId;
            ProvenanceRootId = provenanceRootId;
            FixedText = fixedText;
            ProofLimits = proofLimits ?? Array.Empty<string>();
            MediaRefs = mediaRefs ?? Array.Empty<string>();
            ObservedFieldIds = observedFieldIds ?? Array.Empty<string>();
            ContentVersion = contentVersion;
        }

        public string EvidenceId { get; }

        public string Title { get; }

        public string SourceKind { get; }

        public string SourceId { get; }

        public string SourceLabel { get; }

        public string AreaId { get; }

        public string ItemId { get; }

        public string ProvenanceRootId { get; }

        public string FixedText { get; }

        public IReadOnlyList<string> ProofLimits { get; }

        public IReadOnlyList<string> MediaRefs { get; }

        public IReadOnlyList<string> ObservedFieldIds { get; }

        public string ContentVersion { get; }
    }
}
