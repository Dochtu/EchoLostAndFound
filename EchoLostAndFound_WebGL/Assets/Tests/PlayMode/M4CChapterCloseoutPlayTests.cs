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
    public sealed class M4CChapterCloseoutPlayTests
    {
        const string SaveKey = "EchoStation.M4A.evidence.v1";
        bool hadSave;
        string previousSave;
        StationHud hud;

        [UnitySetUp]
        public IEnumerator EnterStationWithEmptySave()
        {
            hadSave = PlayerPrefs.HasKey(SaveKey);
            previousSave = PlayerPrefs.GetString(SaveKey);
            PlayerPrefs.DeleteKey(SaveKey);
            yield return EnterStation();
        }

        [TearDown]
        public void RestorePlayerSave()
        {
            if (hadSave) PlayerPrefs.SetString(SaveKey, previousSave);
            else PlayerPrefs.DeleteKey(SaveKey);
            PlayerPrefs.Save();
        }

        IEnumerator EnterStation()
        {
            yield return SceneManager.LoadSceneAsync("Station");
            yield return null;
            hud = Object.FindFirstObjectByType<StationHud>();
            Assert.That(hud, Is.Not.Null);
        }

        void Inspect(string target)
        {
            var prop = Object.FindObjectsByType<M2Interactable>(FindObjectsSortMode.None)
                .Single(item => item.DisplayName == target);
            hud.Interact(prop);
        }

        string VisibleText() => string.Join("\n", hud.GetComponentsInChildren<TMP_Text>()
            .Where(text => text.isActiveAndEnabled).Select(text => text.text));

        void Click(string label)
        {
            var matches = hud.GetComponentsInChildren<Button>().Where(button =>
                button.isActiveAndEnabled && button.interactable &&
                button.GetComponentsInChildren<TMP_Text>().Any(t => t.text.Contains(label))).ToArray();
            Assert.That(matches.Length, Is.EqualTo(1), label + "\n" + VisibleText());
            matches[0].onClick.Invoke();
        }

        void InspectWatchParts()
        {
            Inspect("怀表");
            foreach (var part in new[] { "表盘", "背刻", "编号", "侧冠", "冠轴损伤" })
                Click("查看 " + part);
            Assert.That(VisibleText(), Does.Contain("QH-283"));
        }

        [UnityTest]
        public IEnumerator BagReceiptSurvivesReentryAndCheckpointRestoresThePhysicalWatch()
        {
            InspectWatchParts();
            Click("装袋待核");
            Click("取消，返回调查");
            Assert.That(hud.IsOpen, Is.False);
            Inspect("怀表");
            Click("装袋待核");
            Click("确认装袋并登记");
            Assert.That(VisibleText(), Does.Contain("第一章调查交接"));
            Assert.That(VisibleText(), Does.Contain("怀表已装袋待核"));
            Assert.That(VisibleText(), Does.Contain("第二章资格已开放"));
            Assert.That(VisibleText(), Does.Contain("E01"));
            Click("继续调查");
            yield return EnterStation();
            AssertWatchAvailable(false);
            Inspect("失物包");
            Click("查阅怀表记录");
            Assert.That(VisibleText(), Does.Contain("QH-283"));
            Click("查看保管回执");
            Click("返回菜单");
            Click("查看第一章交接");
            Click("读取交接前检查点");
            Click("确认读取");
            yield return EnterStation();
            AssertWatchAvailable(true);
            Inspect("怀表");
            Click("装袋待核");
            Assert.That(VisibleText(), Does.Contain("确认装袋并登记"));
        }

        [UnityTest]
        public IEnumerator OwnerEvidenceAndLinyaosOwnDisclosureLeadToReadableHandoverReceipt()
        {
            InspectWatchParts();
            Inspect("失物包");
            Click("查同号单据");
            Click("翻副联册的对应档位");
            Click("取出指定领件联");
            Inspect("怀表");
            Click("核对怀表原主");
            Click("原主沈禾，今可由她书面指定的林遥领件");
            Assert.That(VisibleText(), Does.Contain("已核"));

            Inspect("老周");
            Click("出示 E03");
            Click("出示 E04");
            Inspect("林遥");
            Click("办理今夜暂收");
            Assert.That(VisibleText(), Does.Not.Contain("确认暂收并登记"));
            Click("取消，返回调查");
            Inspect("林遥");
            Click("出示 E03");
            Click("出示 E04");
            Assert.That(VisibleText(), Does.Contain("是我妈妈"));
            Click("办理今夜暂收");
            Assert.That(VisibleText(), Does.Contain("去名公开"));
            Assert.That(VisibleText(), Does.Contain("交回受限封存"));
            Click("确认暂收并登记");
            Assert.That(VisibleText(), Does.Contain("第一章调查交接"));
            Assert.That(VisibleText(), Does.Contain("林遥今夜暂收怀表"));
            Click("继续调查");
            yield return EnterStation();
            AssertWatchAvailable(false);
            Inspect("失物包");
            Click("查看保管回执");
            Assert.That(VisibleText(), Does.Contain("林遥今夜暂收怀表"));
            Click("继续调查");
            Inspect("维修柜");
            Click("看配电故障卡正面");
            Assert.That(VisibleText(), Does.Contain("E02"));
        }

        void AssertWatchAvailable(bool expected)
        {
            var watch = Object.FindObjectsByType<M2Interactable>(FindObjectsSortMode.None)
                .Single(item => item.DisplayName == "怀表");
            var meshes = watch.GetComponentsInChildren<Renderer>(true);
            var colliders = watch.GetComponentsInChildren<Collider>(true);
            Assert.That(meshes.Length, Is.GreaterThan(0));
            Assert.That(colliders.Length, Is.GreaterThan(0));
            Assert.That(meshes.Any(mesh => mesh.enabled), Is.EqualTo(expected));
            Assert.That(colliders.Any(collider => collider.enabled), Is.EqualTo(expected));
        }
    }
}
