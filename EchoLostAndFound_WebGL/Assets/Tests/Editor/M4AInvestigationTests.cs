using System.Collections.Generic;
using System.Linq;
using EchoLostAndFound.Dialogue;
using EchoLostAndFound.Evidence;
using EchoLostAndFound.MockAi;
using EchoLostAndFound.Shared.Contracts;
using NUnit.Framework;
using UnityEngine;

namespace EchoLostAndFound.QA
{
    public sealed class M4AInvestigationTests
    {
        EvidenceCatalog catalog;
        EvidenceRegistry evidence;
        DialogueEngine dialogue;

        static string Content(string name)
        {
            var asset = Resources.Load<TextAsset>("M3B/" + name);
            Assert.That(asset, Is.Not.Null, name);
            return asset.text;
        }

        [SetUp]
        public void LoadShippedContent()
        {
            catalog = EvidenceCatalogJson.Parse(Content("ch01_evidence"));
            var lines = DialogueCatalogJson.Parse(Content("ch01_dialogue"));
            var fixtures = MockAiScenarioJson.Parse(Content("mock_ai_fixtures"));
            Assert.That(new[] { catalog.ContentVersion, lines.ContentVersion, fixtures.ContentVersion },
                Is.All.EqualTo("story-v1.0-phase2"));
            evidence = new EvidenceRegistry(catalog);
            dialogue = new DialogueEngine(lines, evidence, new GuidIdGenerator(), new MockAiProvider(fixtures));
        }

        [Test]
        public void WatchNeedsAllFiveFieldsAndRecheckingEmitsNoDuplicateEvents()
        {
            var fields = catalog.Get("E01").RequiredFieldIds;
            Assert.That(fields.Count, Is.EqualTo(5));
            var events = new List<EvidenceStateChangedEvent>();
            evidence.StateChanged += events.Add;
            evidence.ObserveFields(fields.Take(4).ToArray());
            Assert.That(evidence.FindVisibleRecord("E01"), Is.Null);
            evidence.ObserveField(fields.Last());
            var card = evidence.FindVisibleRecord("E01");
            Assert.That(card.FixedText, Does.Contain("21:17"));
            var eventCount = events.Count;
            Assert.That(evidence.ObserveFields(fields).Changed, Is.False);
            Assert.That(evidence.RegisterEvidence("E01").AlreadyRegistered, Is.True);
            Assert.That(events.Count, Is.EqualTo(eventCount));
            Assert.That(events.Count(e => e.EventType == EvidenceEventTypes.Registered), Is.EqualTo(1));
            Assert.That(events.Select(e => e.EventId).Distinct().Count(), Is.EqualTo(events.Count));
        }

        [Test]
        public void PresentationHonoursMaterialAndNpcAndUnlocksD01OnlyOnce()
        {
            var events = new List<DialogueResultEvent>();
            dialogue.EventRaised += events.Add;
            var id = dialogue.StartSession("npc_laozhou").ConversationId;
            Assert.That(Assert.Throws<GameContractException>(() => dialogue.PresentEvidence(id, new[] {"E02"})).Code,
                Is.EqualTo(ErrorCodes.PreconditionFailed));
            evidence.ObserveFields(catalog.Get("E01").RequiredFieldIds);
            Assert.That(dialogue.PresentEvidence(id, new[] {"E01"}).TriggeredDisclosureIds, Is.Empty);
            Assert.That(dialogue.GetAvailableOptions(id).Select(o => o.OptionId), Does.Not.Contain("opt.laozhou.repeat_b01"));
            evidence.ObserveFields(catalog.Get("E02").RequiredFieldIds);
            var result = dialogue.PresentEvidence(id, new[] {"E02"});
            Assert.That(result.TriggeredDisclosureIds, Is.EqualTo(new[] {"D01"}));
            Assert.That(result.Segments.Single().Text, Is.EqualTo("进水，二十一点十七。我的灯到二十才摆好。是黑过，中间那点我记混了。"));
            Assert.That(dialogue.GetAvailableOptions(id).Select(o => o.OptionId), Does.Contain("opt.laozhou.repeat_b01"));
            Assert.That(dialogue.PresentEvidence(id, new[] {"E02"}).AlreadyPresented, Is.True);
            var next = dialogue.StartSession("npc_linyao").ConversationId;
            Assert.That(dialogue.GetSession(id).Status, Is.EqualTo(DialogueSessionStatus.Closed));
            Assert.That(Assert.Throws<GameContractException>(() => dialogue.PresentEvidence(next, new[] {"E02"})).Code,
                Is.EqualTo(ErrorCodes.PreconditionFailed));
            Assert.That(events.Count(e => e.DisclosureId == "D01" && e.EventType == DialogueEventTypes.DisclosureTriggered), Is.EqualTo(1));
        }

        [Test]
        public void TimeoutPreservesNodeAndSnapshotAndRestoreRejectsInvalidEvidence()
        {
            evidence.ObserveField("watch.serial_number");
            var snapshot = evidence.CreateSnapshot().ToJson();
            var first = dialogue.StartSession("npc_laozhou");
            var failed = dialogue.SubmitFreeText(first.ConversationId, "超时测试");
            Assert.That(failed.FallbackReason, Is.EqualTo("timeout"));
            Assert.That(failed.GeneratedBridge, Is.Null);
            Assert.That(failed.NodeId, Is.EqualTo(first.NodeId));
            Assert.That(evidence.CreateSnapshot().ToJson(), Is.EqualTo(snapshot));
            var restored = new EvidenceRegistry(catalog, EvidenceSnapshot.ParseAndValidate(catalog, snapshot));
            Assert.That(restored.ObservedFieldIds, Is.EqualTo(new[] {"watch.serial_number"}));
            Assert.That(restored.AcquiredEvidenceIds, Is.Empty);
            var corrupt = new EvidenceSnapshot(catalog.ContentVersion, new string[0], new[] {"E01"});
            Assert.That(Assert.Throws<GameContractException>(() => corrupt.Validate(catalog)).Code, Is.EqualTo(ErrorCodes.SaveCorrupt));
            dialogue.ExpireOpenSessions();
            Assert.That(Assert.Throws<GameContractException>(() => dialogue.Choose(first.ConversationId, "opt.laozhou.ask_b01")).Code,
                Is.EqualTo(ErrorCodes.TurnExpired));
        }
    }
}
