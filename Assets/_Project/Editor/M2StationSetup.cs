using System;
using System.IO;
using System.Linq;
using EchoLostAndFound.M2;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Rendering.HighDefinition;
using UnityEngine.SceneManagement;

public static class M2StationSetup
{
    const string ScenePath = "Assets/_Project/Scenes/Station.unity";
    const string PlayerPath = "Assets/_Project/Prefabs/Player/M2Player.prefab";

    [MenuItem("Tools/Echo/M2/Install exploration in Station")]
    public static void Apply()
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode)
            throw new InvalidOperationException("Stop Play Mode before installing exploration.");
        for (int i = 0; i < SceneManager.sceneCount; i++)
            if (SceneManager.GetSceneAt(i).isDirty)
                throw new InvalidOperationException("Save pending changes before opening Station.");

        var scene = EditorSceneManager.OpenScene(ScenePath);
        var station = GameObject.Find("Station").transform;
        var systems = Required(station, "SceneSystems");
        var preview = Required(station, "Cameras/StationPreviewCamera");
        var prefab = CreatePlayerPrefab(preview);
        var player = systems.Find("M2Player");
        if (!player) player = ((GameObject)PrefabUtility.InstantiatePrefab(prefab, systems)).transform;
        player.SetPositionAndRotation(new Vector3(-8.3f, .04f, -4.45f), Quaternion.Euler(0, -90, 0));
        PrefabUtility.RecordPrefabInstancePropertyModifications(player);
        preview.gameObject.SetActive(false);

        InstallBuildingCollision(Child(systems, "M2 Building Collision"));
        InstallTargets(station);
        EditorSceneManager.MarkSceneDirty(scene);
        if (!EditorSceneManager.SaveScene(scene)) throw new IOException("Failed to save " + ScenePath);
        EditorSceneManager.OpenScene(ScenePath);
        if (UnityEngine.Object.FindObjectsByType<M2Interactable>(FindObjectsSortMode.None).Length != 4 ||
            !Camera.main || !Camera.main.GetComponentInParent<M2Player>())
            throw new InvalidDataException("Unexpected M2 objects after Station reload.");
        Debug.Log("M2 Station installed and reloaded with connected player and four interaction targets.");
    }

    static Transform Required(Transform parent, string path)
    {
        var target = parent.Find(path);
        if (!target) throw new InvalidDataException("Missing Station object: " + path);
        return target;
    }

    static Transform Child(Transform parent, string name)
    {
        var target = parent.Find(name);
        if (target) return target;
        target = new GameObject(name).transform;
        target.SetParent(parent, false);
        return target;
    }

    static GameObject CreatePlayerPrefab(Transform preview)
    {
        var existing = AssetDatabase.LoadAssetAtPath<GameObject>(PlayerPath);
        var actions = AssetDatabase.LoadAssetAtPath<InputActionAsset>("Assets/InputSystem_Actions.inputactions");
        var font = AssetDatabase.LoadAssetAtPath<Font>("Assets/SourceHanSansSC-Regular.otf");
        if (!actions || !font) throw new InvalidDataException("Missing M2 input actions or Chinese font.");
        var root = existing ? PrefabUtility.LoadPrefabContents(PlayerPath) : new GameObject("M2Player");
        try
        {
            var capsule = root.GetComponent<CharacterController>();
            if (!capsule) capsule = root.AddComponent<CharacterController>();
            capsule.center = Vector3.up * .9f;
            capsule.height = 1.8f;
            capsule.radius = .28f;
            capsule.skinWidth = .035f;
            capsule.stepOffset = .2f;
            capsule.minMoveDistance = 0f;
            var eye = Child(root.transform, "PlayerCamera");
            eye.tag = "MainCamera";
            var camera = eye.GetComponent<Camera>();
            if (!camera) camera = eye.gameObject.AddComponent<Camera>();
            camera.CopyFrom(preview.GetComponent<Camera>());
            eye.SetLocalPositionAndRotation(Vector3.up * 1.65f, Quaternion.identity);
            camera.fieldOfView = 60f;
            camera.nearClipPlane = .035f;
            var hd = eye.GetComponent<HDAdditionalCameraData>();
            if (!hd) hd = eye.gameObject.AddComponent<HDAdditionalCameraData>();
            EditorUtility.CopySerialized(preview.GetComponent<HDAdditionalCameraData>(), hd);
            if (!eye.GetComponent<AudioListener>()) eye.gameObject.AddComponent<AudioListener>();
            var controller = root.GetComponent<M2Player>();
            if (!controller) controller = root.AddComponent<M2Player>();
            controller.Configure(camera, actions, font);
            var result = PrefabUtility.SaveAsPrefabAsset(root, PlayerPath);
            if (!result) throw new IOException(PlayerPath);
            return result;
        }
        finally
        {
            if (existing) PrefabUtility.UnloadPrefabContents(root);
            else UnityEngine.Object.DestroyImmediate(root);
        }
    }

    // Sizes follow the authored shell, open side doors, settees and canopy posts.
    // Keeping the floors continuous avoids capsule contacts on the tile seams.
    static void InstallBuildingCollision(Transform root)
    {
        void Box(string name, float x, float y, float z, float width, float height, float depth)
        {
            var part = Child(root, name);
            part.localPosition = new Vector3(x, y, z);
            SetBox(part, Vector3.zero, new Vector3(width, height, depth));
        }

        Box("Office floor", -9.5f, -.1f, -4, 7, .2f, 8);
        Box("Hall floor", 0, -.1f, 0, 12, .2f, 20);
        Box("Platform floor", 10, -.1f, 0, 8, .2f, 36);
        Box("Office outer wall", -13, 1.8f, -4, .2f, 3.6f, 8.2f);
        Box("Office south wall", -9.5f, 1.8f, -8, 7.2f, 3.6f, .2f);
        Box("Office north wall", -9.5f, 1.8f, 0, 7.2f, 3.6f, .2f);
        Box("Hall south wall", 0, 2.9f, -9.83f, 12.2f, 5.8f, .35f);
        Box("Hall north wall", 0, 2.9f, 9.83f, 12.2f, 5.8f, .35f);
        foreach (int side in new[] { -1, 1 })
        {
            float x = side * 6;
            float door = side < 0 ? -3.05f : .95f;
            float south = door - 1.29f, north = door + 1.29f;
            Box($"Wall {side} south", x, 2.9f, (-10 + south) / 2, .28f, 5.8f, south + 10);
            Box($"Wall {side} north", x, 2.9f, (10 + north) / 2, .28f, 5.8f, 10 - north);
            Box($"Lintel {side}", x, 4.45f, door, .28f, 2.7f, 2.58f);
            foreach (float z in new[] { -6.8f, -.4f, 6.5f })
                Box($"Bench {side} {z}", side * 3.05f, .49f, z, .79f, .98f, 2.86f);
            foreach (float z in new[] { -9.6f, -6f, -2f, 2f, 6f, 9.6f })
                Box($"Column {side} {z}", side * 5.48f, 2.6f, z, .56f, 5.2f, .56f);
            Box($"Platform end {side}", 10, 1.5f, side * 17.95f, 8.4f, 3f, .18f);
            Box($"Platform rear {side}", 6, 1.5f, side * 14f, .22f, 3f, 8.2f);
        }
        Box("Platform safety rail", 14.04f, 1.05f, 0, .12f, 2.1f, 36);
        Box("Maintenance cabinet", 7.14f, 1f, 6.1f, .80f, 2f, 1.56f);
        for (int i = -3; i <= 3; i++)
            Box($"Canopy post {i}", 8.19f, 1.91f, i * 5, .43f, 3.82f, .43f);
    }

    static void SetBox(Transform target, Vector3 center, Vector3 size)
    {
        var box = target.GetComponent<BoxCollider>();
        if (!box) box = target.gameObject.AddComponent<BoxCollider>();
        box.center = center;
        box.size = size;
    }

    static void Target(Transform owner, string label, InteractionKind kind)
    {
        var target = owner.GetComponent<M2Interactable>();
        if (!target) target = owner.gameObject.AddComponent<M2Interactable>();
        target.Configure(label, kind);
        EditorUtility.SetDirty(target);
        PrefabUtility.RecordPrefabInstancePropertyModifications(target);
    }

    static void InstallTargets(Transform station)
    {
        var counter = Required(station, "Environment/LostAndFound/Counter");
        var model = Required(counter, "M1_5 Intake cabinet");
        // An early M2 install placed the gameplay box in imported FBX coordinates.
        // Migrate only components added by that install, never prefab source components.
        var previous = model.GetComponent<M2Interactable>();
        if (previous && PrefabUtility.IsAddedComponentOverride(previous))
        {
            var previousBox = model.GetComponent<BoxCollider>();
            if (previousBox && PrefabUtility.IsAddedComponentOverride(previousBox))
                UnityEngine.Object.DestroyImmediate(previousBox);
            UnityEngine.Object.DestroyImmediate(previous);
        }
        var cabinet = Child(counter, "M2 Cabinet body");
        // M1.5 hid the previous cabinet geometry but kept its colliders.
        foreach (Transform child in counter)
        {
            var oldRenderer = child.GetComponent<Renderer>();
            if (!oldRenderer || oldRenderer.enabled) continue;
            foreach (var collider in child.GetComponents<Collider>())
            {
                collider.enabled = false;
                PrefabUtility.RecordPrefabInstancePropertyModifications(collider);
            }
        }
        SetBox(cabinet, Vector3.up * .5f, new Vector3(1.25f, 1, 3.74f));
        Target(cabinet, "柜台", InteractionKind.Counter);

        var books = counter.Cast<Transform>().Where(t => t.name == "Ledger binding")
            .OrderBy(t => t.localPosition.y).ToArray();
        if (books.Length != 3) throw new InvalidDataException("Expected three stacked register bindings.");
        var register = Child(counter, "M2 Register stack");
        register.localPosition = books[0].localPosition;
        SetBox(register, Vector3.up * .08f, new Vector3(.49f, .185f, .62f));
        Target(register, "登记册", InteractionKind.Item);

        var watch = Required(station, "Props/PocketWatch");
        SetBox(watch, Vector3.up * .014f, new Vector3(.13f, .035f, .13f));
        Target(watch, "怀表", InteractionKind.Item);

        var visitor = Required(station, "Characters/StationVisitor");
        var body = visitor.GetComponent<CapsuleCollider>();
        if (!body) body = visitor.gameObject.AddComponent<CapsuleCollider>();
        body.center = Vector3.up * .85f;
        body.height = 1.7f;
        body.radius = .27f;
        Target(visitor, "站内旅客", InteractionKind.Npc);
    }
}
