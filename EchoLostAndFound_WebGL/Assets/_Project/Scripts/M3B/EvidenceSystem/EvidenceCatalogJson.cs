using System;
using System.Collections.Generic;
using EchoLostAndFound.Shared.Contracts;
using EchoLostAndFound.Shared.Json;

namespace EchoLostAndFound.Evidence
{
    /// <summary>
    /// Loads the approved evidence content file (M3B/EvidenceSystem/Content/ch01_evidence.json)
    /// into an immutable <see cref="EvidenceCatalog"/>. The schema is strict: unknown
    /// members, wrong JSON kinds and unknown enum values are rejected with the offending
    /// JSON path, matching DataSchema §1 "未知字段一律拒绝".
    /// </summary>
    public static class EvidenceCatalogJson
    {
        private static readonly Func<string, EvidenceSourceKind?> SourceKindResolver = raw =>
            EvidenceSourceKinds.TryParse(raw, out var kind) ? (EvidenceSourceKind?)kind : null;

        public static EvidenceCatalog Parse(string json)
        {
            if (json == null) throw new JsonDataException("Evidence catalog JSON is null.", "$");
            var root = JsonContract.RequireObject(SafeParse(json), "$");
            JsonContract.RejectUnknownFields(root, "$", "content_version", "evidence");

            var contentVersion = JsonContract.RequireString(root, "content_version", "$");
            var evidenceArray = JsonContract.RequireArrayMember(root, "evidence", "$");
            if (evidenceArray.Count == 0)
                throw new JsonDataException("The evidence catalog must contain at least one evidence card.", "$.evidence");

            var definitions = new List<EvidenceDefinition>(evidenceArray.Count);
            for (var i = 0; i < evidenceArray.Count; i++)
            {
                definitions.Add(ReadEvidence(JsonContract.RequireObject(evidenceArray[i], JsonContract.IndexPath("$.evidence", i)),
                    JsonContract.IndexPath("$.evidence", i), contentVersion));
            }

            try
            {
                return new EvidenceCatalog(contentVersion, definitions);
            }
            catch (GameContractException exception)
            {
                throw new JsonDataException(exception.Message, "$.evidence", exception.Code);
            }
        }

        private static EvidenceDefinition ReadEvidence(JsonObject obj, string path, string contentVersion)
        {
            JsonContract.RejectUnknownFields(
                obj,
                path,
                "evidence_id",
                "title",
                "source_kind",
                "source_id",
                "source_label",
                "area_id",
                "item_id",
                "provenance_root_id",
                "composed_from_parts",
                "fixed_text",
                "proof_limits",
                "media_refs",
                "fields");

            var evidenceId = JsonContract.RequireString(obj, "evidence_id", path);
            var title = JsonContract.RequireString(obj, "title", path);
            var sourceKind = JsonContract.ParseEnum(
                JsonContract.RequireString(obj, "source_kind", path),
                JsonContract.MemberPath(path, "source_kind"),
                SourceKindResolver,
                EvidenceSourceKinds.AllowedValues);
            var sourceId = JsonContract.RequireString(obj, "source_id", path);
            var sourceLabel = JsonContract.OptionalString(obj, "source_label", path);
            var areaId = JsonContract.RequireString(obj, "area_id", path);
            var itemId = JsonContract.OptionalString(obj, "item_id", path);
            var provenanceRootId = JsonContract.OptionalString(obj, "provenance_root_id", path);
            var composedFromParts = JsonContract.RequireBool(obj, "composed_from_parts", path);
            var fixedText = JsonContract.RequireString(obj, "fixed_text", path);
            var proofLimits = JsonContract.OptionalStringArray(obj, "proof_limits", path);
            var mediaRefs = JsonContract.OptionalStringArray(obj, "media_refs", path);

            var fieldArray = JsonContract.RequireArrayMember(obj, "fields", path);
            if (fieldArray.Count == 0)
                throw new JsonDataException("An evidence card must declare at least one field.", JsonContract.MemberPath(path, "fields"));

            var fields = new List<EvidenceFieldDefinition>(fieldArray.Count);
            for (var i = 0; i < fieldArray.Count; i++)
            {
                fields.Add(ReadField(
                    JsonContract.RequireObject(fieldArray[i], JsonContract.IndexPath(JsonContract.MemberPath(path, "fields"), i)),
                    JsonContract.IndexPath(JsonContract.MemberPath(path, "fields"), i)));
            }

            if (composedFromParts)
            {
                foreach (var field in fields)
                {
                    if (field.PartId == null)
                        throw new JsonDataException("composed_from_parts evidence requires part_id on every field.", path + ".fields");
                }
            }

            return new EvidenceDefinition(
                evidenceId,
                title,
                sourceKind,
                sourceId,
                sourceLabel,
                areaId,
                itemId,
                provenanceRootId,
                fixedText,
                proofLimits,
                mediaRefs,
                contentVersion,
                composedFromParts,
                fields);
        }

        private static EvidenceFieldDefinition ReadField(JsonObject obj, string path)
        {
            JsonContract.RejectUnknownFields(obj, path, "field_id", "item_id", "part_id", "label", "display_text", "media_refs");
            return new EvidenceFieldDefinition(
                JsonContract.RequireString(obj, "field_id", path),
                JsonContract.OptionalString(obj, "item_id", path),
                JsonContract.OptionalString(obj, "part_id", path),
                JsonContract.RequireString(obj, "label", path),
                JsonContract.RequireString(obj, "display_text", path),
                JsonContract.OptionalStringArray(obj, "media_refs", path));
        }

        private static JsonValue SafeParse(string json)
        {
            try
            {
                return JsonValue.Parse(json);
            }
            catch (JsonDataException)
            {
                throw;
            }
            catch (Exception exception)
            {
                throw new JsonDataException("Evidence catalog could not be parsed: " + exception.Message, "$");
            }
        }
    }
}
