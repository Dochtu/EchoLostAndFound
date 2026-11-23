using System;
using System.Linq;
using EchoLostAndFound.M2;
using EchoLostAndFound.WebGL.Contracts;
using EchoStation;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace EchoLostAndFound.QA
{
    public sealed class StationAcceptanceTests
    {
        private const string StationPath = "Assets/Station/Scenes/Station.unity";

        [Test]
        public void BuildStartsInStationWithInvestigatorAndBothInteractions()
        {
            Assert.That(EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path),
                Is.EqualTo(new[] { StationPath }));
            Assert.That(GraphicsSettings.currentRenderPipeline?.GetType().Name,
                Is.EqualTo("UniversalRenderPipelineAsset"));
            var scene = SceneManager.GetSceneByPath(StationPath);
            bool alreadyLoaded = scene.isLoaded;
            if (!alreadyLoaded) scene = EditorSceneManager.OpenScene(StationPath, OpenSceneMode.Additive);
            try
            {
                var roots = scene.GetRootGameObjects();
                var player = roots.SelectMany(root => root.GetComponentsInChildren<StationPlayer>()).Single();
                Assert.That(player.GetComponent<CharacterController>(), Is.Not.Null);
                Assert.That(player.GetComponentInChildren<Camera>(), Is.Not.Null);
                var targets = roots.SelectMany(root => root.GetComponentsInChildren<M2Interactable>()).ToArray();
                Assert.That(targets.Select(target => target.Kind), Does.Contain(InteractionKind.Item));
                Assert.That(targets.Select(target => target.Kind), Does.Contain(InteractionKind.Npc));
                Assert.That(targets.All(target => target.GetComponentInChildren<Collider>()), Is.True);
            }
            finally
            {
                if (!alreadyLoaded) EditorSceneManager.CloseScene(scene, true);
            }
        }

        [Test]
        public void InvestigationRayHonoursRangeAndCannotReachThroughStationWalls()
        {
            var origin = new Vector3(2048, 2048, 2048);
            var targetObject = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var wall = GameObject.CreatePrimitive(PrimitiveType.Cube);
            try
            {
                targetObject.transform.position = origin + Vector3.forward * 3f;
                var target = targetObject.AddComponent<M2Interactable>();
                var ray = new Ray(origin, Vector3.forward);
                wall.transform.position = origin + Vector3.forward * 1.5f;
                Physics.SyncTransforms();
                Assert.That(M2InteractionProbe.Find(ray, 4f), Is.Null, "Solid wall occludes clue");
                wall.SetActive(false);
                Physics.SyncTransforms();
                Assert.That(M2InteractionProbe.Find(ray, 2.4f), Is.Null, "Clue surface is 2.5 m away");
                Assert.That(M2InteractionProbe.Find(ray, 2.6f), Is.SameAs(target));
                target.enabled = false;
                Assert.That(M2InteractionProbe.Find(ray, 2.6f), Is.Null, "Disabled interaction");
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(wall);
                UnityEngine.Object.DestroyImmediate(targetObject);
            }
        }

        [Test]
        public void BothEntryPointsHaveDisplayableContentAndDistinctCommandIdentities()
        {
            var json = Resources.Load<TextAsset>("M3A/StationPreview");
            Assert.That(json, Is.Not.Null);
            var content = JsonUtility.FromJson<StationPreview>(json.text);
            Assert.That(content.evidence.field_id, Is.EqualTo("watch.dial"));
            Assert.That(content.evidence.observation_text, Is.EqualTo("The hands are stopped at 9:17."),
                "A twelve-hour dial only reveals the hand positions; night-time needs separate evidence.");
            Assert.That(content.dialogue.speaker_name, Is.Not.Empty);
            Assert.That(content.dialogue.display_text, Is.Not.Empty);
            var inspection = InteractionEvent.InspectDial();
            var conversation = InteractionEvent.OpenDialogue();
            Assert.That(inspection.target_id, Is.EqualTo("item_pocket_watch"));
            Assert.That(inspection.part_id, Is.EqualTo("dial"));
            Assert.That(conversation.target_id, Is.EqualTo(content.dialogue.npc_id));
            Assert.That(Guid.Parse(inspection.request_id), Is.Not.EqualTo(Guid.Parse(conversation.request_id)));
        }
    }
}
