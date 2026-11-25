using System;
using System.Collections.Generic;
using System.Linq;
using EchoLostAndFound.Shared.Ai;
using EchoLostAndFound.Shared.Contracts;

namespace EchoLostAndFound.Dialogue
{
    public static class DialogueEventTypes
    {
        public const string SessionOpened = "dialogue.session_opened";
        public const string TurnCompleted = "dialogue.turn_completed";
        public const string EvidencePresented = "dialogue.evidence_presented";
        public const string DisclosureTriggered = "dialogue.disclosure_triggered";
        public const string SessionClosed = "dialogue.session_closed";
        public const string SessionExpired = "dialogue.session_expired";
    }

    /// <summary>
    /// Dialogue result event emitted by the deterministic engine. AI output never creates
    /// one of these and never carries evidence: only successful engine transitions publish.
    /// </summary>
    public sealed class DialogueResultEvent
    {
        public DialogueResultEvent(
            string eventId,
            string eventType,
            string conversationId,
            string npcId,
            string nodeId,
            string disclosureId,
            IReadOnlyList<string> evidenceIds,
            IReadOnlyList<string> fieldIds,
            IReadOnlyList<string> contentRefs,
            string contentVersion)
        {
            EventId = eventId;
            EventType = eventType;
            ConversationId = conversationId;
            NpcId = npcId;
            NodeId = nodeId;
            DisclosureId = disclosureId;
            EvidenceIds = evidenceIds ?? Array.Empty<string>();
            FieldIds = fieldIds ?? Array.Empty<string>();
            ContentRefs = contentRefs ?? Array.Empty<string>();
            ContentVersion = contentVersion;
        }

        public string EventId { get; }

        public string EventType { get; }

        public string ConversationId { get; }

        public string NpcId { get; }

        public string NodeId { get; }

        public string DisclosureId { get; }

        public IReadOnlyList<string> EvidenceIds { get; }

        public IReadOnlyList<string> FieldIds { get; }

        public IReadOnlyList<string> ContentRefs { get; }

        public string ContentVersion { get; }
    }

    /// <summary>Player-facing option. Only currently available options are ever exposed.</summary>
    public sealed class DialogueOptionView
    {
        public DialogueOptionView(string optionId, string label, DialogueOptionKind kind)
        {
            OptionId = optionId;
            Label = label;
            Kind = kind;
        }

        public string OptionId { get; }

        public string Label { get; }

        public DialogueOptionKind Kind { get; }
    }

    public sealed class DialogueSession
    {
        internal readonly HashSet<string> PresentedEvidence = new HashSet<string>(StringComparer.Ordinal);
        internal readonly HashSet<string> SatisfiedDisclosures = new HashSet<string>(StringComparer.Ordinal);

        internal DialogueSession(string conversationId, string npcId, string currentNodeId)
        {
            ConversationId = conversationId;
            NpcId = npcId;
            CurrentNodeId = currentNodeId;
            Status = DialogueSessionStatus.Open;
        }

        public string ConversationId { get; }

        public string NpcId { get; }

        public DialogueSessionStatus Status { get; internal set; }

        public string CurrentNodeId { get; internal set; }

        public bool IsOpen => Status == DialogueSessionStatus.Open;

        public string StatusContractValue => DialogueEngine.ToContractValue(Status);
    }

    public sealed class DialogueTurnResult
    {
        public DialogueTurnResult(
            string turnId,
            string conversationId,
            string npcId,
            DialogueSessionStatus sessionStatus,
            string nodeId,
            IReadOnlyList<DialogueSegment> segments,
            string generatedBridge,
            string fallbackReason,
            IReadOnlyList<DialogueOptionView> availableOptions,
            IReadOnlyList<DialogueResultEvent> events)
        {
            TurnId = turnId;
            ConversationId = conversationId;
            NpcId = npcId;
            SessionStatus = sessionStatus;
            NodeId = nodeId;
            Segments = segments ?? Array.Empty<DialogueSegment>();
            GeneratedBridge = generatedBridge;
            FallbackReason = fallbackReason;
            AvailableOptions = availableOptions ?? Array.Empty<DialogueOptionView>();
            Events = events ?? Array.Empty<DialogueResultEvent>();
        }

        public string TurnId { get; }

        public string ConversationId { get; }

        public string NpcId { get; }

        public DialogueSessionStatus SessionStatus { get; }

        public string StatusContractValue => DialogueEngine.ToContractValue(SessionStatus);

        public string NodeId { get; }

        public IReadOnlyList<DialogueSegment> Segments { get; }

        /// <summary>Only set for a completed free-text turn; null otherwise. Never a fixed line.</summary>
        public string GeneratedBridge { get; }

        public string FallbackReason { get; }

        public IReadOnlyList<DialogueOptionView> AvailableOptions { get; }

        public IReadOnlyList<DialogueResultEvent> Events { get; }
    }

    public sealed class DialogueEvidencePresentationResult
    {
        public DialogueEvidencePresentationResult(
            string conversationId,
            string npcId,
            IReadOnlyList<string> presentedEvidenceIds,
            IReadOnlyList<string> newlyPresentedFieldIds,
            bool alreadyPresented,
            IReadOnlyList<string> availableDisclosureIds,
            IReadOnlyList<string> triggeredDisclosureIds,
            IReadOnlyList<DialogueSegment> segments,
            IReadOnlyList<DialogueResultEvent> events)
        {
            ConversationId = conversationId;
            NpcId = npcId;
            PresentedEvidenceIds = presentedEvidenceIds ?? Array.Empty<string>();
            NewlyPresentedFieldIds = newlyPresentedFieldIds ?? Array.Empty<string>();
            AlreadyPresented = alreadyPresented;
            AvailableDisclosureIds = availableDisclosureIds ?? Array.Empty<string>();
            TriggeredDisclosureIds = triggeredDisclosureIds ?? Array.Empty<string>();
            Segments = segments ?? Array.Empty<DialogueSegment>();
            Events = events ?? Array.Empty<DialogueResultEvent>();
        }

        public string ConversationId { get; }

        public string NpcId { get; }

        public IReadOnlyList<string> PresentedEvidenceIds { get; }

        public IReadOnlyList<string> NewlyPresentedFieldIds { get; }

        /// <summary>True when this call added no new field; DataSchema duplicate-presentation shape.</summary>
        public bool AlreadyPresented { get; }

        public IReadOnlyList<string> AvailableDisclosureIds { get; }

        public IReadOnlyList<string> TriggeredDisclosureIds { get; }

        public IReadOnlyList<DialogueSegment> Segments { get; }

        public IReadOnlyList<DialogueResultEvent> Events { get; }
    }

    /// <summary>
    /// Offline, deterministic dialogue state machine for Chapter 1. It needs no network,
    /// no model and no UnityEngine API: fixed content drives every line, options are gated
    /// by evidence state, and the optional AI provider is used only for generated bridges
    /// whose text can never change evidence, disclosures or nodes.
    /// </summary>
    public sealed class DialogueEngine
    {
        private readonly DialogueCatalog catalog;
        private readonly IEvidenceStateView evidence;
        private readonly IIdGenerator idGenerator;
        private readonly INpcAiProvider aiProvider;
        private readonly Dictionary<string, DialogueSession> sessions = new Dictionary<string, DialogueSession>(StringComparer.Ordinal);
        private readonly Dictionary<string, HashSet<string>> npcPresentedFields = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal);
        private readonly Dictionary<string, HashSet<string>> npcPlayedDisclosures = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal);

        public DialogueEngine(
            DialogueCatalog catalog,
            IEvidenceStateView evidence,
            IIdGenerator idGenerator = null,
            INpcAiProvider aiProvider = null)
        {
            this.catalog = catalog ?? throw new ArgumentNullException(nameof(catalog));
            this.evidence = evidence ?? throw new ArgumentNullException(nameof(evidence));
            this.idGenerator = idGenerator ?? GuidIdGenerator.Instance;
            this.aiProvider = aiProvider;
        }

        /// <summary>Raised synchronously for every published <see cref="DialogueResultEvent"/>.</summary>
        public event Action<DialogueResultEvent> EventRaised;

        public DialogueCatalog Catalog => catalog;

        public string[] PresentedFields(string npc) => npcPresentedFields.TryGetValue(npc, out var fields)
            ? fields.OrderBy(id => id, StringComparer.Ordinal).ToArray() : Array.Empty<string>();

        public string[] PlayedDisclosures(string npc) => npcPlayedDisclosures.TryGetValue(npc, out var ids)
            ? ids.OrderBy(id => id, StringComparer.Ordinal).ToArray() : Array.Empty<string>();

        // Restore durable knowledge only. Conversation IDs, turns and network sessions are transient.
        public void RestoreKnowledge(string npcId, IReadOnlyList<string> fields, IReadOnlyList<string> played)
        {
            var npc = catalog.Get(npcId);
            var seen = new HashSet<string>(fields, StringComparer.Ordinal);
            var cards = new HashSet<string>(npc.AllowedEvidenceIds.Where(id => evidence.HasEvidence(id)
                && evidence.GetObservedFieldIds(id).All(seen.Contains)), StringComparer.Ordinal);
            var allowedFields = new HashSet<string>(cards.SelectMany(id => evidence.GetObservedFieldIds(id)));
            var valid = npc.Disclosures.Where(d => d.RequirementsMet(cards, evidence)).Select(d => d.DisclosureId);
            if (!seen.IsSubsetOf(allowedFields) || played.Except(valid).Any())
                throw GameContractException.SaveCorrupt("人物核对记录与证据不一致。");
            npcPresentedFields[npcId] = seen;
            npcPlayedDisclosures[npcId] = new HashSet<string>(played, StringComparer.Ordinal);
        }

        public static string ToContractValue(DialogueSessionStatus status)
        {
            switch (status)
            {
                case DialogueSessionStatus.Open: return "open";
                case DialogueSessionStatus.Closed: return "closed";
                case DialogueSessionStatus.Cancelled: return "cancelled";
                case DialogueSessionStatus.Expired: return "expired";
                default: throw new ArgumentOutOfRangeException(nameof(status));
            }
        }

        /// <summary>
        /// Opens a conversation and returns the opening node plus available options.
        /// DataSchema §5: a new conversation closes the previous open conversation.
        /// </summary>
        public DialogueTurnResult StartSession(string npcId)
        {
            var npc = catalog.Get(npcId);
            CloseOpenSessions(DialogueSessionStatus.Closed);

            var session = new DialogueSession(idGenerator.CreateId(), npc.NpcId, npc.OpeningNodeId);
            if (npcPlayedDisclosures.TryGetValue(npcId, out var remembered))
                session.SatisfiedDisclosures.UnionWith(remembered);
            sessions.Add(session.ConversationId, session);
            var node = npc.GetNode(npc.OpeningNodeId);
            var events = new List<DialogueResultEvent>
            {
                CreateEvent(DialogueEventTypes.SessionOpened, session, node.NodeId, null, null, null, new[] { node.ContentRef })
            };
            Publish(events);
            return new DialogueTurnResult(
                idGenerator.CreateId(),
                session.ConversationId,
                npc.NpcId,
                session.Status,
                session.CurrentNodeId,
                new[] { node.ToSegment() },
                null,
                null,
                BuildAvailableOptions(npc, node, session),
                events);
        }

        public DialogueSession GetSession(string conversationId)
        {
            if (conversationId == null || !sessions.TryGetValue(conversationId, out var session))
                throw GameContractException.NotFound("对话会话 '" + conversationId + "' 不存在。");
            return session;
        }

        public IReadOnlyList<DialogueOptionView> GetAvailableOptions(string conversationId)
        {
            var session = GetRequiredOpenSession(conversationId);
            var npc = catalog.Get(session.NpcId);
            return BuildAvailableOptions(npc, npc.GetNode(session.CurrentNodeId), session);
        }

        /// <summary>Advances the conversation through one fixed option.</summary>
        public DialogueTurnResult Choose(string conversationId, string optionId)
        {
            if (string.IsNullOrWhiteSpace(optionId))
                throw GameContractException.InvalidRequest("option_id 不能为空。");
            var session = GetRequiredOpenSession(conversationId);
            var npc = catalog.Get(session.NpcId);
            var node = npc.GetNode(session.CurrentNodeId);
            if (!node.TryGetOption(optionId, out var option))
                throw GameContractException.NotFound("节点 " + node.NodeId + " 不存在选项 '" + optionId + "'。");
            if (!option.Condition.IsSatisfied(evidence, session.SatisfiedDisclosures.Contains))
                throw GameContractException.Precondition("选项 " + option.OptionId + " 的开启条件尚未满足。");

            if (option.Kind == DialogueOptionKind.End)
            {
                session.Status = DialogueSessionStatus.Closed;
                var closeEvent = CreateEvent(DialogueEventTypes.SessionClosed, session, node.NodeId, null, null, null, Array.Empty<string>());
                Publish(new[] { closeEvent });
                return new DialogueTurnResult(
                    idGenerator.CreateId(),
                    session.ConversationId,
                    npc.NpcId,
                    session.Status,
                    session.CurrentNodeId,
                    Array.Empty<DialogueSegment>(),
                    null,
                    null,
                    Array.Empty<DialogueOptionView>(),
                    new[] { closeEvent });
            }

            var target = npc.GetNode(option.TargetNodeId);
            session.CurrentNodeId = target.NodeId;
            var turnEvent = CreateEvent(
                DialogueEventTypes.TurnCompleted,
                session,
                target.NodeId,
                null,
                null,
                null,
                new[] { target.ContentRef });
            Publish(new[] { turnEvent });
            return new DialogueTurnResult(
                idGenerator.CreateId(),
                session.ConversationId,
                npc.NpcId,
                session.Status,
                session.CurrentNodeId,
                new[] { target.ToSegment() },
                null,
                null,
                BuildAvailableOptions(npc, target, session),
                new[] { turnEvent });
        }

        /// <summary>
        /// Presents evidence inside an open conversation (DataSchema npc.present +
        /// disclosure.trigger). An NPC only accepts evidence that has approved content;
        /// a D requires every listed evidence card, so partial sets never trigger it.
        /// Re-presenting already known fields is reported as AlreadyPresented and never
        /// publishes another evidence event.
        /// </summary>
        public DialogueEvidencePresentationResult PresentEvidence(string conversationId, IReadOnlyList<string> evidenceIds)
        {
            var session = GetRequiredOpenSession(conversationId);
            if (evidenceIds == null || evidenceIds.Count == 0)
                throw GameContractException.InvalidRequest("evidence_ids 至少需要一个。");

            var npc = catalog.Get(session.NpcId);
            var requested = new List<string>(evidenceIds.Count);
            var requestSet = new HashSet<string>(StringComparer.Ordinal);
            foreach (var evidenceId in evidenceIds)
            {
                if (string.IsNullOrWhiteSpace(evidenceId))
                    throw GameContractException.InvalidRequest("evidence_id 不能为空。");
                if (!requestSet.Add(evidenceId)) continue;
                if (!npc.AllowsEvidence(evidenceId))
                    throw GameContractException.Precondition(
                        "证据 '" + evidenceId + "' 没有为 NPC " + npc.NpcId + " 配置已批准回应。");
                if (!evidence.HasEvidence(evidenceId))
                    throw GameContractException.Precondition("证据 '" + evidenceId + "' 尚未获得，不能出示。");
                requested.Add(evidenceId);
            }

            var allAlreadyInSession = true;
            foreach (var evidenceId in requested)
            {
                if (!session.PresentedEvidence.Contains(evidenceId)) allAlreadyInSession = false;
            }

            if (!npcPresentedFields.TryGetValue(npc.NpcId, out var presentedFields))
            {
                presentedFields = new HashSet<string>(StringComparer.Ordinal);
                npcPresentedFields.Add(npc.NpcId, presentedFields);
            }

            var newlyPresentedFields = new List<string>();
            foreach (var evidenceId in requested)
            {
                session.PresentedEvidence.Add(evidenceId);
                foreach (var fieldId in evidence.GetObservedFieldIds(evidenceId))
                {
                    if (presentedFields.Add(fieldId)) newlyPresentedFields.Add(fieldId);
                }
            }

            var available = new List<string>();
            var triggered = new List<string>();
            var segments = new List<DialogueSegment>();
            var events = new List<DialogueResultEvent>();

            foreach (var disclosure in npc.Disclosures)
            {
                if (!disclosure.RequirementsMet(session.PresentedEvidence, evidence)) continue;
                if (session.SatisfiedDisclosures.Add(disclosure.DisclosureId))
                    available.Add(disclosure.DisclosureId);

                if (!npcPlayedDisclosures.TryGetValue(npc.NpcId, out var played))
                {
                    played = new HashSet<string>(StringComparer.Ordinal);
                    npcPlayedDisclosures.Add(npc.NpcId, played);
                }

                foreach (var segment in disclosure.FixedSegments) segments.Add(segment);
                if (!played.Add(disclosure.DisclosureId)) continue;

                triggered.Add(disclosure.DisclosureId);
                var contentRefs = disclosure.ContentRef == null ? null : new[] { disclosure.ContentRef };
                events.Add(CreateEvent(
                    DialogueEventTypes.DisclosureTriggered,
                    session,
                    session.CurrentNodeId,
                    disclosure.DisclosureId,
                    disclosure.RequiredEvidenceIds,
                    disclosure.RequiredObservedFieldIds,
                    contentRefs));
            }

            var alreadyPresented = allAlreadyInSession && newlyPresentedFields.Count == 0;
            if (newlyPresentedFields.Count > 0)
            {
                events.Insert(0, CreateEvent(
                    DialogueEventTypes.EvidencePresented,
                    session,
                    session.CurrentNodeId,
                    null,
                    requested,
                    newlyPresentedFields,
                    null));
            }

            Publish(events);
            return new DialogueEvidencePresentationResult(
                session.ConversationId,
                npc.NpcId,
                requested,
                newlyPresentedFields,
                alreadyPresented,
                available,
                triggered,
                segments,
                events);
        }

        /// <summary>
        /// Free-text turn (DataSchema §5): fixed segments are unaffected, the optional AI
        /// provider may only produce generated_bridge text, and every failure path returns
        /// a fallback_reason instead of story state.
        /// </summary>
        public DialogueTurnResult SubmitFreeText(string conversationId, string playerInput, int timeoutMilliseconds = 3000)
        {
            var session = GetRequiredOpenSession(conversationId);
            if (string.IsNullOrWhiteSpace(playerInput))
                throw GameContractException.InvalidRequest("player_input 不能为空。");
            if (playerInput.Length > 2000)
                throw GameContractException.RequestTooLarge("player_input 超过 2000 字上限。");
            if (timeoutMilliseconds <= 0)
                throw GameContractException.InvalidRequest("timeout_ms 必须为正数。");

            var npc = catalog.Get(session.NpcId);
            var node = npc.GetNode(session.CurrentNodeId);
            var options = BuildAvailableOptions(npc, node, session);
            var topicIds = new List<string>(options.Count);
            foreach (var option in options)
            {
                if (option.Kind == DialogueOptionKind.Topic) topicIds.Add(option.OptionId);
            }

            var request = new NpcAiRequest(
                idGenerator.CreateId(),
                npc.NpcId,
                playerInput,
                new List<string>(evidence.AcquiredEvidenceIds),
                topicIds,
                timeoutMilliseconds,
                catalog.ContentVersion);

            NpcAiReply reply = null;
            if (aiProvider != null)
            {
                try
                {
                    reply = aiProvider.Generate(request);
                }
                catch (Exception exception)
                {
                    reply = NpcAiReply.Failed(NpcAiOutcome.ModelUnavailable, "provider-exception", exception.GetType().Name);
                }
            }

            string fallbackReason;
            string generatedBridge = null;
            if (reply == null)
            {
                fallbackReason = aiProvider == null
                    ? NpcAiFallbackReasons.ModelUnavailable
                    : NpcAiFallbackReasons.InvalidOutput;
            }
            else if (reply.Outcome == NpcAiOutcome.Completed && !string.IsNullOrWhiteSpace(reply.Text))
            {
                fallbackReason = null;
                generatedBridge = reply.Text;
            }
            else
            {
                fallbackReason = string.IsNullOrEmpty(reply.FallbackReason)
                    ? NpcAiFallbackReasons.ForOutcome(reply.Outcome)
                    : reply.FallbackReason;
            }

            var turnEvent = CreateEvent(
                DialogueEventTypes.TurnCompleted,
                session,
                session.CurrentNodeId,
                null,
                null,
                null,
                Array.Empty<string>());
            Publish(new[] { turnEvent });

            return new DialogueTurnResult(
                request.RequestId,
                session.ConversationId,
                npc.NpcId,
                session.Status,
                session.CurrentNodeId,
                Array.Empty<DialogueSegment>(),
                generatedBridge,
                fallbackReason,
                options,
                new[] { turnEvent });
        }

        /// <summary>Explicitly closes a session (UI "离开 NPC").</summary>
        public void CloseSession(string conversationId)
        {
            var session = GetSession(conversationId);
            if (session.Status == DialogueSessionStatus.Open)
            {
                session.Status = DialogueSessionStatus.Closed;
                Publish(new[] { CreateEvent(DialogueEventTypes.SessionClosed, session, session.CurrentNodeId, null, null, null, Array.Empty<string>()) });
            }
        }

        /// <summary>
        /// Marks every open session Expired. DataSchema: conversations are not persisted and
        /// expire when game state is restored; call this after loading a snapshot.
        /// </summary>
        public IReadOnlyList<string> ExpireOpenSessions()
        {
            var expired = new List<string>();
            var events = new List<DialogueResultEvent>();
            foreach (var session in sessions.Values)
            {
                if (session.Status != DialogueSessionStatus.Open) continue;
                session.Status = DialogueSessionStatus.Expired;
                expired.Add(session.ConversationId);
                events.Add(CreateEvent(DialogueEventTypes.SessionExpired, session, session.CurrentNodeId, null, null, null, Array.Empty<string>()));
            }

            Publish(events);
            return expired;
        }

        private void CloseOpenSessions(DialogueSessionStatus newStatus)
        {
            var events = new List<DialogueResultEvent>();
            foreach (var session in sessions.Values)
            {
                if (session.Status != DialogueSessionStatus.Open) continue;
                session.Status = newStatus;
                events.Add(CreateEvent(DialogueEventTypes.SessionClosed, session, session.CurrentNodeId, null, null, null, Array.Empty<string>()));
            }

            Publish(events);
        }

        private DialogueSession GetRequiredOpenSession(string conversationId)
        {
            var session = GetSession(conversationId);
            if (!session.IsOpen)
                throw GameContractException.TurnExpired("对话会话已结束（" + session.StatusContractValue + "）。");
            return session;
        }

        private IReadOnlyList<DialogueOptionView> BuildAvailableOptions(
            NpcDialogueDefinition npc,
            DialogueNodeDefinition node,
            DialogueSession session)
        {
            var result = new List<DialogueOptionView>();
            foreach (var option in node.Options)
            {
                if (!option.Condition.IsSatisfied(evidence, session.SatisfiedDisclosures.Contains)) continue;
                result.Add(new DialogueOptionView(option.OptionId, option.Label, option.Kind));
            }

            return result;
        }

        private DialogueResultEvent CreateEvent(
            string eventType,
            DialogueSession session,
            string nodeId,
            string disclosureId,
            IReadOnlyList<string> evidenceIds,
            IReadOnlyList<string> fieldIds,
            IReadOnlyList<string> contentRefs)
        {
            return new DialogueResultEvent(
                idGenerator.CreateId(),
                eventType,
                session.ConversationId,
                session.NpcId,
                nodeId,
                disclosureId,
                evidenceIds,
                fieldIds,
                contentRefs,
                catalog.ContentVersion);
        }

        private void Publish(IReadOnlyList<DialogueResultEvent> events)
        {
            var handler = EventRaised;
            if (handler == null) return;
            foreach (var stateEvent in events) handler(stateEvent);
        }
    }
}
