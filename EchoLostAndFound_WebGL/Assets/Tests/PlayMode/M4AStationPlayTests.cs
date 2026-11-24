using System.Collections;
using System.Collections.Generic;
using System.Linq;
using EchoLostAndFound.M2;
using EchoStation;
using NUnit.Framework;
using TMPro;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using UnityEngine.UI;

namespace EchoLostAndFound.QA
{
    public sealed class M4AStationPlayTests
    {
        const string SaveKey = "EchoStation.M4A.evidence.v1";
        bool hadSave;
        string previousSave;
        StationHud hud;

        static IInteractable Prop(string label)
        {
            return Object.FindObjectsByType<M2Interactable>(FindObjectsSortMode.None)
                .Single(prop => prop.DisplayName == label);
        }

        [UnitySetUp]
        public IEnumerator OpenFreshStation()
        {
            hadSave = PlayerPrefs.HasKey(SaveKey);
            previousSave = PlayerPrefs.GetString(SaveKey);
            PlayerPrefs.DeleteKey(SaveKey);
            yield return SceneManager.LoadSceneAsync("Station");
            yield return null;
            hud = Object.FindFirstObjectByType<StationHud>();
            Assert.That(hud, Is.Not.Null);
        }

        [TearDown]
        public void RestoreLocalPreferences()
        {
            if (hadSave) PlayerPrefs.SetString(SaveKey, previousSave);
            else PlayerPrefs.DeleteKey(SaveKey);
            PlayerPrefs.Save();
        }

        string TextOnScreen() => string.Join("\n", Object.FindObjectsByType<TMP_Text>(
            FindObjectsSortMode.None).Where(t => t.isActiveAndEnabled).Select(t => t.text));

        static Button FindButton(string label)
        {
            return Object.FindObjectsByType<Button>(FindObjectsSortMode.None).Single(b =>
                b.interactable && b.GetComponentsInChildren<TMP_Text>().Any(t => t.text.Contains(label)));
        }

        [UnityTest]
        public IEnumerator WatchCardSurvivesReturnAndRepairCardChangesNpcOptions()
        {
            hud.Interact(Prop("怀表"));
            StringAssert.Contains("A-0641", TextOnScreen());
            StringAssert.DoesNotContain("QH-283", TextOnScreen());
            for (int part = 0; part < 5 && !PlayerPrefs.GetString(SaveKey).Contains("\"E01\""); ++part)
                hud.ActivateChoice(1);
            StringAssert.Contains("\"E01\"", PlayerPrefs.GetString(SaveKey));
            StringAssert.Contains("QH-283", TextOnScreen());
            hud.ClosePanel();

            hud.Interact(Prop("维修柜"));
            hud.ActivateChoice(1);
            StringAssert.Contains("\"E02\"", PlayerPrefs.GetString(SaveKey));
            hud.ClosePanel();

            yield return SceneManager.LoadSceneAsync("Station");
            yield return null;
            hud = Object.FindFirstObjectByType<StationHud>();
            hud.Interact(Prop("老周"));
            StringAssert.Contains("这封从旧库搬过两回", TextOnScreen());
            StringAssert.DoesNotContain("再问站台那晚的照明", TextOnScreen());
            FindButton("问站台那晚的照明").onClick.Invoke();
            StringAssert.Contains("那盏油灯拖到里头去了", TextOnScreen());
            FindButton("先不问这个").onClick.Invoke();
            FindButton("E02").onClick.Invoke();
            StringAssert.Contains("我的灯到二十才摆好", TextOnScreen());
            Assert.That(FindButton("再问站台那晚的照明"), Is.Not.Null);
            hud.ClosePanel();
            hud.Interact(Prop("老周"));
            StringAssert.Contains("这封从旧库搬过两回", TextOnScreen());
        }
    }
}
