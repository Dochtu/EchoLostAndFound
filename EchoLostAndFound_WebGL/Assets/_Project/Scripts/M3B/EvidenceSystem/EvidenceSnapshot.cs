using System;
using System.Collections.Generic;
using EchoLostAndFound.Shared.Contracts;
using EchoLostAndFound.Shared.Json;

namespace EchoLostAndFound.Evidence
{
    /// <summary>
    /// Persisted evidence progress (DataSchema PlayerStateView: observed_fields,
    /// visible_evidence_records). The snapshot stores IDs only; text always comes from
    /// the approved catalog, so save data can never smuggle in unapproved content.
    /// </summary>
    public sealed class EvidenceSnapshot
    {
        private const string SchemaVersion = "1";

        public EvidenceSnapshot(
            string contentVersion,
            IReadOnlyList<string> observedFieldIds,
            IReadOnlyList<string> acquiredEvidenceIds)
        {
            ContentVersion = contentVersion;
            ObservedFieldIds = observedFieldIds ?? Array.Empty<string>();
            AcquiredEvidenceIds = acquiredEvidenceIds ?? Array.Empty<string>();
        }

        public string ContentVersion { get; }

        public IReadOnlyList<string> ObservedFieldIds { get; }

        public IReadOnlyList<string> AcquiredEvidenceIds { get; }

        /// <summary>Decodes the snapshot shape. Semantic validation needs a catalog; see <see cref="Validate"/>.</summary>
        public static EvidenceSnapshot Parse(string json)
        {
            if (json == null) throw new JsonDataException("Evidence snapshot JSON is null.", "$");
            var root = JsonContract.RequireObject(JsonValue.Parse(json), "$");
            JsonContract.RejectUnknownFields(root, "$", "schema_version", "content_version", "observed_field_ids", "acquired_evidence_ids");

            var schemaVersion = JsonContract.OptionalString(root, "schema_version", "$");
            if (schemaVersion != null && !string.Equals(schemaVersion, SchemaVersion, StringComparison.Ordinal))
                throw GameContractException.SaveIncompatible("证据存档 schema_version '" + schemaVersion + "' 不受支持。");

            return new EvidenceSnapshot(
                JsonContract.RequireString(root, "content_version", "$"),
                JsonContract.OptionalStringArray(root, "observed_field_ids", "$"),
                JsonContract.OptionalStringArray(root, "acquired_evidence_ids", "$"));
        }

        public static EvidenceSnapshot ParseAndValidate(EvidenceCatalog catalog, string json)
        {
            var snapshot = Parse(json);
            snapshot.Validate(catalog);
            return snapshot;
        }

        /// <summary>
        /// Rejects content-version drift, unknown IDs, duplicate IDs and an acquired card
        /// whose fields are not all observed (corrupt save). Throws GameContractException
        /// with the DataSchema save error codes.
        /// </summary>
        public void Validate(EvidenceCatalog catalog)
        {
            if (catalog == null) throw new ArgumentNullException(nameof(catalog));
            if (!string.Equals(ContentVersion, catalog.ContentVersion, StringComparison.Ordinal))
            {
                throw GameContractException.SaveIncompatible(
                    "证据存档 content_version '" + ContentVersion + "' 与当前内容 '" + catalog.ContentVersion + "' 不一致。");
            }

            var observed = new HashSet<string>(StringComparer.Ordinal);
            for (var i = 0; i < ObservedFieldIds.Count; i++)
            {
                var fieldId = ObservedFieldIds[i];
                if (!observed.Add(fieldId))
                    throw GameContractException.SaveCorrupt("证据存档包含重复的 observed_field_id '" + fieldId + "'。");
                if (!catalog.TryFindEvidenceForField(fieldId, out _, out _))
                    throw GameContractException.SaveCorrupt("证据存档包含未知 observed_field_id '" + fieldId + "'。");
            }

            var acquired = new HashSet<string>(StringComparer.Ordinal);
            for (var i = 0; i < AcquiredEvidenceIds.Count; i++)
            {
                var evidenceId = AcquiredEvidenceIds[i];
                if (!acquired.Add(evidenceId))
                    throw GameContractException.SaveCorrupt("证据存档包含重复的 acquired_evidence_id '" + evidenceId + "'。");
                if (!catalog.TryGet(evidenceId, out var definition))
                    throw GameContractException.SaveCorrupt("证据存档包含未知 acquired_evidence_id '" + evidenceId + "'。");

                foreach (var required in definition.RequiredFieldIds)
                {
                    if (!observed.Contains(required))
                    {
                        throw GameContractException.SaveCorrupt(
                            "证据存档中 " + evidenceId + " 已获取，但缺少已观察字段 '" + required + "'。");
                    }
                }
            }
        }

        public string ToJson(bool pretty = true)
        {
            var root = new JsonObject();
            root.Add("schema_version", SchemaVersion);
            root.Add("content_version", ContentVersion);
            root.AddStringArray("observed_field_ids", ObservedFieldIds);
            root.AddStringArray("acquired_evidence_ids", AcquiredEvidenceIds);
            return JsonWriter.Serialize(root, pretty);
        }
    }
}
