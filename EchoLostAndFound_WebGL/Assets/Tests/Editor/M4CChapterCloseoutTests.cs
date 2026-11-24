using EchoStation;
using NUnit.Framework;
using UnityEngine;

namespace EchoLostAndFound.QA
{
    public sealed class M4CChapterCloseoutTests
    {
        StationInvestigation game;
        string previousSave;
        bool hadSave;

        [SetUp]
        public void OpenSeparateInvestigation()
        {
            hadSave = PlayerPrefs.HasKey(StationInvestigation.SaveKey);
            previousSave = PlayerPrefs.GetString(StationInvestigation.SaveKey);
            PlayerPrefs.DeleteKey(StationInvestigation.SaveKey);
            Reload();
        }

        [TearDown]
        public void RestorePlayerSave()
        {
            if (hadSave) PlayerPrefs.SetString(StationInvestigation.SaveKey, previousSave);
            else PlayerPrefs.DeleteKey(StationInvestigation.SaveKey);
            PlayerPrefs.Save();
        }

        void Reload() => game = new StationInvestigation();

        void ReadCard(string id)
        {
            foreach (var field in game.Evidence.Catalog.Get(id).RequiredFieldIds)
                game.Observe(game.Evidence.ObserveField(field));
        }

        void CompareDocumentsWith(string npc)
        {
            var session = game.Dialogue.StartSession(npc).ConversationId;
            game.Dialogue.PresentEvidence(session, new[] { "E03" });
            var compared = game.Dialogue.PresentEvidence(session, new[] { "E04" });
            Assert.That(compared.TriggeredDisclosureIds, Does.Contain("D02"));
            game.Dialogue.CloseSession(session);
        }

        [Test]
        public void BagRequiresRegisteredWatchAndExplicitConfirmation()
        {
            game.Observe(game.Evidence.ObserveField("watch.dial"));
            Assert.That(game.CommitCustody(false, null, true), Is.False);
            Reload();
            Assert.That(game.Evidence.IsFieldObserved("watch.dial"), Is.True);
            Assert.That(game.Evidence.HasEvidence("E01"), Is.False);

            ReadCard("E01");
            Assert.That(game.CommitCustody(false, null, false), Is.False);
            Reload();
            Assert.That(game.Custody, Is.Null.Or.Empty);
            Assert.That(game.CommitCustody(false, null, true), Is.True);
            Reload();
            Assert.That(game.Custody, Is.EqualTo("sealed_pending"));
            Assert.That(game.Evidence.AcquiredEvidenceIds, Is.EquivalentTo(new[] { "E01" }));
            Assert.That(game.OwnerProven, Is.False);
            Assert.That(game.LinyaoVerified, Is.False);

            var receiptSave = PlayerPrefs.GetString(StationInvestigation.SaveKey);
            game.CommitCustody(false, null, true);
            game.CommitCustody(true, "npc_linyao", true);
            Assert.That(PlayerPrefs.GetString(StationInvestigation.SaveKey), Is.EqualTo(receiptSave),
                "Repeat clicks and a conflicting choice must preserve the committed receipt and checkpoint.");
        }

        [TestCase("E01")]
        [TestCase("E03")]
        [TestCase("E04")]
        public void CorrectOwnerConclusionNeedsEveryDocument(string missing)
        {
            foreach (var id in new[] { "E01", "E03", "E04" })
                if (id != missing) ReadCard(id);
            Assert.That(game.SubmitOwner(true), Is.False);
            Reload();
            Assert.That(game.OwnerProven, Is.False);
            Assert.That(game.CommitCustody(true, "npc_linyao", true), Is.False);
        }

        [Test]
        public void HandoverRequiresPlayersConclusionAndLinyaosOwnDisclosureAndSignature()
        {
            ReadCard("E01");
            ReadCard("E03");
            ReadCard("E04");
            Assert.That(game.SubmitOwner(false), Is.False);
            Assert.That(game.OwnerProven, Is.False);
            Assert.That(game.SubmitOwner(true), Is.True);
            CompareDocumentsWith("npc_laozhou");
            Reload();
            Assert.That(game.OwnerProven, Is.True);
            Assert.That(game.LinyaoVerified, Is.False);
            var firstVisit = game.Dialogue.StartSession("npc_linyao").ConversationId;
            Assert.That(game.CommitCustody(true, "npc_linyao", true), Is.False);
            game.Dialogue.CloseSession(firstVisit);
            CompareDocumentsWith("npc_linyao");
            Reload();
            Assert.That(game.LinyaoVerified, Is.True);
            Assert.That(game.CommitCustody(true, "npc_linyao", true), Is.False,
                "A persisted disclosure does not establish a live handover context.");
            game.Dialogue.StartSession("npc_linyao");
            Assert.That(game.CanHandover, Is.True);
            Assert.That(game.CommitCustody(true, "npc_laozhou", true), Is.False);
            Assert.That(game.CommitCustody(true, "npc_linyao", false), Is.False);
            Assert.That(game.Custody, Is.Null.Or.Empty);
            Assert.That(game.CommitCustody(true, "npc_linyao", true), Is.True);
            Reload();
            Assert.That(game.Custody, Is.EqualTo("linyao_temporary"));
            Assert.That(game.Evidence.FindVisibleRecord("E01"), Is.Not.Null);

            ReadCard("E02");
            game.ReadIndex();
            Reload();
            Assert.That(game.IndexRead, Is.True);
            Assert.That(game.Evidence.HasEvidence("E02"), Is.True);
            Assert.That(game.RestorePreChoice(), Is.True);
            Reload();
            Assert.That(game.Custody, Is.Null.Or.Empty);
            Assert.That(game.LinyaoVerified, Is.True);
            Assert.That(game.OwnerProven, Is.True);
            Assert.That(game.IndexRead, Is.False);
            Assert.That(game.Evidence.AcquiredEvidenceIds, Is.EquivalentTo(new[] { "E01", "E03", "E04" }));
            Assert.That(game.CommitCustody(false, null, true), Is.True);
            Reload();
            Assert.That(game.Custody, Is.EqualTo("sealed_pending"));
        }

        [Test]
        public void LinyaosKnowledgeAloneDoesNotSolveR01()
        {
            ReadCard("E01");
            ReadCard("E03");
            ReadCard("E04");
            CompareDocumentsWith("npc_linyao");
            Reload();
            Assert.That(game.LinyaoVerified, Is.True);
            Assert.That(game.OwnerProven, Is.False);
            game.Dialogue.StartSession("npc_linyao");
            Assert.That(game.CanHandover, Is.False);
            Assert.That(game.CommitCustody(true, "npc_linyao", true), Is.False);
        }

        [Test]
        public void LegacySnapshotKeepsPartialWatchAndDoesNotInventAChoice()
        {
            game.Observe(game.Evidence.ObserveField("watch.serial_number"));
            ReadCard("E03");
            PlayerPrefs.SetString(StationInvestigation.SaveKey, game.Evidence.CreateSnapshot().ToJson(false));
            Reload();
            Assert.That(game.Evidence.IsFieldObserved("watch.serial_number"), Is.True);
            Assert.That(game.Evidence.AcquiredEvidenceIds, Is.EquivalentTo(new[] { "E03" }));
            Assert.That(game.Custody, Is.Null.Or.Empty);
            Assert.That(game.OwnerProven, Is.False);
            ReadCard("E01");
            Assert.That(game.CommitCustody(false, null, true), Is.True);
            Reload();
            Assert.That(game.Custody, Is.EqualTo("sealed_pending"));
            Assert.That(game.Evidence.AcquiredEvidenceIds, Is.EquivalentTo(new[] { "E01", "E03" }));
        }
    }
}
