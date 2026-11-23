using System;
using System.Linq;
using EchoLostAndFound.M2;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace EchoLostAndFound.QA
{
    public class M2EditTests
    {
        const string Station = "Assets/_Project/Scenes/Station.unity";
        const string PlayerPrefab = "Assets/_Project/Prefabs/Player/M2Player.prefab";
        Scene station;
        bool openedForTest;

        [OneTimeSetUp]
        public void ReadStation()
        {
            station = SceneManager.GetSceneByPath(Station);
            if (station.isLoaded) return;
            station = EditorSceneManager.OpenScene(Station, OpenSceneMode.Additive);
            openedForTest = true;
        }

        [OneTimeTearDown]
        public void ReleaseStation()
        {
            if (openedForTest) EditorSceneManager.CloseScene(station, true);
        }

        T[] All<T>() where T : Component => station.GetRootGameObjects()
            .SelectMany(root => root.GetComponentsInChildren<T>(true)).ToArray();

        [Test]
        public void StationUsesConnectedPlayerPrefabAndSingleActiveEye()
        {
            var player = All<M2Player>().Single();
            Assert.That(PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(player), Is.EqualTo(PlayerPrefab));
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(PlayerPrefab);
            Assert.That(prefab.GetComponent<CharacterController>(), Is.Not.Null);
            var camera = All<Camera>().Single(c => c.isActiveAndEnabled);
            Assert.That(camera.CompareTag("MainCamera"), Is.True);
            Assert.That(camera.transform.IsChildOf(player.transform), Is.True);
            var eye = player.transform.InverseTransformPoint(camera.transform.position);
            Assert.That(new Vector2(eye.x, eye.z).magnitude, Is.LessThan(.05f), "World camera must follow collision capsule centre");
            Assert.That(eye.y, Is.InRange(1.4f, 1.8f), "Playable eye height");
            Assert.That(All<AudioListener>().Count(l => l.isActiveAndEnabled), Is.EqualTo(1));
        }

        [Test]
        public void EachStationInteractionHasDistinctVisibleNameAndSolidHitSurface()
        {
            var targets = All<M2Interactable>().Where(t => t.isActiveAndEnabled).ToArray();
            var names = targets.Select(t => t.DisplayName).ToArray();
            foreach (var required in new[] { "柜台", "怀表", "登记册" })
                Assert.That(names.Count(n => n.Contains(required)), Is.EqualTo(1), required);
            Assert.That(targets.Count(t => t.Kind == InteractionKind.Npc), Is.GreaterThanOrEqualTo(1));
            Assert.That(names.All(n => !string.IsNullOrWhiteSpace(n)), Is.True);
            Assert.That(names.Distinct().Count(), Is.EqualTo(names.Length));
            foreach (var target in targets)
                Assert.That(target.GetComponentsInChildren<Collider>().Any(c => c.enabled && !c.isTrigger), Is.True, target.DisplayName);
        }
    }
}
