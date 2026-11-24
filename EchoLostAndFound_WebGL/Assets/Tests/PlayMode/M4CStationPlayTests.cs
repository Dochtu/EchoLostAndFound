using System.Collections;
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
    /// <summary>
    /// M4-C scene coverage: 林遥, the A-0641 package, the counter binder and the fault card's
    /// back-page index are all reachable in the generated scene, and the D02 branch fires
    /// once through the normal presentation buttons.
    /// </summary>
    public sealed class M4CStationPlayTests
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

        string Saved() => PlayerPrefs.GetString(SaveKey);

        static Button FindButton(string label)
        {
            return Object.FindObjectsByType<Button>(FindObjectsSortMode.None).Single(b =>
                b.interactable && b.GetComponentsInChildren<TMP_Text>().Any(t => t.text.Contains(label)));
        }

        [Test]
        public void LinyaoPackageBinderAndPickupSheetAreReachable()
        {
            hud.Interact(Prop(StationTargets.WatchLabel));
            for (int part = 0; part < 5; ++part) hud.ActivateChoice(1);
            StringAssert.Contains("\"E01\"", Saved());
            hud.ClosePanel();

            hud.Interact(Prop(StationTargets.LostPackageLabel));
            StringAssert.Contains("旧修表收据", TextOnScreen());
            hud.ActivateChoice(1);
            StringAssert.Contains("\"E03\"", Saved());
            Assert.That(FindButton("翻副联册的对应档位"), Is.Not.Null);
            hud.ClosePanel();

            hud.Interact(Prop(StationTargets.BinderLabel));
            hud.ActivateChoice(1);
            StringAssert.Contains("\"E04\"", Saved());
            hud.ClosePanel();

            hud.Interact(Prop(StationTargets.CabinetLabel));
            hud.ActivateChoice(1);
            StringAssert.Contains("\"E02\"", Saved());
            hud.ClosePanel();

            hud.Interact(Prop(StationTargets.CabinetLabel));
            hud.ActivateChoice(2);
            StringAssert.Contains("该时段拾物联", TextOnScreen());
            hud.ActivateChoice(1);
            StringAssert.Contains("\"E05\"", Saved());
            hud.ClosePanel();

            hud.Interact(Prop(StationTargets.LinyaoLabel));
            StringAssert.Contains("我妈留的领取凭号", TextOnScreen());
            FindButton("E03").onClick.Invoke();
            FindButton("E04").onClick.Invoke();
            StringAssert.Contains("是我妈妈", TextOnScreen());
            hud.ClosePanel();
        }

        [UnityTest]
        public IEnumerator PackageAndBinderRefuseBeforeTheSerialNumberIsRead()
        {
            hud.Interact(Prop(StationTargets.LostPackageLabel));
            StringAssert.Contains("钢印编号", TextOnScreen());
            hud.ClosePanel();
            hud.Interact(Prop(StationTargets.BinderLabel));
            StringAssert.Contains("钢印编号", TextOnScreen());
            hud.ClosePanel();
            Assert.That(Saved(), Does.Not.Contain("\"E03\""));
            Assert.That(Saved(), Does.Not.Contain("\"E04\""));
            yield return null;

            hud.Interact(Prop(StationTargets.WatchLabel));
            hud.ActivateChoice(3);
            Assert.That(Saved(), Does.Contain("watch.serial_number"));
            hud.ClosePanel();

            hud.Interact(Prop(StationTargets.LostPackageLabel));
            StringAssert.Contains("查同号单据", TextOnScreen());
            hud.ClosePanel();
            hud.Interact(Prop(StationTargets.BinderLabel));
            StringAssert.Contains("取出指定领件联", TextOnScreen());
            hud.ClosePanel();
        }
    }
}
