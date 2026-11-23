using System.Collections;
using EchoLostAndFound.M2;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

namespace EchoLostAndFound.QA
{
    public class M2PlayTests
    {
        Keyboard keyboard;
        Mouse mouse;
        M2Player player;
        CharacterController capsule;

        [UnitySetUp]
        public IEnumerator StartStation()
        {
            keyboard = InputSystem.AddDevice<Keyboard>();
            mouse = InputSystem.AddDevice<Mouse>();
            yield return SceneManager.LoadSceneAsync("Assets/_Project/Scenes/Station.unity");
            yield return null;
            player = Object.FindFirstObjectByType<M2Player>();
            Assert.That(player, Is.Not.Null);
            capsule = player.GetComponent<CharacterController>();
            Assert.That(capsule.isGrounded || player.transform.position.y < .15f, Is.True);
        }

        [UnityTearDown]
        public IEnumerator RemoveInput()
        {
            InputSystem.RemoveDevice(keyboard);
            InputSystem.RemoveDevice(mouse);
            yield return null;
        }

        static GameObject Box(string name, Vector3 center, Vector3 dimensions)
        {
            var box = new GameObject(name);
            box.transform.position = center;
            box.AddComponent<BoxCollider>().size = dimensions;
            return box;
        }

        [Test]
        public void ProbeHonoursSurfaceDistanceNearestHitAndBlockingGlass()
        {
            var start = new Vector3(0, 150, 0);
            var ray = new Ray(start, Vector3.forward);
            var far = Box("Far", start + Vector3.forward * 3, Vector3.one);
            var near = Box("Near", start + Vector3.forward * 2, Vector3.one);
            var glass = Box("Glass", start + Vector3.forward * .8f, Vector3.one * .2f);
            try
            {
                far.AddComponent<M2Interactable>().Configure("后方", InteractionKind.Item);
                var target = near.AddComponent<M2Interactable>();
                target.Configure("前方", InteractionKind.Item);
                Physics.SyncTransforms();
                Assert.That(M2InteractionProbe.Find(ray, 4), Is.Null, "Solid glass must mask both targets");
                glass.GetComponent<Collider>().isTrigger = true;
                Physics.SyncTransforms();
                Assert.That(M2InteractionProbe.Find(ray, 1.49f), Is.Null);
                Assert.That(M2InteractionProbe.Find(ray, 1.51f), Is.SameAs(target));
                Assert.That(M2InteractionProbe.Find(ray, 4), Is.SameAs(target));
            }
            finally
            {
                Object.Destroy(far);
                Object.Destroy(near);
                Object.Destroy(glass);
            }
        }

        [UnityTest]
        public IEnumerator ReachAllFourAuthoredTargetsFromPlayableEyeHeight()
        {
            IEnumerator AimAndOpen(Vector3 aim, string label)
            {
                Vector3 dir = aim - player.View.transform.position;
                float desiredYaw = Mathf.Atan2(dir.x, dir.z) * Mathf.Rad2Deg;
                float desiredPitch = -Mathf.Atan2(dir.y, new Vector2(dir.x, dir.z).magnitude) * Mathf.Rad2Deg;
                var mouseDelta = new Vector2(Mathf.DeltaAngle(player.transform.eulerAngles.y, desiredYaw),
                    player.Pitch - desiredPitch) / player.LookSensitivity;
                InputSystem.QueueDeltaStateEvent(mouse.delta, mouseDelta);
                yield return Frames(2);
                Assert.That(player.FocusedTarget?.DisplayName, Is.EqualTo(label), $"Aim at {aim}");
                Keys(Key.E);
                yield return Frames(2);
                Assert.That(player.ActiveTarget?.DisplayName, Is.EqualTo(label));
                Keys(Key.Escape);
                yield return Frames(2);
                Assert.That(player.IsInterfaceOpen, Is.False);
                Keys();
                yield return Frames(2);
            }
            yield return AimAndOpen(new Vector3(-9.83f, 1.06f, -4.45f), "怀表");
            yield return AimAndOpen(new Vector3(-9.86f, 1.18f, -3.69f), "登记册");
            yield return AimAndOpen(new Vector3(-9.38f, .76f, -5.5f), "柜台");
            WalkTo(-8.3f, -3.2f);
            WalkTo(-4.8f, -3.2f);
            WalkTo(-4.8f, 3.1f);
            yield return AimAndOpen(new Vector3(-4.8f, 1.3f, 4.6f), "站内旅客");
        }

        // Each step uses the live prefab's capsule and Station's actual floor, walls and doorways.
        void WalkTo(float x, float z)
        {
            var destination = new Vector3(x, 0, z);
            int steps = 0;
            while (++steps <= 400)
            {
                var position = player.transform.position;
                var delta = destination - new Vector3(position.x, 0, position.z);
                if (delta.magnitude < .06f) break;
                capsule.Move(Vector3.ClampMagnitude(delta, .08f) + Vector3.down * .02f);
            }
            Assert.That(steps, Is.LessThanOrEqualTo(400), $"Route blocked at {player.transform.position}, heading for {destination}");
            Assert.That(player.transform.position.y, Is.InRange(-.15f, .45f), $"Floor at {destination}");
        }

        [Test]
        public void CapsuleWalksBothDoorwaysReturnsAndCannotCrossWestHallWall()
        {
            var spawn = player.transform.position;
            var route = new[] {
                new Vector2(-8.3f, -3.2f), new Vector2(0, -3.2f), new Vector2(0, 2.8f),
                new Vector2(4.5f, 2.8f), new Vector2(4.5f, .95f), new Vector2(10, .95f)
            };
            foreach (var p in route) WalkTo(p.x, p.y);
            for (int i = 0; i < 80; i++) capsule.Move(Vector3.right * .08f);
            Assert.That(player.transform.position.x, Is.InRange(13.5f, 13.93f), "Stop on platform inside of track rail");
            Assert.That(player.transform.position.y, Is.InRange(-.15f, .45f));
            WalkTo(10, .95f);
            for (int i = route.Length - 2; i >= 0; --i) WalkTo(route[i].x, route[i].y);
            WalkTo(spawn.x, spawn.z);
            WalkTo(-8.3f, -3.2f);
            WalkTo(0, -3.2f);
            WalkTo(0, -4.85f);
            WalkTo(-4.9f, -4.85f);
            for (int i = 0; i < 45; ++i) capsule.Move(Vector3.left * .08f);
            Assert.That(player.transform.position.x, Is.InRange(-5.85f, -5.45f), "Hall side of west wall");
        }

        void Keys(params Key[] keys) => InputSystem.QueueStateEvent(keyboard, new KeyboardState(keys));

        static IEnumerator Frames(int count)
        {
            for (var i = 0; i < count; i++) yield return null;
        }

        [UnityTest]
        public IEnumerator AllFourMovementKeysFollowThePlayersHeading()
        {
            WalkTo(-8.3f, -3.2f);
            WalkTo(0, -3.2f);
            IEnumerator StepKey(Key key, Vector3 expected)
            {
                var from = player.transform.position;
                Keys(key);
                yield return Frames(5);
                Keys();
                yield return Frames(2);
                Vector3 actual = Vector3.ProjectOnPlane(player.transform.position - from, Vector3.up);
                Assert.That(Vector3.Dot(actual, expected), Is.GreaterThan(.025f), key.ToString());
                Assert.That(Vector3.Angle(actual, expected), Is.LessThan(2f), key.ToString());
            }
            yield return StepKey(Key.W, player.transform.forward);
            yield return StepKey(Key.S, -player.transform.forward);
            yield return StepKey(Key.A, -player.transform.right);
            yield return StepKey(Key.D, player.transform.right);
        }

        [UnityTest]
        public IEnumerator RealInputDrivesPlayerButStopsDuringPreviewAndDialogue()
        {
            var origin = player.transform.position;
            Keys(Key.S);
            yield return Frames(4);
            Keys();
            yield return Frames(2);
            Assert.That(Vector3.Distance(player.transform.position, origin), Is.GreaterThan(.025f));
            var initialYaw = player.transform.eulerAngles.y;
            InputSystem.QueueDeltaStateEvent(mouse.delta, new Vector2(60, 0));
            yield return Frames(2);
            Assert.That(Mathf.Abs(Mathf.DeltaAngle(initialYaw, player.transform.eulerAngles.y)), Is.GreaterThan(1));
            InputSystem.QueueDeltaStateEvent(mouse.delta, new Vector2(0, 3000));
            yield return Frames(2);
            Assert.That(Mathf.Abs(player.Pitch), Is.InRange(79f, 80.1f));
            InputSystem.QueueDeltaStateEvent(mouse.delta, new Vector2(0, -3000));
            yield return Frames(2);
            Assert.That(Mathf.Abs(player.Pitch), Is.InRange(79f, 80.1f));

            InputSystem.QueueDeltaStateEvent(mouse.delta, new Vector2(0, player.Pitch / player.LookSensitivity));
            yield return Frames(2);
            Assert.That(Mathf.Abs(player.Pitch), Is.LessThan(.1f));

            foreach (var kind in new[] { InteractionKind.Item, InteractionKind.Npc })
            {
                var eye = player.View.transform;
                var targetBox = Box("QA target", eye.position + eye.forward * .8f, Vector3.one * .15f);
                var target = targetBox.AddComponent<M2Interactable>();
                target.Configure(kind.ToString(), kind);
                Physics.SyncTransforms();
                yield return Frames(2);
                Assert.That(player.FocusedTarget, Is.SameAs(target));
                // E must recheck the live ray even if last frame showed a prompt.
                var blocker = Box("Block last frame focus", eye.position + eye.forward * .45f, Vector3.one * .12f);
                Physics.SyncTransforms();
                Keys(Key.E);
                yield return Frames(2);
                Assert.That(player.IsInterfaceOpen, Is.False);
                Assert.That(player.FocusedTarget, Is.Null);
                Keys();
                Object.Destroy(blocker);
                yield return Frames(2);
                Keys(Key.E);
                yield return Frames(2);
                Assert.That(player.ActiveTarget, Is.SameAs(target));
                Assert.That(player.IsInterfaceOpen, Is.True);
                var frozen = player.transform.position;
                var frozenRotation = eye.rotation;
                Keys(Key.W, Key.A);
                InputSystem.QueueDeltaStateEvent(mouse.delta, new Vector2(96, 10));
                yield return Frames(4);
                Assert.That(Vector3.Distance(player.transform.position, frozen), Is.LessThan(.005f));
                Assert.That(Quaternion.Angle(eye.rotation, frozenRotation), Is.LessThan(.02f));
                Assert.That(Cursor.lockState, Is.EqualTo(CursorLockMode.None));
                Keys(Key.Escape);
                yield return Frames(2);
                Assert.That(player.IsInterfaceOpen, Is.False);
                Keys();
                Object.Destroy(targetBox);
                yield return Frames(2);
            }
        }
    }
}
