using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using EchoLostAndFound.Shared.Contracts;

namespace EchoLostAndFound.Dialogue
{
    /// <summary>DataSchema §5 conversation session states. Cancelled is reserved for the server flow.</summary>
    public enum DialogueSessionStatus
    {
        Open,
        Closed,
        Cancelled,
        Expired
    }

    public enum DialogueOptionKind
    {
        /// <summary>Moves the conversation to a fixed dialogue node.</summary>
        Topic,

        /// <summary>Ends the conversation; the session becomes Closed.</summary>
        End
    }

    public enum DialogueDisclosureKind
    {
        /// <summary>A D / B disclosure with an approved fixed line.</summary>
        Testimony,

        /// <summary>Recognition line (e.g. the engraving) that is not a D and grants no knowledge.</summary>
        Recognition,

        /// <summary>Verification-only disclosure: the contract returns no fixed segments.</summary>
        Verification
    }

    /// <summary>One fixed, approved dialogue segment (DataSchema §5 fixed_segments entry).</summary>
    public sealed class DialogueSegment
    {
        public DialogueSegment(string contentRef, string text)
        {
            ContentRef = contentRef;
            Text = text;
        }

        public string ContentRef { get; }

        public string Text { get; }
    }

    /// <summary>
    /// Deterministic availability rule for an option or a disclosure. Conditions only
    /// read state (never write it) and never consult AI output.
    /// </summary>
    public sealed class DialogueCondition
    {
        public static readonly DialogueCondition Always = new DialogueCondition(
            Array.Empty<string>(),
            Array.Empty<string>(),
            Array.Empty<string>(),
            Array.Empty<string>());

        public DialogueCondition(
            IReadOnlyList<string> requiresEvidenceIds,
            IReadOnlyList<string> requiresAnyEvidenceIds,
            IReadOnlyList<string> requiresObservedFieldIds,
            IReadOnlyList<string> requiresDisclosureIds)
        {
            RequiresEvidenceIds = requiresEvidenceIds ?? Array.Empty<string>();
            RequiresAnyEvidenceIds = requiresAnyEvidenceIds ?? Array.Empty<string>();
            RequiresObservedFieldIds = requiresObservedFieldIds ?? Array.Empty<string>();
            RequiresDisclosureIds = requiresDisclosureIds ?? Array.Empty<string>();
        }

        public IReadOnlyList<string> RequiresEvidenceIds { get; }

        /// <summary>Satisfied when at least one of these evidence IDs is present.</summary>
        public IReadOnlyList<string> RequiresAnyEvidenceIds { get; }

        public IReadOnlyList<string> RequiresObservedFieldIds { get; }

        public IReadOnlyList<string> RequiresDisclosureIds { get; }

        public bool IsSatisfied(Shared.Contracts.IEvidenceStateView evidence, Func<string, bool> disclosureSeen)
        {
            if (evidence == null) throw new ArgumentNullException(nameof(evidence));
            foreach (var evidenceId in RequiresEvidenceIds)
            {
                if (!evidence.HasEvidence(evidenceId)) return false;
            }

            if (RequiresAnyEvidenceIds.Count > 0)
            {
                var any = false;
                foreach (var evidenceId in RequiresAnyEvidenceIds)
                {
                    if (evidence.HasEvidence(evidenceId))
                    {
                        any = true;
                        break;
                    }
                }

                if (!any) return false;
            }

            foreach (var fieldId in RequiresObservedFieldIds)
            {
                if (!evidence.IsFieldObserved(fieldId)) return false;
            }

            if (disclosureSeen != null)
            {
                foreach (var disclosureId in RequiresDisclosureIds)
                {
                    if (!disclosureSeen(disclosureId)) return false;
                }
            }
            else if (RequiresDisclosureIds.Count > 0)
            {
                return false;
            }

            return true;
        }
    }

    public sealed class DialogueOptionDefinition
    {
        public DialogueOptionDefinition(
            string optionId,
            string label,
            DialogueOptionKind kind,
            string targetNodeId,
            DialogueCondition condition)
        {
            if (string.IsNullOrWhiteSpace(optionId)) throw GameContractException.Validation("option_id 不能为空。");
            if (string.IsNullOrWhiteSpace(label)) throw GameContractException.Validation("选项 " + optionId + " 缺少 label。");
            if (kind == DialogueOptionKind.Topic && string.IsNullOrWhiteSpace(targetNodeId))
                throw GameContractException.Validation("topic 选项 " + optionId + " 缺少 target_node_id。");
            if (kind == DialogueOptionKind.End && !string.IsNullOrWhiteSpace(targetNodeId))
                throw GameContractException.Validation("end 选项 " + optionId + " 不能带 target_node_id。");

            OptionId = optionId;
            Label = label;
            Kind = kind;
            TargetNodeId = string.IsNullOrWhiteSpace(targetNodeId) ? null : targetNodeId;
            Condition = condition ?? DialogueCondition.Always;
        }

        public string OptionId { get; }

        public string Label { get; }

        public DialogueOptionKind Kind { get; }

        public string TargetNodeId { get; }

        public DialogueCondition Condition { get; }
    }

    public sealed class DialogueNodeDefinition
    {
        private readonly ReadOnlyCollection<DialogueOptionDefinition> options;

        public DialogueNodeDefinition(
            string nodeId,
            string contentRef,
            string text,
            IReadOnlyList<DialogueOptionDefinition> options)
        {
            if (string.IsNullOrWhiteSpace(nodeId)) throw GameContractException.Validation("node_id 不能为空。");
            if (string.IsNullOrWhiteSpace(contentRef)) throw GameContractException.Validation("节点 " + nodeId + " 缺少 content_ref。");
            if (string.IsNullOrWhiteSpace(text)) throw GameContractException.Validation("节点 " + nodeId + " 缺少 text。");

            NodeId = nodeId;
            ContentRef = contentRef;
            Text = text;
            this.options = new ReadOnlyCollection<DialogueOptionDefinition>(
                options == null ? new List<DialogueOptionDefinition>() : new List<DialogueOptionDefinition>(options));
        }

        public string NodeId { get; }

        public string ContentRef { get; }

        public string Text { get; }

        public IReadOnlyList<DialogueOptionDefinition> Options => options;

        public bool TryGetOption(string optionId, out DialogueOptionDefinition option)
        {
            foreach (var candidate in options)
            {
                if (string.Equals(candidate.OptionId, optionId, StringComparison.Ordinal))
                {
                    option = candidate;
                    return true;
                }
            }

            option = null;
            return false;
        }

        public DialogueSegment ToSegment()
        {
            return new DialogueSegment(ContentRef, Text);
        }
    }

    /// <summary>
    /// Approved disclosure content. Testimony/Recognition rows carry a fixed line;
    /// Verification rows deliberately carry no text (DataSchema D02 laozhou case).
    /// </summary>
    public sealed class DialogueDisclosureDefinition
    {
        public DialogueDisclosureDefinition(
            string disclosureId,
            string npcId,
            DialogueDisclosureKind kind,
            IReadOnlyList<string> requiredEvidenceIds,
            IReadOnlyList<string> requiredObservedFieldIds,
            string contentRef,
            string text)
        {
            if (string.IsNullOrWhiteSpace(disclosureId)) throw GameContractException.Validation("disclosure_id 不能为空。");
            if (string.IsNullOrWhiteSpace(npcId)) throw GameContractException.Validation("disclosure " + disclosureId + " 缺少 npc_id。");
            if (requiredEvidenceIds == null || requiredEvidenceIds.Count == 0)
                throw GameContractException.Validation("disclosure " + disclosureId + " 至少需要一个 required_evidence_id。");

            if (kind == DialogueDisclosureKind.Verification)
            {
                if (!string.IsNullOrEmpty(contentRef) || !string.IsNullOrEmpty(text))
                    throw GameContractException.Validation("verification disclosure " + disclosureId + " 不能带固定台词。");
            }
            else if (string.IsNullOrWhiteSpace(contentRef) || string.IsNullOrWhiteSpace(text))
            {
                throw GameContractException.Validation("disclosure " + disclosureId + " 缺少 content_ref 或 text。");
            }

            DisclosureId = disclosureId;
            NpcId = npcId;
            Kind = kind;
            RequiredEvidenceIds = requiredEvidenceIds;
            RequiredObservedFieldIds = requiredObservedFieldIds ?? Array.Empty<string>();
            ContentRef = string.IsNullOrEmpty(contentRef) ? null : contentRef;
            Text = string.IsNullOrEmpty(text) ? null : text;
        }

        public string DisclosureId { get; }

        public string NpcId { get; }

        public DialogueDisclosureKind Kind { get; }

        public IReadOnlyList<string> RequiredEvidenceIds { get; }

        public IReadOnlyList<string> RequiredObservedFieldIds { get; }

        public string ContentRef { get; }

        public string Text { get; }

        public IReadOnlyList<DialogueSegment> FixedSegments
        {
            get
            {
                if (string.IsNullOrEmpty(Text)) return Array.Empty<DialogueSegment>();
                return new[] { new DialogueSegment(ContentRef, Text) };
            }
        }

        public bool RequirementsMet(ISet<string> currentEvidenceIds, Shared.Contracts.IEvidenceStateView evidence)
        {
            foreach (var evidenceId in RequiredEvidenceIds)
            {
                if (!currentEvidenceIds.Contains(evidenceId)) return false;
            }

            foreach (var fieldId in RequiredObservedFieldIds)
            {
                if (!evidence.IsFieldObserved(fieldId)) return false;
            }

            return true;
        }
    }

    public sealed class NpcDialogueDefinition
    {
        public NpcDialogueDefinition(
            string npcId,
            string displayName,
            string openingNodeId,
            IReadOnlyList<string> allowedEvidenceIds,
            IReadOnlyList<DialogueNodeDefinition> nodes,
            IReadOnlyList<DialogueDisclosureDefinition> disclosures)
        {
            if (!NpcIdRules.IsWellFormed(npcId)) throw GameContractException.Validation("npc_id '" + npcId + "' 格式无效。");
            if (string.IsNullOrWhiteSpace(displayName)) throw GameContractException.Validation("NPC " + npcId + " 缺少 display_name。");
            if (nodes == null || nodes.Count == 0) throw GameContractException.Validation("NPC " + npcId + " 没有对话节点。");
            if (allowedEvidenceIds == null || allowedEvidenceIds.Count == 0)
                throw GameContractException.Validation("NPC " + npcId + " 没有 allowed_evidence_ids。");

            var byId = new Dictionary<string, DialogueNodeDefinition>(StringComparer.Ordinal);
            foreach (var node in nodes)
            {
                if (byId.ContainsKey(node.NodeId))
                    throw GameContractException.Validation("NPC " + npcId + " 存在重复 node_id '" + node.NodeId + "'。");
                byId.Add(node.NodeId, node);
            }

            if (!byId.ContainsKey(openingNodeId))
                throw GameContractException.Validation("NPC " + npcId + " 的 opening_node_id '" + openingNodeId + "' 不存在。");

            foreach (var node in nodes)
            {
                var optionIds = new HashSet<string>(StringComparer.Ordinal);
                foreach (var option in node.Options)
                {
                    if (!optionIds.Add(option.OptionId))
                        throw GameContractException.Validation("节点 " + node.NodeId + " 存在重复 option_id '" + option.OptionId + "'。");
                    if (option.Kind == DialogueOptionKind.Topic && !byId.ContainsKey(option.TargetNodeId))
                        throw GameContractException.Validation("选项 " + option.OptionId + " 指向不存在的节点 '" + option.TargetNodeId + "'。");
                }
            }

            var disclosuresById = new Dictionary<string, DialogueDisclosureDefinition>(StringComparer.Ordinal);
            if (disclosures != null)
            {
                foreach (var disclosure in disclosures)
                {
                    if (!string.Equals(disclosure.NpcId, npcId, StringComparison.Ordinal))
                        throw GameContractException.Validation("disclosure " + disclosure.DisclosureId + " 的 npc_id 与所属 NPC 不一致。");
                    if (disclosuresById.ContainsKey(disclosure.DisclosureId))
                        throw GameContractException.Validation("NPC " + npcId + " 存在重复 disclosure_id '" + disclosure.DisclosureId + "'。");
                    disclosuresById.Add(disclosure.DisclosureId, disclosure);
                }
            }

            NpcId = npcId;
            DisplayName = displayName;
            OpeningNodeId = openingNodeId;
            AllowedEvidenceIds = allowedEvidenceIds;
            Nodes = new ReadOnlyCollection<DialogueNodeDefinition>(new List<DialogueNodeDefinition>(nodes));
            Disclosures = new ReadOnlyCollection<DialogueDisclosureDefinition>(
                disclosures == null ? new List<DialogueDisclosureDefinition>() : new List<DialogueDisclosureDefinition>(disclosures));
            nodesById = byId;
            disclosuresByIdInternal = disclosuresById;
        }

        private readonly Dictionary<string, DialogueNodeDefinition> nodesById;
        private readonly Dictionary<string, DialogueDisclosureDefinition> disclosuresByIdInternal;

        public string NpcId { get; }

        public string DisplayName { get; }

        public string OpeningNodeId { get; }

        public IReadOnlyList<string> AllowedEvidenceIds { get; }

        public IReadOnlyList<DialogueNodeDefinition> Nodes { get; }

        public IReadOnlyList<DialogueDisclosureDefinition> Disclosures { get; }

        public bool AllowsEvidence(string evidenceId)
        {
            if (evidenceId == null) return false;
            foreach (var allowed in AllowedEvidenceIds)
            {
                if (string.Equals(allowed, evidenceId, StringComparison.Ordinal)) return true;
            }

            return false;
        }

        public DialogueNodeDefinition GetNode(string nodeId)
        {
            if (nodeId != null && nodesById.TryGetValue(nodeId, out var node)) return node;
            throw GameContractException.NotFound("NPC " + NpcId + " 不存在对话节点 '" + nodeId + "'。");
        }

        public DialogueDisclosureDefinition GetDisclosure(string disclosureId)
        {
            if (disclosureId != null && disclosuresByIdInternal.TryGetValue(disclosureId, out var disclosure)) return disclosure;
            throw GameContractException.NotFound("NPC " + NpcId + " 不存在 disclosure '" + disclosureId + "'。");
        }
    }

    public static class NpcIdRules
    {
        public static bool IsWellFormed(string npcId)
        {
            return !string.IsNullOrEmpty(npcId) && npcId.StartsWith("npc_", StringComparison.Ordinal) && npcId.Length > 4;
        }
    }

    public sealed class DialogueCatalog
    {
        private readonly Dictionary<string, NpcDialogueDefinition> byNpcId;

        public DialogueCatalog(string contentVersion, IReadOnlyList<NpcDialogueDefinition> npcs)
        {
            if (string.IsNullOrWhiteSpace(contentVersion)) throw GameContractException.Validation("content_version 不能为空。");
            if (npcs == null || npcs.Count == 0) throw GameContractException.Validation("对话目录不能为空。");

            byNpcId = new Dictionary<string, NpcDialogueDefinition>(StringComparer.Ordinal);
            var ordered = new List<NpcDialogueDefinition>(npcs.Count);
            foreach (var npc in npcs)
            {
                if (npc == null) throw GameContractException.Validation("对话目录中存在 null NPC。");
                if (byNpcId.ContainsKey(npc.NpcId))
                    throw GameContractException.Validation("重复 npc_id '" + npc.NpcId + "'。");
                byNpcId.Add(npc.NpcId, npc);
                ordered.Add(npc);
            }

            ContentVersion = contentVersion;
            Npcs = new ReadOnlyCollection<NpcDialogueDefinition>(ordered);
        }

        public string ContentVersion { get; }

        public IReadOnlyList<NpcDialogueDefinition> Npcs { get; }

        public bool Contains(string npcId)
        {
            return npcId != null && byNpcId.ContainsKey(npcId);
        }

        public NpcDialogueDefinition Get(string npcId)
        {
            if (!NpcIdRules.IsWellFormed(npcId))
                throw GameContractException.InvalidRequest("npc_id '" + npcId + "' 格式无效。");
            if (!byNpcId.TryGetValue(npcId, out var npc))
                throw GameContractException.NotFound("NPC '" + npcId + "' 没有已批准的对话内容。");
            return npc;
        }

        public bool TryGet(string npcId, out NpcDialogueDefinition npc)
        {
            npc = null;
            return npcId != null && byNpcId.TryGetValue(npcId, out npc);
        }
    }
}
