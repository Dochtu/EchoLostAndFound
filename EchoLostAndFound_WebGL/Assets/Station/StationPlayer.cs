using System;
using EchoLostAndFound.M2;
using EchoLostAndFound.WebGL.Contracts;
using UnityEngine;
using UnityEngine.InputSystem;

namespace EchoStation
{
    [RequireComponent(typeof(CharacterController))]
    public sealed class StationPlayer : MonoBehaviour, IStationInteractionSource
    {
        [SerializeField] Camera view;
        [SerializeField] InputActionAsset bindings;
        [SerializeField] StationHud hud;
        CharacterController motor;
        InputActionAsset actions;
        InputAction move, look, interact, cancel;
        float fallSpeed;
        bool captured;
        public Camera View => view;
        public float Pitch { get; private set; }
        public float InteractionDistance => 2.4f;
        public IInteractable FocusedTarget { get; private set; }
        public IInteractable ActiveTarget { get; private set; }
        public event Action<InteractionEvent> Interacted;

        public void Configure(Camera camera, InputActionAsset input, StationHud overlay)
        {
            view = camera;
            bindings = input;
            hud = overlay;
        }

        void Awake()
        {
            motor = GetComponent<CharacterController>();
            actions = Instantiate(bindings);
            move = actions.FindAction("Player/Move", true);
            look = actions.FindAction("Player/Look", true);
            interact = actions.FindAction("Player/Interact", true);
            cancel = actions.FindAction("UI/Cancel", true);
        }

        void OnEnable()
        {
            move.Enable();
            look.Enable();
            interact.Enable();
            cancel.Enable();
        }

        void OnDisable()
        {
            actions.Disable();
            Release();
        }

        void OnDestroy() => Destroy(actions);

        void Release()
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
            captured = false;
            ActiveTarget = FocusedTarget = null;
        }

        void Capture()
        {
            Cursor.lockState = CursorLockMode.Locked;
            Cursor.visible = false;
            captured = true;
        }

        // The inspection sheet owns the pointer while it is open: walking, looking and re-locking stop.
        void Update()
        {
            if (hud != null && hud.IsOpen)
            {
                if (Cursor.lockState != CursorLockMode.None)
                {
                    Cursor.lockState = CursorLockMode.None;
                    Cursor.visible = true;
                }
                bool back = interact.WasPressedThisFrame();
                bool escape = cancel.WasPressedThisFrame();
                if (!back && !escape) return;
                // While the free-text field has focus, E and Esc belong to the text editor,
                // not to the panel: typing must never close the conversation.
                if (hud.IsTyping) return;
                hud.ClosePanel();
                ActiveTarget = null;
                if (escape) Release();
                else Capture();
                hud.ShowFocus("");
                return;
            }

            if (captured && Cursor.lockState != CursorLockMode.Locked) Release();
            if (!captured)
            {
                hud.ShowFocus("Click to explore");
                if (Mouse.current != null && Mouse.current.leftButton.wasPressedThisFrame) Capture();
                return;
            }

            if (cancel.WasPressedThisFrame()) { Release(); return; }

            // Port of M2Player's input, planar movement, vertical clamp and eye-origin probe.
            Vector2 delta = look.ReadValue<Vector2>() * 0.12f;
            transform.Rotate(0f, delta.x, 0f);
            Pitch = Mathf.Clamp(Pitch - delta.y, -80f, 80f);
            view.transform.localRotation = Quaternion.Euler(Pitch, 0f, 0f);
            Vector2 input = Vector2.ClampMagnitude(move.ReadValue<Vector2>(), 1f);
            Vector3 velocity = (transform.right * input.x + transform.forward * input.y) * 2.6f;
            fallSpeed = motor.isGrounded ? -2f : Mathf.Max(fallSpeed + Physics.gravity.y * Time.deltaTime, -45f);
            velocity.y = fallSpeed;
            motor.Move(velocity * Time.deltaTime);

            Ray ray = view.ViewportPointToRay(new Vector3(.5f, .5f));
            FocusedTarget = M2InteractionProbe.Find(new Ray(view.transform.position, ray.direction), InteractionDistance, transform);
            hud.ShowFocus(FocusedTarget?.DisplayName);
            bool pressed = interact.WasPressedThisFrame();
            if (pressed) LogProbe(FocusedTarget?.DisplayName ?? "none");
            if (FocusedTarget == null || !pressed) return;
            ActiveTarget = FocusedTarget;
            FocusedTarget = null;
            BeginInteraction(ActiveTarget);
            Debug.Log("Station interaction: " + ActiveTarget.DisplayName);
        }

        // Debug aid for the M4-C browser acceptance run: reports the exact spot and aim
        // whenever E is pressed, so the E2E script can walk to each prop deterministically.
        void LogProbe(string target)
        {
            Debug.Log("M4C probe pos=" + transform.position.x.ToString("F2") + "," + transform.position.z.ToString("F2")
                + " yaw=" + transform.eulerAngles.y.ToString("F0")
                + " pitch=" + Pitch.ToString("F0")
                + " target=" + target);
        }

        // The HUD owns panel routing (see StationTargets); the player only reports which
        // approved interaction happened, so the M2 contract event keeps its old meaning.
        void BeginInteraction(IInteractable target)
        {
            hud.Interact(target);
            switch (target.Kind)
            {
                case InteractionKind.Item:
                    Interacted?.Invoke(InteractionEvent.InspectDial());
                    break;
                case InteractionKind.Npc:
                    Interacted?.Invoke(InteractionEvent.OpenDialogue());
                    break;
            }
        }
    }
}
