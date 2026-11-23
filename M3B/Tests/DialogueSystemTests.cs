using System;
using System.Collections.Generic;
using System.Linq;
using EchoLostAndFound.Dialogue;
using EchoLostAndFound.Evidence;
using EchoLostAndFound.MockAi;
using EchoLostAndFound.Shared.Ai;
using EchoLostAndFound.Shared.Contracts;
using EchoLostAndFound.Shared.Json;

namespace EchoLostAndFound.Tests
{
    internal static class DialogueSystemTests
    {
        public static void Register(TestRegistry registry)
        {
            registry.Add("Dialogue_SessionTransitionsAndFixedLines", SessionTransitionsAndFixedLines);
            registry.Add("Dialogue_ConditionalOptionUnlocksAfterDisclosure", ConditionalOptionUnlocksAfterDisclosure);
            registry.Add("Dialogue_EvidencePresentationTriggersD01", EvidencePresentationTriggersD01);
            registry.Add("Dialogue_D02RequiresBothDocuments", D02RequiresBothDocuments);
            registry.Add("Dialogue_D02VerificationForLaozhouHasNoLine", D02VerificationForLaozhouHasNoLine);
            registry.Add("Dialogue_D03RequiresWatchAndInspection", D03RequiresWatchAndInspection);
            registry.Add("Dialogue_PresentationRejectsUnknownEvidence", PresentationRejectsUnknownEvidence);
            registry.Add("Dialogue_FreeTextFallbackNeverChangesState", FreeTextFallbackNeverChangesState);
            registry.Add("Dialogue_FreeTextUsesMockBridgeOnly", FreeTextUsesMockBridgeOnly);
            registry.Add("Dialogue_SessionLifecycleAndExpiry", SessionLifecycleAndExpiry);
            registry.Add("Dialogue_CatalogJsonRejectsAnomalies", CatalogJsonRejectsAnomalies);
        }

        private static void SessionTransitionsAndFixedLines()
        {
            var engine = TestData.CreateEngine(TestData.CreateRegistry());
            var events = new List<DialogueResultEvent>();
            engine.EventRaised += events.Add;

            var turn = engine.StartSession("npc_laozhou");
            Assert.Equal(DialogueSessionStatus.Open, turn.SessionStatus);
            Assert.Equal("open", turn.StatusContractValue);
            Assert.Equal("node.laozhou.opening", turn.NodeId);
            Assert.Equal(1, turn.Segments.Count);
            Assert.Equal("dialogue.CH01.opening.laozhou", turn.Segments[0].ContentRef);
            Assert.Equal("这封从旧库搬过两回。我来对号，你来签。先看表背，失物只认号。", turn.Segments[0].Text);

            var optionIds = new List<string>();
            foreach (var option in turn.AvailableOptions) optionIds.Add(option.OptionId);
            Assert.True(optionIds.Contains("opt.laozhou.ask_b01"));
            Assert.True(optionIds.Contains("opt.laozhou.leave"));
            Assert.False(optionIds.Contains("opt.laozhou.repeat_b01"), "D01 未达成前不应出现重复追问选项。");

            var b01 = engine.Choose(turn.ConversationId, "opt.laozhou.ask_b01");
            Assert.Equal("node.laozhou.b01", b01.NodeId);
            Assert.Equal("dialogue.CH01.B01.initial", b01.Segments[0].ContentRef);
            Assert.Equal("站台那晚在我印象里一直亮着。我还把那盏油灯拖到里头去了。", b01.Segments[0].Text);

            var closed = engine.Choose(turn.ConversationId, "opt.laozhou.b01.leave");
            Assert.Equal(DialogueSessionStatus.Closed, closed.SessionStatus);
            Assert.ContractCode(() => engine.Choose(turn.ConversationId, "opt.laozhou.b01.back"), ErrorCodes.TurnExpired);

            var eventTypes = new List<string>();
            foreach (var e in events) eventTypes.Add(e.EventType);
            Assert.True(eventTypes.Contains(DialogueEventTypes.SessionOpened));
            Assert.True(eventTypes.Contains(DialogueEventTypes.TurnCompleted));
            Assert.True(eventTypes.Contains(DialogueEventTypes.SessionClosed));
        }

        private static void ConditionalOptionUnlocksAfterDisclosure()
        {
            var evidence = TestData.CreateRegistry("E02");
            var engine = TestData.CreateEngine(evidence);
            var turn = engine.StartSession("npc_laozhou");

            var before = engine.GetAvailableOptions(turn.ConversationId);
            Assert.False(HasOption(before, "opt.laozhou.repeat_b01"));

            var presentation = engine.PresentEvidence(turn.ConversationId, new[] { "E02" });
            Assert.True(presentation.TriggeredDisclosureIds.Contains("D01"));

            var after = engine.GetAvailableOptions(turn.ConversationId);
            Assert.True(HasOption(after, "opt.laozhou.repeat_b01"), "D01 满意后应解锁重复追问。");

            var again = engine.Choose(turn.ConversationId, "opt.laozhou.repeat_b01");
            Assert.Equal("node.laozhou.b01", again.NodeId);
        }

        private static void EvidencePresentationTriggersD01()
        {
            var evidence = TestData.CreateRegistry("E02");
            var engine = TestData.CreateEngine(evidence);
            var turn = engine.StartSession("npc_laozhou");

            var result = engine.PresentEvidence(turn.ConversationId, new[] { "E02" });
            Assert.SequenceEqual(new[] { "E02" }, result.PresentedEvidenceIds);
            Assert.Equal(4, result.NewlyPresentedFieldIds.Count);
            Assert.False(result.AlreadyPresented);
            Assert.True(result.AvailableDisclosureIds.Contains("D01"));
            Assert.SequenceEqual(new[] { "D01" }, result.TriggeredDisclosureIds);
            Assert.Equal(1, result.Segments.Count);
            Assert.Equal("dialogue.CH01.D01.laozhou", result.Segments[0].ContentRef);
            Assert.Equal("进水，二十一点十七。我的灯到二十才摆好。是黑过，中间那点我记混了。", result.Segments[0].Text);

            var hasPresentationEvent = false;
            var hasDisclosureEvent = false;
            foreach (var e in result.Events)
            {
                if (e.EventType == DialogueEventTypes.EvidencePresented) hasPresentationEvent = true;
                if (e.EventType == DialogueEventTypes.DisclosureTriggered) hasDisclosureEvent = true;
            }

            Assert.True(hasPresentationEvent);
            Assert.True(hasDisclosureEvent);

            var repeat = engine.PresentEvidence(turn.ConversationId, new[] { "E02" });
            Assert.True(repeat.AlreadyPresented);
            Assert.Equal(0, repeat.NewlyPresentedFieldIds.Count);
            Assert.Equal(0, repeat.TriggeredDisclosureIds.Count);
            Assert.Equal(0, repeat.Events.Count, "重复出示不得再发事件。");
            Assert.Equal(1, repeat.Segments.Count, "重复出示可重放已批准固定台词，但仍不产生新事件。");
        }

        private static void D02RequiresBothDocuments()
        {
            var evidence = TestData.CreateRegistry("E03");
            var engine = TestData.CreateEngine(evidence);
            var turn = engine.StartSession("npc_linyao");

            var partial = engine.PresentEvidence(turn.ConversationId, new[] { "E03" });
            Assert.Equal(0, partial.TriggeredDisclosureIds.Count, "仅出示 E03 不得触发 D02。");

            evidence.ObserveFields(TestData.EvidenceCatalog.Get("E04").RequiredFieldIds);
            var complete = engine.PresentEvidence(turn.ConversationId, new[] { "E04" });
            Assert.True(complete.TriggeredDisclosureIds.Contains("D02"));
            Assert.Equal(1, complete.Segments.Count);
            Assert.Equal("dialogue.CH01.D02.linyao", complete.Segments[0].ContentRef);
            Assert.Equal("沈禾，是我妈妈。这个号和她放在家里那张一样。她写着要我自己领。", complete.Segments[0].Text);

            var repeat = engine.PresentEvidence(turn.ConversationId, new[] { "E03", "E04" });
            Assert.True(repeat.AlreadyPresented);
            Assert.Equal(0, repeat.TriggeredDisclosureIds.Count);
        }

        private static void D02VerificationForLaozhouHasNoLine()
        {
            var evidence = TestData.CreateRegistry("E03", "E04");
            var engine = TestData.CreateEngine(evidence);
            var turn = engine.StartSession("npc_laozhou");

            var result = engine.PresentEvidence(turn.ConversationId, new[] { "E03", "E04" });
            Assert.True(result.TriggeredDisclosureIds.Contains("D02"));
            Assert.Equal(0, result.Segments.Count, "老周的 D02 只是核对，不得新增台词。");
            foreach (var e in result.Events)
            {
                if (e.EventType == DialogueEventTypes.DisclosureTriggered)
                {
                    Assert.Equal("D02", e.DisclosureId);
                    Assert.Equal(0, e.ContentRefs.Count);
                }
            }
        }

        private static void D03RequiresWatchAndInspection()
        {
            var evidence = TestData.CreateRegistry("E01", "E05");
            var engine = TestData.CreateEngine(evidence);
            var turn = engine.StartSession("npc_laozhou");

            var result = engine.PresentEvidence(turn.ConversationId, new[] { "E01", "E05" });
            Assert.True(result.TriggeredDisclosureIds.Contains("D03"));
            var d03 = FindSegment(result.Segments, "dialogue.CH01.D03.laozhou");
            Assert.Equal("她抓住小姑娘的胳膊，表掉到台沿。我弯腰拣的时候指针已经不动了，冠头是歪的。", d03.Text);
        }

        private static void PresentationRejectsUnknownEvidence()
        {
            var evidence = TestData.CreateRegistry("E01");
            var engine = TestData.CreateEngine(evidence);
            var laozhouSession = engine.StartSession("npc_laozhou");
            Assert.ContractCode(
                () => engine.PresentEvidence(laozhouSession.ConversationId, new[] { "E99" }),
                ErrorCodes.PreconditionFailed,
                "老周没有为 E99 配置回应。");
            Assert.ContractCode(
                () => engine.PresentEvidence(laozhouSession.ConversationId, new[] { "E02" }),
                ErrorCodes.PreconditionFailed);

            var linyao = engine.StartSession("npc_linyao");
            evidence.ObserveFields(TestData.EvidenceCatalog.Get("E02").RequiredFieldIds);
            Assert.ContractCode(
                () => engine.PresentEvidence(linyao.ConversationId, new[] { "E02" }),
                ErrorCodes.PreconditionFailed);
        }

        private static void FreeTextFallbackNeverChangesState()
        {
            var evidence = TestData.CreateRegistry("E01");
            var provider = new MockAiProvider(TestData.MockScenarios);
            var engine = TestData.CreateEngine(evidence, provider);
            var turn = engine.StartSession("npc_laozhou");

            var timedOut = engine.SubmitFreeText(turn.ConversationId, "超时测试");
            Assert.Equal("timeout", timedOut.FallbackReason);
            Assert.Null(timedOut.GeneratedBridge);
            Assert.Equal(DialogueSessionStatus.Open, engine.GetSession(turn.ConversationId).Status);
            Assert.False(evidence.HasEvidence("E02"));
            Assert.Equal(1, evidence.AcquiredEvidenceIds.Count);

            var noProvider = TestData.CreateEngine(evidence);
            var plain = noProvider.StartSession("npc_laozhou");
            var unavailable = noProvider.SubmitFreeText(plain.ConversationId, "灯");
            Assert.Equal(NpcAiFallbackReasons.ModelUnavailable, unavailable.FallbackReason);
            Assert.Null(unavailable.GeneratedBridge);

            Assert.ContractCode(() => engine.SubmitFreeText(turn.ConversationId, " "), ErrorCodes.InvalidRequest);
            Assert.ContractCode(() => engine.SubmitFreeText(turn.ConversationId, new string('x', 2001)), ErrorCodes.RequestTooLarge);
            Assert.ContractCode(() => engine.SubmitFreeText(turn.ConversationId, "灯", 0), ErrorCodes.InvalidRequest);
        }

        private static void FreeTextUsesMockBridgeOnly()
        {
            var evidence = TestData.CreateRegistry("E01");
            var provider = new MockAiProvider(TestData.MockScenarios);
            var engine = TestData.CreateEngine(evidence, provider);
            var turn = engine.StartSession("npc_laozhou");

            var completed = engine.SubmitFreeText(turn.ConversationId, "灯");
            Assert.Null(completed.FallbackReason);
            Assert.NotNull(completed.GeneratedBridge);
            Assert.Contains("模拟回复", completed.GeneratedBridge);
            Assert.Equal("node.laozhou.opening", completed.NodeId, "自由文本不得跳转节点。");

            var invalid = engine.SubmitFreeText(turn.ConversationId, "坏输出测试");
            Assert.Equal(NpcAiFallbackReasons.InvalidOutput, invalid.FallbackReason);
            Assert.Null(invalid.GeneratedBridge);

            var unsafeOutput = engine.SubmitFreeText(turn.ConversationId, "不安全测试");
            Assert.Equal(NpcAiFallbackReasons.UnsafeOutput, unsafeOutput.FallbackReason);

            var linyao = engine.StartSession("npc_linyao");
            var unknown = engine.SubmitFreeText(linyao.ConversationId, "天气怎么样");
            Assert.Equal(NpcAiFallbackReasons.UnknownIntent, unknown.FallbackReason);
        }

        private static void SessionLifecycleAndExpiry()
        {
            var engine = TestData.CreateEngine(TestData.CreateRegistry());
            var first = engine.StartSession("npc_laozhou");
            var second = engine.StartSession("npc_linyao");

            Assert.Equal(DialogueSessionStatus.Closed, engine.GetSession(first.ConversationId).Status);
            Assert.Equal(DialogueSessionStatus.Open, engine.GetSession(second.ConversationId).Status);
            Assert.ContractCode(() => engine.Choose(first.ConversationId, "opt.laozhou.leave"), ErrorCodes.TurnExpired);

            var expired = engine.ExpireOpenSessions();
            Assert.SequenceEqual(new[] { second.ConversationId }, expired);
            Assert.Equal(DialogueSessionStatus.Expired, engine.GetSession(second.ConversationId).Status);
            Assert.ContractCode(() => engine.GetAvailableOptions(second.ConversationId), ErrorCodes.TurnExpired);

            Assert.ContractCode(() => engine.StartSession("npc_xucheng"), ErrorCodes.NotFound);
            Assert.ContractCode(() => engine.StartSession("laozhou"), ErrorCodes.InvalidRequest);
        }

        private static void CatalogJsonRejectsAnomalies()
        {
            Assert.Throws<JsonDataException>(() => DialogueCatalogJson.Parse("{"));
            Assert.Throws<JsonDataException>(() => DialogueCatalogJson.Parse("{\"content_version\":\"v\",\"npcs\":[]}"));

            const string unknownMember = "{\"content_version\":\"story-v1.0-phase2\",\"npcs\":[{" +
                "\"npc_id\":\"npc_laozhou\",\"display_name\":\"x\",\"opening_node_id\":\"node.a\"," +
                "\"allowed_evidence_ids\":[\"E01\"],\"nodes\":[{\"node_id\":\"node.a\",\"content_ref\":\"c\",\"text\":\"t\",\"options\":[]}]," +
                "\"disclosures\":[],\"bogus\":1}]}";
            Assert.Throws<JsonDataException>(() => DialogueCatalogJson.Parse(unknownMember));

            const string unknownKind = "{\"content_version\":\"story-v1.0-phase2\",\"npcs\":[{" +
                "\"npc_id\":\"npc_laozhou\",\"display_name\":\"x\",\"opening_node_id\":\"node.a\"," +
                "\"allowed_evidence_ids\":[\"E01\"],\"nodes\":[{\"node_id\":\"node.a\",\"content_ref\":\"c\",\"text\":\"t\"," +
                "\"options\":[{\"option_id\":\"o\",\"label\":\"l\",\"kind\":\"magic\",\"target_node_id\":\"node.a\"}]}]," +
                "\"disclosures\":[]}]}";
            Assert.Throws<JsonDataException>(() => DialogueCatalogJson.Parse(unknownKind));

            var duplicateNpc = "{\"content_version\":\"story-v1.0-phase2\",\"npcs\":[" +
                NpcFragment("npc_laozhou") + "," + NpcFragment("npc_laozhou") + "]}";
            Assert.Throws<JsonDataException>(() => DialogueCatalogJson.Parse(duplicateNpc));
        }

        private static string NpcFragment(string npcId)
        {
            return "{\"npc_id\":\"" + npcId + "\",\"display_name\":\"x\",\"opening_node_id\":\"node.a\"," +
                   "\"allowed_evidence_ids\":[\"E01\"],\"nodes\":[{\"node_id\":\"node.a\",\"content_ref\":\"c\"," +
                   "\"text\":\"t\",\"options\":[]}],\"disclosures\":[]}";
        }

        private static bool HasOption(IReadOnlyList<DialogueOptionView> options, string optionId)
        {
            foreach (var option in options)
            {
                if (option.OptionId == optionId) return true;
            }

            return false;
        }

        private static DialogueSegment FindSegment(IReadOnlyList<DialogueSegment> segments, string contentRef)
        {
            foreach (var segment in segments)
            {
                if (segment.ContentRef == contentRef) return segment;
            }

            throw new AssertionException("找不到 content_ref=" + contentRef + " 的固定段落。");
        }
    }
}
