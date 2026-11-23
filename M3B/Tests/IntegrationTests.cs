using System;
using EchoLostAndFound.Dialogue;
using EchoLostAndFound.Evidence;
using EchoLostAndFound.MockAi;
using EchoLostAndFound.Shared.Ai;

namespace EchoLostAndFound.Tests
{
    /// <summary>
    /// End-to-end flow matching the sequence documented in IntegrationGuide.md:
    /// load content, acquire evidence, talk to an NPC offline, present evidence,
    /// use the mock AI bridge, snapshot, restore and expire sessions.
    /// </summary>
    internal static class IntegrationTests
    {
        public static void Register(TestRegistry registry)
        {
            registry.Add("Integration_OfflineInvestigationFlow", OfflineInvestigationFlow);
        }

        private static void OfflineInvestigationFlow()
        {
            // 1. Content is loaded from disk once; both catalogs must share the content version.
            var evidenceCatalog = TestData.EvidenceCatalog;
            var dialogueCatalog = TestData.DialogueCatalog;
            Assert.Equal(evidenceCatalog.ContentVersion, dialogueCatalog.ContentVersion);
            Assert.Equal("story-v1.0-phase2", evidenceCatalog.ContentVersion);

            // 2. The registry owns evidence state; observing every field of a card acquires it.
            var evidence = new EvidenceRegistry(evidenceCatalog, new SequentialIdGenerator());
            evidence.ObserveFields(evidenceCatalog.Get("E01").RequiredFieldIds);
            evidence.ObserveFields(evidenceCatalog.Get("E02").RequiredFieldIds);
            Assert.True(evidence.HasEvidence("E01"));
            Assert.True(evidence.HasEvidence("E02"));
            Assert.Equal(2, evidence.AcquiredEvidenceIds.Count);

            // 3. Offline dialogue: fixed lines require no provider at all.
            var offlineEngine = new DialogueEngine(dialogueCatalog, evidence, new SequentialIdGenerator());
            var session = offlineEngine.StartSession("npc_laozhou");
            Assert.Equal("这封从旧库搬过两回。我来对号，你来签。先看表背，失物只认号。", session.Segments[0].Text);

            var b01 = offlineEngine.Choose(session.ConversationId, "opt.laozhou.ask_b01");
            Assert.Equal("站台那晚在我印象里一直亮着。我还把那盏油灯拖到里头去了。", b01.Segments[0].Text);

            var presented = offlineEngine.PresentEvidence(session.ConversationId, new[] { "E02" });
            Assert.Equal(1, presented.TriggeredDisclosureIds.Count);
            Assert.Equal("D01", presented.TriggeredDisclosureIds[0]);
            Assert.Equal("进水，二十一点十七。我的灯到二十才摆好。是黑过，中间那点我记混了。", presented.Segments[0].Text);

            // 4. The same state can be wired to the mock AI provider for free-text turns.
            var mockProvider = new MockAiProvider(TestData.MockScenarios);
            var engine = new DialogueEngine(dialogueCatalog, evidence, new SequentialIdGenerator(), mockProvider);
            var aiSession = engine.StartSession("npc_laozhou");
            var acquiredBefore = evidence.AcquiredEvidenceIds.Count;
            var reply = engine.SubmitFreeText(aiSession.ConversationId, "灯");
            Assert.Null(reply.FallbackReason);
            Assert.Contains("模拟回复", reply.GeneratedBridge);
            Assert.True(mockProvider.Generate(new NpcAiRequest(
                "probe", "npc_laozhou", "灯", evidence.AcquiredEvidenceIds,
                new[] { "opt.laozhou.ask_b01" }, 3000, evidence.ContentVersion)).IsSynthetic);
            // AI output never mutates evidence state.
            Assert.Equal(acquiredBefore, evidence.AcquiredEvidenceIds.Count);

            // 5. Snapshot round-trip and restore-time session expiry.
            var snapshotJson = evidence.CreateSnapshot().ToJson();
            var restored = EvidenceSnapshot.ParseAndValidate(evidenceCatalog, snapshotJson);
            var restoredRegistry = new EvidenceRegistry(evidenceCatalog, restored, new SequentialIdGenerator());
            Assert.True(restoredRegistry.HasEvidence("E01"));
            Assert.True(restoredRegistry.HasEvidence("E02"));
            Assert.Equal(evidence.ObservedFieldIds.Count, restoredRegistry.ObservedFieldIds.Count);

            var restoredEngine = new DialogueEngine(dialogueCatalog, restoredRegistry, new SequentialIdGenerator());
            var stale = restoredEngine.StartSession("npc_laozhou");
            restoredEngine.ExpireOpenSessions();
            Assert.Equal(DialogueSessionStatus.Expired, restoredEngine.GetSession(stale.ConversationId).Status);
            Assert.ContractCode(
                () => restoredEngine.Choose(stale.ConversationId, "opt.laozhou.ask_b01"),
                EchoLostAndFound.Shared.Contracts.ErrorCodes.TurnExpired);
        }
    }
}
