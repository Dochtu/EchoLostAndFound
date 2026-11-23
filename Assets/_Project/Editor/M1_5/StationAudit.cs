using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace Echo.M15
{
    internal static class StationAudit
    {
        internal static void Run(string destination="Docs/Evidence/Stage4_M1_5/AssetValidation.log")
        {
            if(SceneManager.GetActiveScene().path!="Assets/_Project/Scenes/Station.unity") throw new InvalidOperationException("Open saved Station first");
            var lines=new List<string>{DateTime.Now.ToString("s")+" Station disk reload audit"};
            var errors=new List<string>();
            var all=SceneManager.GetActiveScene().GetRootGameObjects().SelectMany(root=>root.GetComponentsInChildren<Transform>(true)).ToArray();
            foreach(var tr in all)
            {
                if(GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(tr.gameObject)>0) errors.Add("Missing script "+tr.name);
                var r=tr.GetComponent<Renderer>();
                if(r && r.enabled && tr.gameObject.activeInHierarchy && r.sharedMaterials.Any(m=>!m || !m.shader || !m.shader.isSupported))
                    errors.Add("Invalid active material "+tr.name);
            }
            lines.Add("Transforms including preserved originals="+all.Length);
            foreach(string guid in AssetDatabase.FindAssets("t:Prefab",new[]{"Assets/_Project/Prefabs"}))
            {
                string path=AssetDatabase.GUIDToAssetPath(guid);
                if(!path.Contains("/M1_5/")) continue;
                var root=PrefabUtility.LoadPrefabContents(path);
                try
                {
                    var meshes=root.GetComponentsInChildren<MeshFilter>(true).Select(f=>f.sharedMesh).Concat(root.GetComponentsInChildren<SkinnedMeshRenderer>(true).Select(f=>f.sharedMesh)).ToArray();
                    if(meshes.Length==0 || meshes.Any(m=>!m || m.vertexCount==0 || m.bounds.size.sqrMagnitude==0)) errors.Add("Invalid mesh "+path);
                    var lod=root.GetComponent<LODGroup>();
                    lines.Add($"Reopened {path} meshes={meshes.Length} lods={(lod?lod.lodCount:1)}");
                }
                finally {PrefabUtility.UnloadPrefabContents(root);}
            }
            var npc=GameObject.Find("Station/Characters/StationVisitor").GetComponentInChildren<Animator>();
            var idle=npc.runtimeAnimatorController.animationClips.Single(c=>c.name=="StandingIdle");
            lines.Add($"Visitor validAvatar={npc.avatar.isValid} isHuman={npc.isHuman} idleSeconds={idle.length:F2} loop={idle.isLooping} renderers={npc.GetComponentsInChildren<SkinnedMeshRenderer>().Length}");
            if(!npc.isHuman || !npc.avatar.isValid || !idle.isLooping) errors.Add("Character rig/idle");
            foreach(var name in HallIntegration.ShotNames.Distinct()) if(!GameObject.Find(name)?.GetComponent<Camera>()) errors.Add("Missing shot "+name);
            lines.Add("Issues="+errors.Count);lines.AddRange(errors);
            File.WriteAllLines(destination,lines);
            if(errors.Count>0) throw new InvalidDataException(string.Join(", ",errors));
        }
    }
}
