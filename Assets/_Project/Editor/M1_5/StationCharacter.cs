using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Echo.M15
{
    public static class StationCharacter
    {
        const string Art = "Assets/_Project/Art/Characters/M1_5/";
        const string Model = Art + "StationVisitor.fbx";
        const string Output = "Assets/_Project/Prefabs/Characters/M1_5";
        const string Name = "StationVisitor";
        static readonly string[] Parts = { "Skin", "Wardrobe", "Shoes", "Hair", "Eyes", "Brows", "Lashes", "Teeth" };

        // Invoked by the Station integrator after it verifies the editor is idle and the scene clean.
        public static void Apply()
        {
            var parent = GameObject.Find("Station/Characters")?.transform;
            if (!parent) throw new InvalidOperationException("Missing Station/Characters");
            var previous = parent.Find("NPC_VisualSample");
            if (!previous) throw new InvalidOperationException("Missing original NPC anchor");

            var prefab = PreparePrefab();
            var current = parent.Find(Name);
            if (!current) current = ((GameObject)PrefabUtility.InstantiatePrefab(prefab, parent)).transform;
            current.localPosition = previous.localPosition;
            var animator = current.GetComponentInChildren<Animator>();
            if (!animator || !animator.isHuman) throw new InvalidDataException("Reloaded visitor is missing a Humanoid avatar");

            // Measure under the same retargeted Humanoid idle that plays in the scene.
            // The FBX shoe mesh is stored in centimetres. Its Blender-verified sole lies
            // 23.48 mm beneath the toe joint. Taking the joint in world space avoids
            // applying the model importer's centimetre conversion twice to baked vertices.
            var probe=UnityEngine.Object.Instantiate(prefab);
            try
            {
                probe.transform.SetPositionAndRotation(previous.position,Quaternion.identity);
                var preview=probe.GetComponentInChildren<Animator>();
                preview.cullingMode=AnimatorCullingMode.AlwaysAnimate;
                preview.Rebind();
                int idle=Animator.StringToHash("Base Layer.StandingIdle");
                if (!preview.HasState(0,idle)) throw new InvalidDataException("StandingIdle controller state unavailable");
                preview.Play(idle,0,.25f);
                preview.Update(0f);
                var left=preview.GetBoneTransform(HumanBodyBones.LeftToes);
                var right=preview.GetBoneTransform(HumanBodyBones.RightToes);
                var heel=preview.GetBoneTransform(HumanBodyBones.LeftFoot);
                if (!left || !right || !heel) throw new InvalidDataException("Missing visitor foot joints");
                float soleY=Mathf.Min(left.position.y,right.position.y)-.02348f;
                float offset=previous.position.y+.001f-soleY;
                if (Mathf.Abs(offset)>.16f) throw new InvalidDataException("Sampled idle sole out of range: "+offset);
                current.position=previous.position+Vector3.up*offset;
                var anchor=GameObject.Find("Station_NPC").transform;
                var forward=Vector3.ProjectOnPlane(left.position-heel.position,Vector3.up);
                var target=Vector3.ProjectOnPlane(anchor.position-current.position,Vector3.up);
                current.rotation=Quaternion.AngleAxis(Vector3.SignedAngle(forward,target,Vector3.up),Vector3.up);
                Debug.Log($"M1.5 sampled StandingIdle heel={heel.position.y:F4} sole={soleY:F4} offset={offset:F4}");
            }
            finally { UnityEngine.Object.DestroyImmediate(probe); }
            PrefabUtility.RecordPrefabInstancePropertyModifications(current);
            previous.gameObject.SetActive(false);
            PrefabUtility.RecordPrefabInstancePropertyModifications(previous.gameObject);
        }

        [MenuItem("Tools/Echo/M1.5/Verify character prefab")]
        public static void Verify() => PreparePrefab();

        static GameObject PreparePrefab()
        {
            var importer = AssetImporter.GetAtPath(Model) as ModelImporter;
            if (!importer) throw new FileNotFoundException(Model);
            bool reimport = false;
            if (importer.animationType != ModelImporterAnimationType.Human || importer.avatarSetup != ModelImporterAvatarSetup.CreateFromThisModel)
            {
                importer.animationType = ModelImporterAnimationType.Human;
                importer.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
                reimport = true;
            }
            var clips = importer.clipAnimations.Length>0 ? importer.clipAnimations : importer.defaultClipAnimations;
            if (clips.Length != 1) throw new InvalidDataException("Expected a single FBX idle take; found "+clips.Length);
            if (!clips[0].loopTime || clips[0].name!="StandingIdle")
            {
                clips[0].loopTime = true;
                clips[0].name = "StandingIdle";
                clips[0].lockRootRotation = true;
                clips[0].lockRootHeightY = true;
                clips[0].lockRootPositionXZ = true;
                importer.clipAnimations = clips;
                reimport = true;
            }
            if (reimport) importer.SaveAndReimport();

            EnsureFolder("Assets/_Project/Prefabs","Characters");
            EnsureFolder("Assets/_Project/Prefabs/Characters","M1_5");
            var avatar = AssetDatabase.LoadAllAssetsAtPath(Model).OfType<Avatar>().SingleOrDefault();
            var clip = AssetDatabase.LoadAllAssetsAtPath(Model).OfType<AnimationClip>().SingleOrDefault(c => c.name=="StandingIdle");
            if (!avatar || !avatar.isValid || !avatar.isHuman || !clip || !clip.isHumanMotion)
                throw new InvalidDataException("Invalid imported humanoid or idle motion. Inspect "+Model);
            string controllerPath = Output+"/StationVisitor.controller";
            var controller = AssetDatabase.LoadAssetAtPath<AnimatorController>(controllerPath);
            if (!controller)
            {
                controller=AnimatorController.CreateAnimatorControllerAtPath(controllerPath);
                controller.AddMotion(clip);
                AssetDatabase.SaveAssetIfDirty(controller);
            }
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(Model);
            var instance=(GameObject)PrefabUtility.InstantiatePrefab(model);
            var wrapper = new GameObject(Name);
            try
            {
                instance.transform.SetParent(wrapper.transform,false);
                var animator = instance.GetComponent<Animator>();
                animator.avatar=avatar;
                animator.runtimeAnimatorController=controller;
                animator.applyRootMotion=false;
                PrefabUtility.RecordPrefabInstancePropertyModifications(animator);
                var renderers=instance.GetComponentsInChildren<SkinnedMeshRenderer>();
                foreach (string label in Parts)
                {
                    var renderer = renderers.Single(r=>r.name==label);
                    renderer.sharedMaterial=MaterialFor(label);
                    // The full-body shot resolves the CC0 brow and lash coverage on
                    // the animated skin UVs. Separate cutout cards alias at this size.
                    renderer.enabled=label!="Brows" && label!="Lashes";
                    PrefabUtility.RecordPrefabInstancePropertyModifications(renderer);
                }
                string prefabPath=Output+"/"+Name+".prefab";
                if(!PrefabUtility.SaveAsPrefabAsset(wrapper,prefabPath)) throw new IOException(prefabPath);
                var stored=PrefabUtility.LoadPrefabContents(prefabPath);
                try
                {
                    if(!stored.GetComponentInChildren<Animator>().isHuman || stored.GetComponentsInChildren<SkinnedMeshRenderer>().Length!=Parts.Length)
                        throw new InvalidDataException("Visitor prefab failed reload validation");
                }
                finally {PrefabUtility.UnloadPrefabContents(stored);}
                return AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            }
            finally { UnityEngine.Object.DestroyImmediate(wrapper); }
        }

        static void EnsureFolder(string parent,string name)
        {
            if (!AssetDatabase.IsValidFolder(parent+"/"+name)) AssetDatabase.CreateFolder(parent,name);
        }

        static Material MaterialFor(string part)
        {
            string path=Art+part+".mat";
            var mat=AssetDatabase.LoadAssetAtPath<Material>(path);
            if (!mat)
            {
                mat=new Material(Shader.Find("HDRP/Lit"));
                AssetDatabase.CreateAsset(mat,path);
            }
            mat.SetTexture("_BaseColorMap",AssetDatabase.LoadAssetAtPath<Texture2D>(Art+part+"_Color.png"));
            bool cutout=part=="Hair" || part=="Brows" || part=="Lashes";
            // The system eye atlas uses a transparent cornea region over the iris.
            mat.SetFloat("_AlphaCutoffEnable",cutout || part=="Eyes"?1:0);
            if (part=="Skin") mat.SetColor("_BaseColor",new Color(.88f,.85f,.84f));
            mat.SetFloat("_AlphaCutoff",part=="Eyes"?.12f:part=="Hair"?.27f:.22f);
            mat.SetFloat("_DoubleSidedEnable",cutout?1:0);
            mat.SetFloat("_Smoothness",part=="Eyes"?.56f:part=="Skin"?.39f:part=="Teeth"?.51f:.32f);
            string normal=Art+part+"_Normal.png";
            if (AssetImporter.GetAtPath(normal) is TextureImporter imp)
            {
                if (imp.textureType!=TextureImporterType.NormalMap)
                {
                    imp.textureType=TextureImporterType.NormalMap;
                    imp.SaveAndReimport();
                }
                mat.SetTexture("_NormalMap",AssetDatabase.LoadAssetAtPath<Texture2D>(normal));
                mat.SetFloat("_NormalScale",.7f);
            }
            if (part=="Skin")
            {
                const string profilePath="Packages/com.unity.render-pipelines.high-definition/Runtime/RenderPipelineResources/SkinDiffusionProfile.asset";
                var profile=AssetDatabase.LoadAssetAtPath<DiffusionProfileSettings>(profilePath);
                if (!profile) throw new FileNotFoundException(profilePath);
                mat.SetFloat("_MaterialID",0);
                mat.SetFloat("_SubsurfaceMask",.55f);
                HDMaterial.SetDiffusionProfile(mat,profile);
            }
            if (part=="Skin" || part=="Wardrobe")
            {
                string mask=Art+part+"_Mask.png";
                var maskImporter=(TextureImporter)AssetImporter.GetAtPath(mask);
                if (!maskImporter) throw new FileNotFoundException(mask);
                if (maskImporter.sRGBTexture)
                {
                    maskImporter.sRGBTexture=false;
                    maskImporter.SaveAndReimport();
                }
                mat.SetTexture("_MaskMap",AssetDatabase.LoadAssetAtPath<Texture2D>(mask));
            }
            HDMaterial.ValidateMaterial(mat);
            EditorUtility.SetDirty(mat);
            AssetDatabase.SaveAssetIfDirty(mat);
            return mat;
        }
    }
}
