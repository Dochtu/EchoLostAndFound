using System.Collections;
using System.Linq;
using EchoLostAndFound.M2;
using EchoStation;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

namespace EchoLostAndFound.QA
{
    /// <summary>
    /// C3 free-text coverage that does not need a live service: the panel must show the input
    /// only during a conversation, must refuse empty input, and must never stay locked in a
    /// waiting state whether the service answers, times out or is absent.
    /// </summary>
    public sealed class M4COnlinePlayTests
    {
        const string SaveKey = "EchoStation.M4A.evidence.v1";
        string savedSnapshot;

        [UnitySetUp]
        public IEnumerator SetUp()
        {
            savedSnapshot = PlayerPrefs.GetString(SaveKey, null);
            PlayerPrefs.DeleteKey(SaveKey);
            PlayerPrefs.Save();
            yield return SceneManager.LoadSceneAsync("Station");
        }

        [TearDown]
        public void TearDown()
        {
            if (string.IsNullOrEmpty(savedSnapshot)) PlayerPrefs.DeleteKey(SaveKey);
            else PlayerPrefs.SetString(SaveKey, savedSnapshot);
            PlayerPrefs.Save();
        }

        static IInteractable Prop(string label)
        {
            return Object.FindObjectsByType<M2Interactable>(FindObjectsSortMode.None)
                .Single(prop => prop.DisplayName == label);
        }

        static StationHud Hud()
        {
            return Object.FindFirstObjectByType<StationHud>();
        }

        [UnityTest]
        public IEnumerator FreeTextRowOnlyAppearsWhileTalkingToAnNpc()
        {
            var hud = Hud();
            Assert.IsNotNull(hud, "the station HUD must exist");

            hud.Interact(Prop("老周"));
            yield return null;
            Assert.IsTrue(hud.IsFreeTextVisible, "the input row must be visible during a conversation");
            Assert.AreEqual("老周", hud.CurrentSpeaker);

            hud.ClosePanel();
            yield return null;
            Assert.IsFalse(hud.IsFreeTextVisible, "the input row must hide once the panel closes");

            hud.Interact(Prop("怀表"));
            yield return null;
            Assert.IsFalse(hud.IsFreeTextVisible, "the input row must not appear on a record page");
            hud.ClosePanel();
        }

        [UnityTest]
        public IEnumerator EmptyFreeTextIsRefusedWithoutWaiting()
        {
            var hud = Hud();
            hud.Interact(Prop("老周"));
            yield return null;

            hud.SetFreeText("   ");
            hud.SubmitFreeText();
            yield return null;

            Assert.AreEqual("先说点什么，再发送。", hud.FreeTextStatus);
            Assert.IsFalse(hud.WaitingForReply, "an empty line must not start a request");
            hud.ClosePanel();
        }

        [UnityTest]
        public IEnumerator FreeTextSubmitAlwaysReleasesTheWaitingState()
        {
            var hud = Hud();
            hud.Interact(Prop("老周"));
            yield return null;
            Assert.IsFalse(hud.WaitingForReply, "a fresh conversation must not be waiting");

            hud.SetFreeText("站台那晚亮着吗");
            hud.SubmitFreeText();

            var deadline = Time.realtimeSinceStartup + 25f;
            while (hud.WaitingForReply && Time.realtimeSinceStartup < deadline) yield return null;

            Assert.IsFalse(hud.WaitingForReply, "the send lock must clear after success, failure or timeout");
            Assert.IsFalse(string.IsNullOrEmpty(hud.FreeTextStatus), "the player needs a status line");
            Debug.Log("M4C online probe online=" + hud.Online + " status=" + hud.FreeTextStatus);
            hud.ClosePanel();
        }
    }
}
