using System;
using System.Collections.Generic;
using EchoLostAndFound.Shared.Contracts;
using EchoLostAndFound.Shared.Json;

namespace EchoLostAndFound.Dialogue
{
    /// <summary>
    /// Strict loader for approved dialogue content (M3B/DialogueSystem/Content/ch01_dialogue.json).
    /// Nothing here invents story text: every node/disclosure carries an approved fixed line
    /// and a content_ref; verification disclosures carry no line at all.
    /// </summary>
    public static class DialogueCatalogJson
    {
        private static readonly Func<string, DialogueOptionKind?> OptionKindResolver = raw =>
        {
            switch (raw)
            {
                case "topic": return DialogueOptionKind.Topic;
                case "end": return DialogueOptionKind.End;
                default: return null;
            }
        };

        private static readonly Func<string, DialogueDisclosureKind?> DisclosureKindResolver = raw =>
        {
            switch (raw)
            {
                case "testimony": return DialogueDisclosureKind.Testimony;
                case "recognition": return DialogueDisclosureKind.Recognition;
                case "verification": return DialogueDisclosureKind.Verification;
                default: return null;
            }
        };

        public static DialogueCatalog Parse(string json)
        {
            if (json == null) throw new JsonDataException("Dialogue catalog JSON is null.", "$");
            var root = JsonContract.RequireObject(JsonValue.Parse(json), "$");
            JsonContract.RejectUnknownFields(root, "$", "content_version", "npcs");

            var contentVersion = JsonContract.RequireString(root, "content_version", "$");
            var npcArray = JsonContract.RequireArrayMember(root, "npcs", "$");
            if (npcArray.Count == 0)
                throw new JsonDataException("The dialogue catalog must contain at least one NPC.", "$.npcs");

            var npcs = new List<NpcDialogueDefinition>(npcArray.Count);
            for (var i = 0; i < npcArray.Count; i++)
            {
                var path = JsonContract.IndexPath("$.npcs", i);
                npcs.Add(ReadNpc(JsonContract.RequireObject(npcArray[i], path), path));
            }

            try
            {
                return new DialogueCatalog(contentVersion, npcs);
            }
            catch (GameContractException exception)
            {
                throw new JsonDataException(exception.Message, "$.npcs", exception.Code);
            }
        }

        private static NpcDialogueDefinition ReadNpc(JsonObject obj, string path)
        {
            JsonContract.RejectUnknownFields(
                obj,
                path,
                "npc_id",
                "display_name",
                "opening_node_id",
                "allowed_evidence_ids",
                "nodes",
                "disclosures");

            var npcId = JsonContract.RequireString(obj, "npc_id", path);
            var displayName = JsonContract.RequireString(obj, "display_name", path);
            var openingNodeId = JsonContract.RequireString(obj, "opening_node_id", path);
            var allowedEvidenceIds = JsonContract.RequireStringArray(obj, "allowed_evidence_ids", path);

            var nodeArray = JsonContract.RequireArrayMember(obj, "nodes", path);
            var nodes = new List<DialogueNodeDefinition>(nodeArray.Count);
            for (var i = 0; i < nodeArray.Count; i++)
            {
                var nodePath = JsonContract.IndexPath(JsonContract.MemberPath(path, "nodes"), i);
                nodes.Add(ReadNode(JsonContract.RequireObject(nodeArray[i], nodePath), nodePath));
            }

            var disclosureArray = JsonContract.RequireArrayMember(obj, "disclosures", path);
            var disclosures = new List<DialogueDisclosureDefinition>(disclosureArray.Count);
            for (var i = 0; i < disclosureArray.Count; i++)
            {
                var disclosurePath = JsonContract.IndexPath(JsonContract.MemberPath(path, "disclosures"), i);
                disclosures.Add(ReadDisclosure(
                    JsonContract.RequireObject(disclosureArray[i], disclosurePath),
                    disclosurePath,
                    npcId));
            }

            return new NpcDialogueDefinition(npcId, displayName, openingNodeId, allowedEvidenceIds, nodes, disclosures);
        }

        private static DialogueNodeDefinition ReadNode(JsonObject obj, string path)
        {
            JsonContract.RejectUnknownFields(obj, path, "node_id", "content_ref", "text", "options");
            var nodeId = JsonContract.RequireString(obj, "node_id", path);
            var contentRef = JsonContract.RequireString(obj, "content_ref", path);
            var text = JsonContract.RequireString(obj, "text", path);

            var optionArray = JsonContract.RequireArrayMember(obj, "options", path);
            var options = new List<DialogueOptionDefinition>(optionArray.Count);
            for (var i = 0; i < optionArray.Count; i++)
            {
                var optionPath = JsonContract.IndexPath(JsonContract.MemberPath(path, "options"), i);
                options.Add(ReadOption(JsonContract.RequireObject(optionArray[i], optionPath), optionPath));
            }

            return new DialogueNodeDefinition(nodeId, contentRef, text, options);
        }

        private static DialogueOptionDefinition ReadOption(JsonObject obj, string path)
        {
            JsonContract.RejectUnknownFields(obj, path, "option_id", "label", "kind", "target_node_id", "condition");
            var optionId = JsonContract.RequireString(obj, "option_id", path);
            var label = JsonContract.RequireString(obj, "label", path);
            var kind = JsonContract.ParseEnum(
                JsonContract.RequireString(obj, "kind", path),
                JsonContract.MemberPath(path, "kind"),
                OptionKindResolver,
                "topic, end");
            var targetNodeId = JsonContract.OptionalString(obj, "target_node_id", path);
            var condition = ReadCondition(obj["condition"], JsonContract.MemberPath(path, "condition"));
            return new DialogueOptionDefinition(optionId, label, kind, targetNodeId, condition);
        }

        private static DialogueCondition ReadCondition(JsonValue value, string path)
        {
            if (value == null || value is JsonNull) return DialogueCondition.Always;
            var obj = JsonContract.RequireObject(value, path);
            JsonContract.RejectUnknownFields(obj, path, "requires_evidence_ids", "requires_any_evidence_ids", "requires_observed_field_ids", "requires_disclosure_ids");
            return new DialogueCondition(
                JsonContract.OptionalStringArray(obj, "requires_evidence_ids", path),
                JsonContract.OptionalStringArray(obj, "requires_any_evidence_ids", path),
                JsonContract.OptionalStringArray(obj, "requires_observed_field_ids", path),
                JsonContract.OptionalStringArray(obj, "requires_disclosure_ids", path));
        }

        private static DialogueDisclosureDefinition ReadDisclosure(JsonObject obj, string path, string npcId)
        {
            JsonContract.RejectUnknownFields(
                obj,
                path,
                "disclosure_id",
                "kind",
                "required_evidence_ids",
                "requires_observed_field_ids",
                "content_ref",
                "text");

            var disclosureId = JsonContract.RequireString(obj, "disclosure_id", path);
            var kind = JsonContract.ParseEnum(
                JsonContract.RequireString(obj, "kind", path),
                JsonContract.MemberPath(path, "kind"),
                DisclosureKindResolver,
                "testimony, recognition, verification");
            var requiredEvidenceIds = JsonContract.RequireStringArray(obj, "required_evidence_ids", path);
            var requiredFieldIds = JsonContract.OptionalStringArray(obj, "requires_observed_field_ids", path);
            var contentRef = JsonContract.OptionalString(obj, "content_ref", path);
            var text = JsonContract.OptionalString(obj, "text", path);
            return new DialogueDisclosureDefinition(
                disclosureId,
                npcId,
                kind,
                requiredEvidenceIds,
                requiredFieldIds,
                contentRef,
                text);
        }
    }
}
