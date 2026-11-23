using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;
using UnityEngine.SceneManagement;

// Editor acceptance checks also run against the reopened on-disk scene before capture.
public static class Stage4SceneValidationTests
{
    const string Evidence = "Docs/Evidence/Stage4_M0_M1";
    public static readonly string[] Anchors = {
        "Station_MainHall", "Station_LostFound", "Station_Watch", "Station_NPC", "Station_Platform"
    };

    [MenuItem("Tools/Echo/Validate open Station scene")]
    public static void Run()
    {
        var rows = new List<string>();
        var failures = new List<string>();
        void Check(bool condition, string message)
        {
            rows.Add((condition ? "PASS " : "FAIL ") + message);
            if (!condition) failures.Add(message);
        }
        var scene = SceneManager.GetActiveScene();
        var objects = scene.GetRootGameObjects().SelectMany(x => x.GetComponentsInChildren<Transform>(true)).ToArray();
        T[] Components<T>() where T : Component => objects.SelectMany(t => t.GetComponents<T>()).ToArray();
        Check(scene.path == "Assets/_Project/Scenes/Station.unity", "active scene " + scene.path);
        Check(GraphicsSettings.currentRenderPipeline is HDRenderPipelineAsset, "active pipeline " + GraphicsSettings.currentRenderPipeline);
        var missing = objects.Where(t => GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject) != 0).ToArray();
        Check(missing.Length == 0, "missing script owners " + string.Join(", ", missing.Select(t => t.name)));
        var badMeshes = Components<MeshFilter>().Where(f => !f.sharedMesh && !f.GetComponent<TMP_Text>()).ToArray();
        Check(badMeshes.Length == 0, "unassigned MeshFilters " + string.Join(", ", badMeshes.Select(t => t.name)));
        var renderers = Components<Renderer>().Where(r => r.enabled && r.gameObject.activeInHierarchy && r is not ParticleSystemRenderer).ToArray();
        var broken = renderers.Where(r => r.sharedMaterials.Length == 0 || r.sharedMaterials.Any(
            m => !m || !m.shader || !m.shader.isSupported || m.shader.name == "Hidden/InternalErrorShader")).ToArray();
        Check(renderers.Length > 0 && broken.Length == 0, $"visible renderer components {renderers.Length}, invalid material owners " + string.Join(", ", broken.Select(t=>t.name)));
        var camera = Camera.main;
        Check(camera && camera.GetComponent<HDAdditionalCameraData>() && Components<Camera>().Count(c => c.isActiveAndEnabled) == 1, "one active main HDRP camera");
        foreach (string anchor in Anchors)
            Check(objects.Count(t => t.name == anchor) == 1 && GameObject.Find(anchor)?.GetComponent<Camera>() != null, "shot anchor " + anchor);
        var profiles = Components<Volume>().Where(v => v.isActiveAndEnabled && v.isGlobal && v.sharedProfile).Select(v => v.sharedProfile).ToArray();
        Check(profiles.Any(p => p.TryGet<Exposure>(out var e) && e.active && p.TryGet<Fog>(out var f) && f.active && p.TryGet<Tonemapping>(out var t) && t.active), "active global exposure, fog and tonemapping");
        int lights = Components<Light>().Count(l => l.isActiveAndEnabled && l.intensity > 0 && l.GetComponent<HDAdditionalLightData>());
        Check(lights > 1, "enabled HDRP lights " + lights);
        Check(Components<ReflectionProbe>().Any(p => p.enabled), "reflection probe present");
        var rain = Components<ParticleSystem>().Where(p => p.gameObject.activeInHierarchy && p.emission.enabled).ToArray();
        Check(rain.Length >= 2, "rain and eave emitters " + string.Join(", ", rain.Select(p=>p.name)));
        var instances = objects.Where(t=>PrefabUtility.IsAnyPrefabInstanceRoot(t.gameObject)).ToArray();
        Check(instances.Length > 0 && instances.All(t=>PrefabUtility.GetPrefabInstanceStatus(t.gameObject) == PrefabInstanceStatus.Connected),
            "prefab instances " + string.Join(", ", instances.Select(t => t.name)));
        foreach(string zone in new[]{"LostAndFound","WaitingHall","Platform"})
        {
            var area=GameObject.Find("Station/Environment/" + zone);
            Check(area && area.GetComponentsInChildren<MeshRenderer>().Length>0 && PrefabUtility.IsPartOfPrefabInstance(area), "mesh-bearing environment prefab " + zone);
        }
        var watch=GameObject.Find("Station/Props/PocketWatch");
        if(watch)
        {
            var texts=watch.GetComponentsInChildren<TMP_Text>().Select(t=>t.text).ToArray();
            Check(texts.Contains("0412·0916") && texts.Contains("QH-283"), "watch back and rim inscriptions");
            bool Needle(string name,float angle)
            {
                var hand=watch.transform.Find("Dial/"+name);
                return hand && hand.GetComponent<MeshRenderer>() && Mathf.Abs(Mathf.DeltaAngle(angle,hand.localEulerAngles.y))<.1f;
            }
            Check(Needle("HourHand",278.5f) && Needle("MinuteHand",102f), "analog hands at 9:17");
        }
        Check(watch && PrefabUtility.IsPartOfPrefabInstance(watch), "reusable watch placed in scene");
        var npc=GameObject.Find("Station/Characters/NPC_VisualSample");
        if(npc)
        {
            var parts=npc.GetComponentsInChildren<Transform>();
            var bounds=new Bounds();
            var surfaces=npc.GetComponentsInChildren<MeshRenderer>();
            if(surfaces.Length>0) {bounds=surfaces[0].bounds; foreach(var s in surfaces) bounds.Encapsulate(s.bounds);}
            Check(parts.Any(t=>t.name=="Head") && parts.Count(t=>t.name.StartsWith("Arm"))>=2 && parts.Count(t=>t.name.StartsWith("Leg"))>=2 &&
                bounds.size.y>1.2f && bounds.size.y<2.2f && Mathf.Abs(bounds.min.y)<.08f,
                $"human sample limbs, height={bounds.size.y:F3}m, feet={bounds.min.y:F3}m");
        }
        Check(npc && PrefabUtility.IsPartOfPrefabInstance(npc), "reusable NPC placed in scene");
        var portals = typeof(HandleUtility).GetMethod("IntersectRayMesh",BindingFlags.Static|BindingFlags.NonPublic|BindingFlags.Public,
            null,new[]{typeof(Ray),typeof(Mesh),typeof(Matrix4x4),typeof(RaycastHit).MakeByRefType()},null);
        foreach(var door in new[]{new Vector3(-6,0,-3.05f),new Vector3(6,0,.95f)})
        {
            var blocked=new HashSet<string>();
            if(portals!=null)
            foreach(var offset in new[]{-.3f,0,.3f})
            foreach(var height in new[]{.2f,.95f,1.7f})
            foreach(var sign in new[]{-1,1})
            {
                var ray=new Ray(door+new Vector3(-sign*1.4f,height,offset),Vector3.right*sign);
                foreach(var mesh in Components<MeshFilter>())
                {
                    var r=mesh.GetComponent<MeshRenderer>();
                    if(!r || !r.enabled || !mesh.sharedMesh || !r.bounds.IntersectRay(ray,out var first) || first>2.8f) continue;
                    object[] args={ray,mesh.sharedMesh,mesh.transform.localToWorldMatrix,default(RaycastHit)};
                    if((bool)portals.Invoke(null,args) && ((RaycastHit)args[3]).distance<2.8f) blocked.Add(mesh.name);
                }
            }
            Check(portals!=null && blocked.Count==0,$"clear rendered doorway at {door}; occluders {string.Join(",",blocked)}");
        }
        rows.Insert(0, DateTime.Now.ToString("s") + " QA inspection; editor " + Application.unityVersion + "; objects " + objects.Length);
        Directory.CreateDirectory(Evidence);
        File.WriteAllLines(Path.Combine(Evidence, "QARuntime.log"), rows);
        if(failures.Count > 0) Debug.LogError("Station validation failed: " + string.Join(" | ", failures));
    }
}
