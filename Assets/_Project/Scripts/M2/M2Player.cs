using System;
using UnityEngine;
using UnityEngine.InputSystem;

namespace EchoLostAndFound.M2
{
    [DisallowMultipleComponent, RequireComponent(typeof(CharacterController))]
    public sealed class M2Player : MonoBehaviour
    {
        [SerializeField] private Camera view;
        [SerializeField] private InputActionAsset actions;
        [SerializeField] private Font chineseFont;
        [SerializeField, Min(0.1f)] private float movementSpeed = 2.6f;
        [SerializeField, Min(0.01f)] private float sensitivity = 0.12f;
        [SerializeField, Range(1f, 89f)] private float pitchLimit = 80f;
        [SerializeField, Min(0.1f)] private float interactionDistance = 2.4f;

        private CharacterController motor;
        private InputActionAsset localActions;
        private InputAction move, look, interact, cancel;
        private M2InteractionHud hud;
        private float fallSpeed;

        public Camera View => view;
        public float Pitch { get; private set; }
        public float LookSensitivity => sensitivity;
        public float InteractionDistance => interactionDistance;
        public IInteractable FocusedTarget { get; private set; }
        public IInteractable ActiveTarget { get; private set; }
        public bool IsInterfaceOpen => ActiveTarget != null;
        // Presentation hooks only. Evidence and story decisions belong to their owning systems.
        public event Action<IInteractable> InterfaceOpened;
        public event Action InterfaceClosed;

        public void Configure(Camera worldCamera, InputActionAsset inputActions, Font font)
        {
            view = worldCamera;
            actions = inputActions;
            chineseFont = font;
        }

        private void Start()
        {
            if (!view || !actions || !chineseFont)
            {
                Debug.LogError("M2Player requires a world camera, input actions and Chinese UI font.", this);
                enabled = false;
                return;
            }
            motor = GetComponent<CharacterController>();
            hud = new M2InteractionHud(chineseFont);
            localActions = Instantiate(actions);
            move = localActions.FindAction("Player/Move", true);
            look = localActions.FindAction("Player/Look", true);
            interact = localActions.FindAction("Player/Interact", true);
            cancel = localActions.FindAction("UI/Cancel", true);
            SetInputMode(false);
        }

        private void OnEnable()
        {
            if (localActions) SetInputMode(false);
        }

        private void OnDisable()
        {
            if (!localActions) return;
            localActions.Disable();
            bool wasOpen = IsInterfaceOpen;
            ActiveTarget = FocusedTarget = null;
            SetCursor(true);
            if (wasOpen) InterfaceClosed?.Invoke();
        }

        private void OnDestroy()
        {
            if (localActions) Destroy(localActions);
        }

        private static void SetCursor(bool free)
        {
            Cursor.lockState = free ? CursorLockMode.None : CursorLockMode.Locked;
            Cursor.visible = free;
        }

        private void SetInputMode(bool modal)
        {
            if (modal)
            {
                move.Disable();
                look.Disable();
                interact.Disable();
                cancel.Enable();
            }
            else
            {
                cancel.Disable();
                move.Enable();
                look.Enable();
                interact.Enable();
            }
            SetCursor(modal);
        }

        private void Update()
        {
            if (IsInterfaceOpen)
            {
                if (cancel.WasPressedThisFrame()) CloseInterface();
                return;
            }

            Vector2 delta = look.ReadValue<Vector2>() * sensitivity;
            transform.Rotate(0f, delta.x, 0f);
            Pitch = Mathf.Clamp(Pitch - delta.y, -pitchLimit, pitchLimit);
            view.transform.localRotation = Quaternion.Euler(Pitch, 0f, 0f);

            Vector2 input = Vector2.ClampMagnitude(move.ReadValue<Vector2>(), 1f);
            Vector3 velocity = (transform.right * input.x + transform.forward * input.y) * movementSpeed;
            fallSpeed = motor.isGrounded ? -2f : Mathf.Max(fallSpeed + Physics.gravity.y * Time.deltaTime, -45f);
            velocity.y = fallSpeed;
            motor.Move(velocity * Time.deltaTime);

            Ray ray = view.ViewportPointToRay(new Vector3(0.5f, 0.5f));
            // Use eye-to-surface distance, including the camera's near clip segment.
            FocusedTarget = M2InteractionProbe.Find(new Ray(view.transform.position, ray.direction), interactionDistance, transform);
            if (FocusedTarget != null && interact.WasPressedThisFrame())
            {
                ActiveTarget = FocusedTarget;
                FocusedTarget = null;
                SetInputMode(true);
                InterfaceOpened?.Invoke(ActiveTarget);
            }
        }

        public void CloseInterface()
        {
            if (!IsInterfaceOpen) return;
            ActiveTarget = null;
            SetInputMode(false);
            InterfaceClosed?.Invoke();
        }

        private void OnGUI()
        {
            hud?.Draw(this);
        }
    }
}
