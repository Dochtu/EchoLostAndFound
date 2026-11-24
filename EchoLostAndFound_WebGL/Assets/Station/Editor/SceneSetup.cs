using System;
using System.Linq;
using EchoLostAndFound.M2;
using TMPro;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace EchoStation
{
    public static class SceneSetup
    {
        const string Root = "Assets/Station/";
        public const string ScenePath = Root + "Scenes/Station.unity";
        static TMP_FontAsset font;
        static Material teal, brass, slate, ivory, pine;

        [MenuItem("Echo/Generate WebGL station")]
        public static void Generate()
        {
            foreach (var folder in new[] {"Scenes", "Materials"})
                if (!AssetDatabase.IsValidFolder(Root + folder))
                    AssetDatabase.CreateFolder("Assets/Station", folder);
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            font = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>("Assets/TextMesh Pro/Resources/Fonts & Materials/LiberationSans SDF.asset");
            if (font == null) throw new InvalidOperationException("Missing LiberationSans SDF");
            teal = Mat("Enamel", "#285250");
            brass = Mat("Brass", "#CD9A4B");
            slate = Mat("Stone", "#485660");
            ivory = Mat("Porcelain", "#E4DCC6");
            pine = Mat("Timber", "#745640");

            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(.68f, .70f, .72f);
            var light = new GameObject("Late afternoon").AddComponent<Light>();
            light.type = LightType.Directional;
            light.transform.rotation = Quaternion.Euler(50, -30, 0);
            light.color = new Color(1, .93f, .79f);
            light.intensity = 1.25f;
            BuildHall();
            var npc = Model("StationVisitor", "Station visitor", new Vector3(0,0,0), 1.75f, true, teal);
            Target(npc, InteractionKind.Npc, "老周", new Vector3(.8f,1.8f,.65f));
            Box("Watch plinth", 1.04f,.60f,.0f, .84f,1.20f,.68f, pine);
            var watch = Model("EvidenceWatch", "Pocket watch", new Vector3(1.04f,1.20f,0), .35f, false, brass);
            Target(watch, InteractionKind.Item, "怀表", new Vector3(.50f,.32f,.46f));
            var cabinet = Box("Repair cabinet",-3.1f,1.05f,3.42f, 1.12f,2.10f,.34f, teal);
            cabinet.isStatic = true;
            // The primitive already owns a BoxCollider, so the cabinet only needs the interaction marker.
            cabinet.AddComponent<M2Interactable>().Configure("维修柜", InteractionKind.Document);
            // Chapter-01 investigation props. Greybox placement only: the implementation map
            // still marks hotspot anchors [待确认], so these coordinates are not approved content.
            var linyao = Model("StationVisitor", "Station visitor (linyao)", new Vector3(-5.4f,0f,1.3f), 1.72f, true, slate);
            linyao.transform.rotation = Quaternion.Euler(0,80,0);
            Target(linyao, InteractionKind.Npc, "林遥", new Vector3(.8f,1.8f,.65f));
            Box("West office window",-6.86f,1.95f,1.3f,.12f,1.3f,2.2f,ivory);
            Box("West office sill",-6.5f,1.22f,1.3f,.55f,.1f,2.2f,pine);
            Box("Package stand",1.86f,.44f,.55f,.18f,.88f,.18f,pine);
            var package = Box("Lost property package",1.86f,.93f,.55f,.52f,.12f,.40f,ivory);
            package.AddComponent<M2Interactable>().Configure("失物包", InteractionKind.Document);
            Box("Binder stand",-1.5f,.5f,1.0f,.18f,1.0f,.18f,pine);
            var binder = Box("Lost-property binder",-1.5f,1.03f,1.0f,.34f,.06f,.46f,teal);
            binder.AddComponent<M2Interactable>().Configure("副联册", InteractionKind.Document);
            var player = new GameObject("Investigator");
            player.transform.position = new Vector3(0,.02f,-2);
            var motor = player.AddComponent<CharacterController>();
            motor.height = 1.8f; motor.radius = .28f; motor.center = new Vector3(0,.9f,0);
            var view = new GameObject("Player view").AddComponent<Camera>();
            view.transform.SetParent(player.transform, false);
            view.transform.localPosition = new Vector3(0,1.57f,0);
            view.tag = "MainCamera"; view.fieldOfView = 67;
            view.clearFlags = CameraClearFlags.SolidColor;
            view.backgroundColor = new Color(.27f,.37f,.42f);
            view.nearClipPlane = .05f; view.farClipPlane = 45;
            view.gameObject.AddComponent<AudioListener>();
            var actions = AssetDatabase.LoadAssetAtPath<InputActionAsset>(Root + "StationInput.inputactions");
            if (actions == null) throw new InvalidOperationException("Station input asset missing");
            player.AddComponent<StationPlayer>().Configure(view, actions, MakeHud());
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new Exception("Unable to save station scene");
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
        }

        static void BuildHall()
        {
            Box("Platform", 0,-.14f,0, 14,.28f,16, slate);
            Box("Rear wall", 0,1.9f,4, 14,3.8f,.2f, ivory);
            Box("Baseboard", 0,.47f,3.85f, 14,.94f,.13f, teal);
            Box("South wall", 0,1.8f,-8, 14,3.6f,.2f, pine);
            Box("West wall", -7,1.8f,0, .2f,3.6f,16, teal);
            Box("East boundary", 7,.65f,0, .16f,1.3f,16, slate);
            Box("Roof", 0,4.0f,0, 14,.16f,16, ivory);
            for (int z=-6; z<=3; z+=3)
            {
                Box("Beam",0,3.8f,z,14,.22f,.16f,teal);
                Box("Pillar",6,1.9f,z,.21f,3.8f,.21f,teal);
                Box("Ceiling lamp",0,3.65f,z,2.6f,.08f,.22f,ivory);
            }
            for (int z=-7; z<4; z+=2)
                Box("Platform edge",5.65f,.012f,z,.12f,.018f,1.75f,brass);
            Box("Station board", 0,2.52f,3.79f,6.9f,1.17f,.12f,teal);
            Box("Board rule",0,2.07f,3.70f,6.5f,.025f,.025f,brass);
            Sign("LOST   &   FOUND",new Vector3(0,2.62f,3.70f),4.2f);
            Sign("STATION OFFICE     /     PLATFORM 02",new Vector3(0,2.24f,3.69f),1.35f);
            for (int i=0;i<2;i++)
            {
                float x = i == 0 ? -4.8f : 4.8f;
                var bench = Model("HallSettee_LOD2","Waiting bench",new Vector3(x,0,2.9f),2.2f,false,pine);
                var collider = bench.AddComponent<BoxCollider>();
                collider.center = new Vector3(0,.42f,0); collider.size = new Vector3(2.2f,.84f,.65f);
                Box("Window frame",x,2.2f,3.8f,2.35f,1.65f,.12f,teal);
                Box("Window glass",x,2.2f,3.7f,2.17f,1.46f,.04f,slate);
                Box("Mullion",x,2.2f,3.65f,.055f,1.46f,.05f,ivory);
            }
        }

        static Material Mat(string name, string hex)
        {
            string path = Root + "Materials/" + name + ".mat";
            var material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (!material)
            {
                material = new Material(Shader.Find("Universal Render Pipeline/Lit"));
                AssetDatabase.CreateAsset(material, path);
            }
            ColorUtility.TryParseHtmlString(hex, out var color);
            material.SetColor("_BaseColor", color);
            material.SetFloat("_Smoothness", .18f);
            EditorUtility.SetDirty(material);
            return material;
        }

        static GameObject Box(string name,float x,float y,float z,float w,float h,float d,Material material)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.position = new Vector3(x,y,z);
            go.transform.localScale = new Vector3(w,h,d);
            go.GetComponent<MeshRenderer>().sharedMaterial = material;
            go.isStatic = true;
            return go;
        }

        static void Sign(string text, Vector3 at, float size)
        {
            var sign = new GameObject(text).AddComponent<TextMeshPro>();
            sign.transform.position = at;
            sign.rectTransform.sizeDelta = new Vector2(6.6f,1);
            sign.font = font;
            sign.text = text; sign.fontSize = size;
            sign.alignment = TextAlignmentOptions.Center;
            sign.color = ivory.GetColor("_BaseColor");
        }

        static GameObject Model(string file, string name, Vector3 feet, float size, bool fitHeight, Material material)
        {
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>(Root+"Models/"+file+".fbx");
            var holder = new GameObject(name);
            var visual = (GameObject)PrefabUtility.InstantiatePrefab(asset, holder.transform);
            var renderers = visual.GetComponentsInChildren<Renderer>();
            var bounds = renderers[0].bounds;
            foreach (var renderer in renderers)
            {
                bounds.Encapsulate(renderer.bounds);
                renderer.sharedMaterials = renderer.sharedMaterials.Select(m =>
                {
                    string label = m ? m.name.ToLowerInvariant() : "";
                    if (file == "StationVisitor" && (label.Contains("skin") || label.Contains("face"))) return ivory;
                    if (file == "StationVisitor" && (label.Contains("hair") || label.Contains("boot"))) return pine;
                    if (file == "EvidenceWatch" && label.Contains("dial")) return ivory;
                    return material;
                }).ToArray();
                renderer.shadowCastingMode = ShadowCastingMode.Off;
            }
            float scale = size / (fitHeight ? bounds.size.y : Mathf.Max(bounds.size.x,bounds.size.y,bounds.size.z));
            visual.transform.localScale *= scale;
            visual.transform.localPosition -= new Vector3(bounds.center.x,bounds.min.y,bounds.center.z)*scale;
            holder.transform.position = feet;
            return holder;
        }

        static void Target(GameObject target, InteractionKind kind, string label, Vector3 size)
        {
            var collider = target.AddComponent<BoxCollider>();
            collider.size = size; collider.center = new Vector3(0,size.y*.5f,0);
            target.AddComponent<M2Interactable>().Configure(label,kind);
        }

        static StationHud MakeHud()
        {
            var canvas = new GameObject("Station HUD",typeof(RectTransform),typeof(Canvas),typeof(CanvasScaler));
            canvas.GetComponent<Canvas>().renderMode = RenderMode.ScreenSpaceOverlay;
            var scaler = canvas.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(960,600); scaler.matchWidthOrHeight = .5f;
            var parent = canvas.transform;
            var bar = Rect("Controls",parent,new Vector2(.5f,0),new Vector2(0,22),new Vector2(500,35));
            bar.gameObject.AddComponent<Image>().color = new Color(.045f,.09f,.10f,.9f);
            Label(bar,"WASD   Move       Mouse   Look       E   Interact       Esc   Release", 15,Vector2.zero, new Vector2(495,30));
            var focus = Label(parent,"Click to explore",21,new Vector2(0,-40),new Vector2(490,35));
            var dot = Label(parent,"+",18,Vector2.zero,new Vector2(28,28));
            var sheet = Rect("Inspection",parent,new Vector2(.5f,.5f),Vector2.zero,new Vector2(560,470));
            sheet.gameObject.AddComponent<Image>().color = new Color(.035f,.085f,.095f,1f);
            var heading = Label(sheet,"",26,new Vector2(0,210),new Vector2(520,34));
            heading.color = new Color(1,.83f,.54f);
            var body = Label(sheet,"",17,new Vector2(0,130),new Vector2(520,116));
            body.alignment = TextAlignmentOptions.Top;
            Label(sheet,"E    返回车站",15,new Vector2(0,-210),new Vector2(260,24));
            sheet.gameObject.SetActive(false);
            var hud = canvas.AddComponent<StationHud>();
            hud.Configure(focus,heading,body,sheet.gameObject,dot.gameObject);
            return hud;
        }

        static RectTransform Rect(string name,Transform parent,Vector2 anchor,Vector2 offset,Vector2 size)
        {
            var rect = (RectTransform)new GameObject(name,typeof(RectTransform)).transform;
            rect.SetParent(parent,false);
            rect.anchorMin = rect.anchorMax = anchor;
            rect.sizeDelta = size; rect.anchoredPosition = offset;
            return rect;
        }

        static TMP_Text Label(Transform parent,string text,int size,Vector2 offset,Vector2 dimensions)
        {
            var rect = Rect("Label",parent,new Vector2(.5f,.5f),offset,dimensions);
            var label = rect.gameObject.AddComponent<TextMeshProUGUI>();
            label.font = font; label.fontSize = size; label.text = text;
            label.alignment = TextAlignmentOptions.Center; label.raycastTarget = false;
            return label;
        }
    }
}
