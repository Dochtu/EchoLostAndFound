using System;
using System.Linq;
using EchoLostAndFound.Dialogue;
using EchoLostAndFound.Evidence;
using EchoLostAndFound.MockAi;
using EchoLostAndFound.Shared.Json;
using UnityEngine;

[assembly: System.Runtime.CompilerServices.InternalsVisibleTo("M3A.EditMode")]

namespace EchoStation
{
    // One PlayerPrefs value contains the live investigation and both A02 checkpoints.
    internal sealed class StationInvestigation
    {
        internal const string SaveKey = "EchoStation.M4A.evidence.v1";
        const string Linyao = "npc_linyao";
        static readonly string[] Npcs = { Linyao, "npc_laozhou" };
        readonly EvidenceCatalog catalog;
        readonly DialogueCatalog lines;
        readonly MockAiProvider mock;
        JsonObject preChoice, chapterEnd;
        bool preserveInvalidSave;
        string activeNpc;
        internal EvidenceRegistry Evidence { get; private set; }
        internal DialogueEngine Dialogue { get; private set; }
        internal string SaveNotice { get; private set; }
        internal bool OwnerProven { get; private set; }
        internal bool IndexRead { get; private set; }
        internal string Custody { get; private set; }
        internal bool LinyaoVerified => Dialogue.PlayedDisclosures(Linyao).Contains("D02");
        internal bool CanHandover => OwnerProven && LinyaoVerified && string.IsNullOrEmpty(Custody);
        bool HasOwnerEvidence => Evidence.HasEvidence("E01") && Evidence.HasEvidence("E03") && Evidence.HasEvidence("E04");

        internal StationInvestigation()
        {
            catalog = EvidenceCatalogJson.Parse(Content("ch01_evidence"));
            lines = DialogueCatalogJson.Parse(Content("ch01_dialogue"));
            var fixtures = MockAiScenarioJson.Parse(Content("mock_ai_fixtures"));
            if (catalog.ContentVersion != "story-v1.0-phase2" || lines.ContentVersion != catalog.ContentVersion ||
                fixtures.ContentVersion != catalog.ContentVersion)
                throw new InvalidOperationException("调查内容版本不一致");
            mock = new MockAiProvider(fixtures);
            if (PlayerPrefs.HasKey(SaveKey))
            {
                try
                {
                    var raw = PlayerPrefs.GetString(SaveKey);
                    var root = JsonContract.RequireObject(JsonValue.Parse(raw), "$");
                    if (!root.ContainsKey("chapter_save"))
                        Reset(EvidenceSnapshot.ParseAndValidate(catalog, raw));
                    else
                    {
                        if (JsonContract.RequireInt(root, "chapter_save", "$") != 1)
                            throw new FormatException("调查存档版本不支持");
                        preChoice = root["pre_choice"] as JsonObject;
                        chapterEnd = root["chapter_end"] as JsonObject;
                        if ((preChoice == null) != (chapterEnd == null)) throw new FormatException();
                        if (preChoice != null)
                        {
                            LoadFrame(preChoice);
                            if (!string.IsNullOrEmpty(Custody) || !Evidence.HasEvidence("E01")) throw new FormatException();
                            LoadFrame(chapterEnd);
                            if (string.IsNullOrEmpty(Custody)) throw new FormatException();
                        }
                        string savedChoice = Custody;
                        LoadFrame(JsonContract.RequireObject(root["current"], "current"));
                        if (!string.Equals(savedChoice, Custody)) throw new FormatException();
                    }
                    return;
                }
                catch (Exception ex)
                {
                    SaveNotice = "存档读取失败，本次调查暂不保存。";
                    preserveInvalidSave = true;
                    Debug.LogWarning("M4C investigation snapshot rejected: " + ex.GetType().Name);
                }
            }
            preChoice = chapterEnd = null;
            Reset(null);
        }

        static string Content(string name)
        {
            var file = Resources.Load<TextAsset>("M3B/" + name);
            if (!file) throw new InvalidOperationException("调查内容缺失 " + name);
            return file.text;
        }

        void Reset(EvidenceSnapshot saved)
        {
            if (Dialogue != null) Dialogue.EventRaised -= OnDialogue;
            Evidence = saved == null ? new EvidenceRegistry(catalog) : new EvidenceRegistry(catalog, saved);
            Dialogue = new DialogueEngine(lines, Evidence, null, mock);
            Dialogue.EventRaised += OnDialogue;
            Evidence.StateChanged += e => Debug.Log($"M4A event {e.EventId} {e.EventType} {e.EvidenceId}");
            activeNpc = null;
            Custody = null;
            IndexRead = OwnerProven = false;
        }

        void OnDialogue(DialogueResultEvent e)
        {
            Debug.Log($"M4A event {e.EventId} {e.EventType} {e.DisclosureId}");
            if (e.EventType == DialogueEventTypes.SessionOpened) activeNpc = e.NpcId;
            if (e.EventType == DialogueEventTypes.SessionClosed || e.EventType == DialogueEventTypes.SessionExpired)
                activeNpc = null;
            if (e.EventType == DialogueEventTypes.EvidencePresented || e.EventType == DialogueEventTypes.DisclosureTriggered)
                SaveFrame(Frame(), preChoice, chapterEnd);
        }

        JsonObject Frame()
        {
            var frame = new JsonObject()
                .Add("evidence", JsonValue.Parse(Evidence.CreateSnapshot().ToJson(false)))
                .Add("index_read", IndexRead).Add("r01", OwnerProven).Add("custody", Custody ?? "");
            foreach (var npc in Npcs)
                frame.Add(npc, new JsonObject().AddStringArray("fields", Dialogue.PresentedFields(npc))
                    .AddStringArray("played", Dialogue.PlayedDisclosures(npc)));
            return frame;
        }

        void LoadFrame(JsonObject frame)
        {
            Reset(EvidenceSnapshot.ParseAndValidate(catalog, JsonWriter.Serialize(frame["evidence"])));
            foreach (var npc in Npcs)
            {
                var memory = JsonContract.RequireObject(frame[npc], npc);
                Dialogue.RestoreKnowledge(npc, JsonContract.RequireStringArray(memory, "fields", npc),
                    JsonContract.RequireStringArray(memory, "played", npc));
            }
            IndexRead = JsonContract.RequireBool(frame, "index_read", "$");
            OwnerProven = JsonContract.RequireBool(frame, "r01", "$");
            var custody = JsonContract.OptionalString(frame, "custody", "$");
            Custody = string.IsNullOrEmpty(custody) ? null : custody;
            if (OwnerProven && !HasOwnerEvidence || Custody != null && (!Evidence.HasEvidence("E01")
                || Custody != "sealed_pending" && !(Custody == "linyao_temporary" && LinyaoVerified && OwnerProven)))
                throw new FormatException("保管记录与已核事实不一致");
        }

        bool SaveFrame(JsonObject current, JsonObject before, JsonObject end)
        {
            if (preserveInvalidSave) return false;
            var root = new JsonObject().Add("chapter_save", 1).Add("current", current);
            if (before != null) root.Add("pre_choice", before).Add("chapter_end", end);
            var old = PlayerPrefs.HasKey(SaveKey) ? PlayerPrefs.GetString(SaveKey) : null;
            try
            {
                PlayerPrefs.SetString(SaveKey, JsonWriter.Serialize(root));
                PlayerPrefs.Save();
                SaveNotice = null;
                return true;
            }
            catch (Exception ex)
            {
                if (old == null) PlayerPrefs.DeleteKey(SaveKey);
                else PlayerPrefs.SetString(SaveKey, old);
                SaveNotice = "本地存档暂不可用。";
                Debug.LogWarning("M4C save failed: " + ex.GetType().Name);
                return false;
            }
        }

        internal void Observe(EvidenceObservationResult result)
        {
            if (result.Changed) SaveFrame(Frame(), preChoice, chapterEnd);
        }

        internal bool ReadIndex()
        {
            if (IndexRead) return true;
            IndexRead = true;
            IndexRead = SaveFrame(Frame(), preChoice, chapterEnd);
            return IndexRead;
        }

        internal bool SubmitOwner(bool correct)
        {
            if (!correct || !HasOwnerEvidence) return false;
            if (OwnerProven) return true;
            OwnerProven = true;
            OwnerProven = SaveFrame(Frame(), preChoice, chapterEnd);
            return OwnerProven;
        }

        internal bool CommitCustody(bool handover, string activeNpc, bool confirmed)
        {
            if (!confirmed || !Evidence.HasEvidence("E01") || Custody != null) return false;
            if (handover ? !CanHandover || activeNpc != Linyao || this.activeNpc != Linyao
                         : !string.IsNullOrEmpty(activeNpc) || this.activeNpc != null) return false;
            var before = Frame();
            Custody = handover ? "linyao_temporary" : "sealed_pending";
            var end = Frame();
            if (!SaveFrame(end, before, end))
            {
                Custody = null;
                return false;
            }
            preChoice = before;
            chapterEnd = end;
            return true;
        }

        internal bool RestorePreChoice()
        {
            if (preChoice == null || !SaveFrame(preChoice, null, null)) return false;
            LoadFrame(preChoice);
            preChoice = chapterEnd = null;
            return true;
        }
    }
}
