using System.Collections.Generic;
using System.Linq;
using EchoLostAndFound.Dialogue;
using EchoLostAndFound.Evidence;
using EchoLostAndFound.M2;
using EchoLostAndFound.MockAi;
using EchoLostAndFound.Shared.Contracts;
using EchoStation;
using NUnit.Framework;
using UnityEngine;

namespace EchoLostAndFound.QA
{
    /// <summary>
    /// M4-C chapter-01 investigation slice: routing, scene gates and the disclosure branches
    /// that the map ties to E03/E04/E05. The scene itself is covered by the PlayMode tests.
    /// </summary>
    public sealed class M4CInvestigationTests
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

        void ObserveCard(string evidenceId)
        {
            evidence.ObserveFields(catalog.Get(evidenceId).RequiredFieldIds);
        }

        [Test]
        public void SceneLabelsRouteOnlyWhenLabelAndKindMatch()
        {
            Assert.That(StationTargets.Resolve("怀表", InteractionKind.Item), Is.EqualTo(StationTarget.Watch));
            Assert.That(StationTargets.Resolve("维修柜", InteractionKind.Document), Is.EqualTo(StationTarget.Cabinet));
            Assert.That(StationTargets.Resolve("失物包", InteractionKind.Document), Is.EqualTo(StationTarget.LostPackage));
            Assert.That(StationTargets.Resolve("副联册", InteractionKind.Document), Is.EqualTo(StationTarget.Binder));
            Assert.That(StationTargets.Resolve("老周", InteractionKind.Npc), Is.EqualTo(StationTarget.Laozhou));
            Assert.That(StationTargets.Resolve("林遥", InteractionKind.Npc), Is.EqualTo(StationTarget.Linyao));

            Assert.That(StationTargets.Resolve("怀表", InteractionKind.Npc), Is.EqualTo(StationTarget.Unknown));
            Assert.That(StationTargets.Resolve("林遥", InteractionKind.Counter), Is.EqualTo(StationTarget.Unknown));
            Assert.That(StationTargets.Resolve(" 林遥 ", InteractionKind.Npc), Is.EqualTo(StationTarget.Linyao));
            Assert.That(StationTargets.Resolve("不存在的物件", InteractionKind.Document), Is.EqualTo(StationTarget.Unknown));
            Assert.That(StationTargets.Resolve(null, InteractionKind.Item), Is.EqualTo(StationTarget.Unknown));

            Assert.That(StationTargets.NpcId(StationTarget.Linyao), Is.EqualTo("npc_linyao"));
            Assert.That(StationTargets.NpcId(StationTarget.Laozhou), Is.EqualTo("npc_laozhou"));
            Assert.That(StationTargets.NpcId(StationTarget.Watch), Is.Null);
            Assert.That(StationTargets.EvidenceId(StationTarget.Binder), Is.EqualTo("E04"));
            Assert.That(StationTargets.EvidenceId(StationTarget.Linyao), Is.Null);
        }

        [Test]
        public void WatchPartsCanBeReadInAnyOrderAndRegisterE01WhenComplete()
        {
            var definition = catalog.Get("E01");
            Assert.That(definition.Fields.Select(field => field.Label),
                Is.EquivalentTo(new[] { "表盘", "背刻", "编号", "侧冠", "冠轴损伤" }));
            Assert.That(definition.Fields.Select(field => field.DisplayText).Distinct().Count(),
                Is.EqualTo(definition.Fields.Count));

            var scrambled = new[]
            {
                "watch.crown_shaft_damage", "watch.side_crown", "watch.serial_number",
                "watch.back_engraving", "watch.dial"
            };
            foreach (var fieldId in scrambled)
            {
                Assert.That(evidence.FindVisibleRecord("E01"), Is.Null, "E01 showed up early on " + fieldId);
                evidence.ObserveField(fieldId);
            }

            var card = evidence.FindVisibleRecord("E01");
            Assert.That(card, Is.Not.Null);
            Assert.That(card.ObservedFieldIds, Is.EquivalentTo(scrambled));
            Assert.That(card.FixedText, Does.Contain("21:17"));
            Assert.That(evidence.IsFieldObserved(StationInvestigationGates.SerialNumberField), Is.True);
        }

        [Test]
        public void PackageAndBinderOpenOnlyAfterTheSerialNumberIsObserved()
        {
            Assert.That(StationInvestigationGates.CanReadRepairReceipt(evidence), Is.False);
            Assert.That(StationInvestigationGates.CanReadDesignatedReceipt(evidence), Is.False);

            evidence.ObserveField(StationInvestigationGates.EngravingField);
            Assert.That(StationInvestigationGates.CanReadRepairReceipt(evidence), Is.False,
                "the engraving must not unlock the receipt; only the serial number does");

            evidence.ObserveField(StationInvestigationGates.SerialNumberField);
            Assert.That(StationInvestigationGates.CanReadRepairReceipt(evidence), Is.True);
            Assert.That(StationInvestigationGates.CanReadDesignatedReceipt(evidence), Is.True);

            Assert.That(evidence.FindVisibleRecord("E03"), Is.Null);
            Assert.That(evidence.FindVisibleRecord("E04"), Is.Null);
            ObserveCard("E03");
            ObserveCard("E04");
            Assert.That(evidence.HasEvidence("E03"), Is.True);
            Assert.That(evidence.HasEvidence("E04"), Is.True);
            Assert.That(StationInvestigationGates.CanReadRepairReceipt(null), Is.False);
            Assert.That(StationInvestigationGates.CanReadDesignatedReceipt(null), Is.False);
        }

        [Test]
        public void PickupInspectionNeedsTheFaultCardIndexNotTheFrontCard()
        {
            Assert.That(StationInvestigationGates.CanReadPickupInspection(false), Is.False);
            Assert.That(StationInvestigationGates.CanReadPickupInspection(true), Is.True);

            ObserveCard("E02");
            Assert.That(evidence.HasEvidence("E02"), Is.True);
            Assert.That(evidence.FindVisibleRecord("E05"), Is.Null,
                "reading the fault card front is not the same as reading the back-page index");
            Assert.That(StationInvestigationGates.CanReadPickupInspection(false), Is.False);

            ObserveCard("E05");
            Assert.That(evidence.HasEvidence("E05"), Is.True);
        }

        [Test]
        public void LinyaoOnlyRecognisesTheEngravingOnceTheWatchIsComplete()
        {
            // REC.engraving needs E01 plus the observed 背刻; the card cannot register
            // until every part is looked at, so 林遥 has nothing to compare before that.
            var conversation = dialogue.StartSession("npc_linyao").ConversationId;
            foreach (var fieldId in catalog.Get("E01").RequiredFieldIds
                         .Where(id => id != StationInvestigationGates.EngravingField))
                evidence.ObserveField(fieldId);

            Assert.That(StationInvestigationGates.CanAskEngraving(evidence), Is.False);
            Assert.That(evidence.FindVisibleRecord("E01"), Is.Null);
            var blocked = Assert.Throws<GameContractException>(
                () => dialogue.PresentEvidence(conversation, new[] { "E01" }));
            Assert.That(blocked.Code, Is.EqualTo(ErrorCodes.PreconditionFailed));

            evidence.ObserveField(StationInvestigationGates.EngravingField);
            Assert.That(StationInvestigationGates.CanAskEngraving(evidence), Is.True);
            var result = dialogue.PresentEvidence(conversation, new[] { "E01" });
            Assert.That(result.TriggeredDisclosureIds, Is.EqualTo(new[] { "REC.engraving" }));
            StringAssert.Contains("四月十二", string.Join("\n", result.Segments.Select(segment => segment.Text)));
        }

        [Test]
        public void D03NeedsE01AndE05AndNeverFiresTwice()
        {
            var conversation = dialogue.StartSession("npc_laozhou").ConversationId;
            ObserveCard("E01");
            Assert.That(dialogue.PresentEvidence(conversation, new[] { "E01" }).TriggeredDisclosureIds, Is.Empty);

            ObserveCard("E05");
            var result = dialogue.PresentEvidence(conversation, new[] { "E05" });
            Assert.That(result.TriggeredDisclosureIds, Is.EqualTo(new[] { "D03" }));
            StringAssert.Contains("冠头是歪的", string.Join("\n", result.Segments.Select(segment => segment.Text)));

            Assert.That(dialogue.PresentEvidence(conversation, new[] { "E01", "E05" }).AlreadyPresented, Is.True);
            Assert.That(dialogue.PresentEvidence(conversation, new[] { "E01" }).TriggeredDisclosureIds, Is.Empty);
        }

        [Test]
        public void D02HasOneBranchPerNpcAndConsumesE03AndE04()
        {
            ObserveCard("E03");
            ObserveCard("E04");

            var laozhou = dialogue.StartSession("npc_laozhou");
            var registry = dialogue.PresentEvidence(laozhou.ConversationId, new[] { "E03", "E04" });
            Assert.That(registry.TriggeredDisclosureIds, Is.EqualTo(new[] { "D02" }));

            var linyao = dialogue.StartSession("npc_linyao");
            var clerk = dialogue.PresentEvidence(linyao.ConversationId, new[] { "E03", "E04" });
            Assert.That(clerk.TriggeredDisclosureIds, Is.EqualTo(new[] { "D02" }));
            StringAssert.Contains("是我妈妈", string.Join("\n", clerk.Segments.Select(segment => segment.Text)));
        }

        [Test]
        public void WholeChapterCanBeCollectedThroughSceneTargetsOnly()
        {
            // No evidence is granted directly: every card is reached through an approved
            // scene target plus the gate that target is supposed to honour.
            var watch = StationTargets.Resolve("怀表", InteractionKind.Item);
            foreach (var fieldId in catalog.Get(StationTargets.EvidenceId(watch)).RequiredFieldIds)
                evidence.ObserveField(fieldId);

            var cabinet = StationTargets.Resolve("维修柜", InteractionKind.Document);
            ObserveCard(StationTargets.EvidenceId(cabinet));
            Assert.That(StationInvestigationGates.CanReadPickupInspection(true), Is.True);
            ObserveCard("E05");

            var package = StationTargets.Resolve("失物包", InteractionKind.Document);
            Assert.That(StationInvestigationGates.CanReadRepairReceipt(evidence), Is.True);
            ObserveCard(StationTargets.EvidenceId(package));

            var binder = StationTargets.Resolve("副联册", InteractionKind.Document);
            Assert.That(StationInvestigationGates.CanReadDesignatedReceipt(evidence), Is.True);
            ObserveCard(StationTargets.EvidenceId(binder));

            Assert.That(evidence.AcquiredEvidenceIds, Is.EquivalentTo(new[] { "E01", "E02", "E03", "E04", "E05" }));

            var laozhou = dialogue.StartSession(StationTargets.NpcId(StationTarget.Laozhou)).ConversationId;
            Assert.That(dialogue.PresentEvidence(laozhou, new[] { "E02" }).TriggeredDisclosureIds, Is.EqualTo(new[] { "D01" }));
            Assert.That(dialogue.PresentEvidence(laozhou, new[] { "E01", "E05" }).TriggeredDisclosureIds, Is.EqualTo(new[] { "D03" }));
            Assert.That(dialogue.PresentEvidence(laozhou, new[] { "E03", "E04" }).TriggeredDisclosureIds, Is.EqualTo(new[] { "D02" }));

            var linyao = dialogue.StartSession(StationTargets.NpcId(StationTarget.Linyao)).ConversationId;
            Assert.That(dialogue.PresentEvidence(linyao, new[] { "E01" }).TriggeredDisclosureIds, Does.Contain("REC.engraving"));
            Assert.That(dialogue.PresentEvidence(linyao, new[] { "E03", "E04" }).TriggeredDisclosureIds, Is.EqualTo(new[] { "D02" }));
        }

        [Test]
        public void EvidenceStillPersistsAndContentVersionIsChecked()
        {
            ObserveCard("E01");
            var snapshot = evidence.CreateSnapshot().ToJson();
            var restored = new EvidenceRegistry(catalog, EvidenceSnapshot.ParseAndValidate(catalog, snapshot));
            Assert.That(restored.AcquiredEvidenceIds, Is.EqualTo(new[] { "E01" }));
            Assert.That(catalog.ContentVersion, Is.EqualTo("story-v1.0-phase2"));

            var cards = new HashSet<string>(evidence.GetVisibleEvidenceRecords().Select(record => record.EvidenceId));
            Assert.That(cards, Is.EquivalentTo(new[] { "E01" }));
        }
    }
}
