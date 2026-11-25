using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Text.RegularExpressions;
using EchoLostAndFound.Shared.Contracts;

namespace EchoLostAndFound.Evidence
{
    /// <summary>
    /// DataSchema §1 source_kind values. Evidence definition data controls the value;
    /// this module never invents a new kind without a content approval.
    /// </summary>
    public enum EvidenceSourceKind
    {
        Physical,
        Document,
        Audio,
        Testimony
    }

    public static class EvidenceSourceKinds
    {
        public const string Physical = "physical";
        public const string Document = "document";
        public const string Audio = "audio";
        public const string Testimony = "testimony";

        public static string ToContractValue(EvidenceSourceKind kind)
        {
            switch (kind)
            {
                case EvidenceSourceKind.Physical: return Physical;
                case EvidenceSourceKind.Document: return Document;
                case EvidenceSourceKind.Audio: return Audio;
                case EvidenceSourceKind.Testimony: return Testimony;
                default: throw new ArgumentOutOfRangeException(nameof(kind));
            }
        }

        public static bool TryParse(string raw, out EvidenceSourceKind kind)
        {
            switch (raw)
            {
                case Physical: kind = EvidenceSourceKind.Physical; return true;
                case Document: kind = EvidenceSourceKind.Document; return true;
                case Audio: kind = EvidenceSourceKind.Audio; return true;
                case Testimony: kind = EvidenceSourceKind.Testimony; return true;
                default: kind = default; return false;
            }
        }

        public static string AllowedValues => "physical, document, audio, testimony";
    }

    /// <summary>
    /// One addressable observation inside an evidence card (DataSchema §1.1 registry).
    /// Documents have no watch item/part; item_id and part_id are null there.
    /// </summary>
    public sealed class EvidenceFieldDefinition
    {
        public EvidenceFieldDefinition(
            string fieldId,
            string itemId,
            string partId,
            string label,
            string displayText,
            IReadOnlyList<string> mediaRefs)
        {
            if (string.IsNullOrWhiteSpace(fieldId)) throw new ArgumentException("field_id is required.", nameof(fieldId));
            if (string.IsNullOrWhiteSpace(label)) throw new ArgumentException("field label is required.", nameof(label));
            if (string.IsNullOrWhiteSpace(displayText)) throw new ArgumentException("field display_text is required.", nameof(displayText));
            FieldId = fieldId;
            ItemId = string.IsNullOrEmpty(itemId) ? null : itemId;
            PartId = string.IsNullOrEmpty(partId) ? null : partId;
            Label = label;
            DisplayText = displayText;
            MediaRefs = mediaRefs ?? Array.Empty<string>();
        }

        public string FieldId { get; }

        public string ItemId { get; }

        public string PartId { get; }

        public string Label { get; }

        public string DisplayText { get; }

        public IReadOnlyList<string> MediaRefs { get; }
    }

    /// <summary>
    /// Immutable approved content definition for one evidence card. Observation and
    /// acquisition state live in <see cref="EvidenceRegistry"/>; this type is catalog data.
    /// </summary>
    public sealed class EvidenceDefinition
    {
        private readonly ReadOnlyCollection<EvidenceFieldDefinition> fields;

        public EvidenceDefinition(
            string evidenceId,
            string title,
            EvidenceSourceKind sourceKind,
            string sourceId,
            string sourceLabel,
            string areaId,
            string itemId,
            string provenanceRootId,
            string fixedText,
            IReadOnlyList<string> proofLimits,
            IReadOnlyList<string> mediaRefs,
            string contentVersion,
            bool composedFromParts,
            IReadOnlyList<EvidenceFieldDefinition> fields)
        {
            if (!EvidenceIdRules.IsWellFormed(evidenceId))
                throw GameContractException.Validation("evidence_id '" + evidenceId + "' 不符合 E01 形式。");
            if (string.IsNullOrWhiteSpace(title)) throw GameContractException.Validation("证据 " + evidenceId + " 缺少 title。");
            if (string.IsNullOrWhiteSpace(sourceId)) throw GameContractException.Validation("证据 " + evidenceId + " 缺少 source_id。");
            if (string.IsNullOrWhiteSpace(fixedText)) throw GameContractException.Validation("证据 " + evidenceId + " 缺少 fixed_text。");
            if (string.IsNullOrWhiteSpace(contentVersion)) throw GameContractException.Validation("证据 " + evidenceId + " 缺少 content_version。");
            if (fields == null || fields.Count == 0)
                throw GameContractException.Validation("证据 " + evidenceId + " 至少需要一个 field。");

            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var field in fields)
            {
                if (!seen.Add(field.FieldId))
                    throw GameContractException.Validation("证据 " + evidenceId + " 存在重复 field_id '" + field.FieldId + "'。");
            }

            EvidenceId = evidenceId;
            Title = title;
            SourceKind = sourceKind;
            SourceId = sourceId;
            SourceLabel = sourceLabel ?? string.Empty;
            AreaId = areaId;
            ItemId = string.IsNullOrEmpty(itemId) ? null : itemId;
            ProvenanceRootId = provenanceRootId;
            FixedText = fixedText;
            ProofLimits = proofLimits ?? Array.Empty<string>();
            MediaRefs = mediaRefs ?? Array.Empty<string>();
            ContentVersion = contentVersion;
            ComposedFromParts = composedFromParts;
            this.fields = new ReadOnlyCollection<EvidenceFieldDefinition>(new List<EvidenceFieldDefinition>(fields));
        }

        public string EvidenceId { get; }

        public string Title { get; }

        public EvidenceSourceKind SourceKind { get; }

        public string SourceId { get; }

        public string SourceLabel { get; }

        public string AreaId { get; }

        public string ItemId { get; }

        public string ProvenanceRootId { get; }

        public string FixedText { get; }

        public IReadOnlyList<string> ProofLimits { get; }

        public IReadOnlyList<string> MediaRefs { get; }

        public string ContentVersion { get; }

        /// <summary>True for E01: the card is composed only after every part/field is observed.</summary>
        public bool ComposedFromParts { get; }

        public IReadOnlyList<EvidenceFieldDefinition> Fields => fields;

        public IReadOnlyList<string> RequiredFieldIds
        {
            get
            {
                var ids = new List<string>(fields.Count);
                foreach (var field in fields) ids.Add(field.FieldId);
                return ids;
            }
        }

        public bool TryGetField(string fieldId, out EvidenceFieldDefinition field)
        {
            foreach (var candidate in fields)
            {
                if (string.Equals(candidate.FieldId, fieldId, StringComparison.Ordinal))
                {
                    field = candidate;
                    return true;
                }
            }

            field = null;
            return false;
        }
    }

    public static class EvidenceIdRules
    {
        private static readonly Regex Pattern = new Regex("^E[0-9]{2}$", RegexOptions.CultureInvariant | RegexOptions.Compiled);

        public static bool IsWellFormed(string evidenceId)
        {
            return !string.IsNullOrEmpty(evidenceId) && Pattern.IsMatch(evidenceId);
        }
    }

    /// <summary>
    /// Static content catalog (DataSchema §1.1 field registry). Lookups are immutable
    /// after construction; this is the only source of legal evidence and field IDs.
    /// </summary>
    public sealed class EvidenceCatalog
    {
        private readonly Dictionary<string, EvidenceDefinition> byId;
        private readonly Dictionary<string, string> evidenceByFieldId;

        public EvidenceCatalog(string contentVersion, IReadOnlyList<EvidenceDefinition> definitions)
        {
            if (string.IsNullOrWhiteSpace(contentVersion))
                throw GameContractException.Validation("content_version 不能为空。");
            if (definitions == null || definitions.Count == 0)
                throw GameContractException.Validation("证据目录不能为空。");

            byId = new Dictionary<string, EvidenceDefinition>(StringComparer.Ordinal);
            evidenceByFieldId = new Dictionary<string, string>(StringComparer.Ordinal);
            var ordered = new List<EvidenceDefinition>(definitions.Count);
            foreach (var definition in definitions)
            {
                if (definition == null) throw GameContractException.Validation("证据目录中存在 null 定义。");
                if (!string.Equals(definition.ContentVersion, contentVersion, StringComparison.Ordinal))
                    throw GameContractException.Validation("证据 " + definition.EvidenceId + " 的 content_version 与目录不一致。");
                if (byId.ContainsKey(definition.EvidenceId))
                    throw GameContractException.Validation("重复的 evidence_id '" + definition.EvidenceId + "'。");

                byId.Add(definition.EvidenceId, definition);
                ordered.Add(definition);
                foreach (var field in definition.Fields)
                {
                    if (evidenceByFieldId.ContainsKey(field.FieldId))
                        throw GameContractException.Validation("field_id '" + field.FieldId + "' 同时登记在两张证据上。");
                    evidenceByFieldId.Add(field.FieldId, definition.EvidenceId);
                }
            }

            ContentVersion = contentVersion;
            Definitions = new ReadOnlyCollection<EvidenceDefinition>(ordered);
        }

        public string ContentVersion { get; }

        public IReadOnlyList<EvidenceDefinition> Definitions { get; }

        public int Count => Definitions.Count;

        public bool Contains(string evidenceId)
        {
            return evidenceId != null && byId.ContainsKey(evidenceId);
        }

        public EvidenceDefinition Get(string evidenceId)
        {
            if (!EvidenceIdRules.IsWellFormed(evidenceId))
                throw GameContractException.InvalidRequest("evidence_id '" + evidenceId + "' 格式无效，应为 E01 形式。");
            if (!byId.TryGetValue(evidenceId, out var definition))
                throw GameContractException.NotFound("证据 '" + evidenceId + "' 不在已批准内容目录中。");
            return definition;
        }

        public bool TryGet(string evidenceId, out EvidenceDefinition definition)
        {
            definition = null;
            return evidenceId != null && byId.TryGetValue(evidenceId, out definition);
        }

        public bool TryFindEvidenceForField(string fieldId, out EvidenceDefinition definition, out EvidenceFieldDefinition field)
        {
            definition = null;
            field = null;
            if (fieldId == null || !evidenceByFieldId.TryGetValue(fieldId, out var evidenceId)) return false;
            definition = byId[evidenceId];
            return definition.TryGetField(fieldId, out field);
        }
    }
}
