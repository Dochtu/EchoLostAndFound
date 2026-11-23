using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Profiling;
using UnityEngine.Rendering.HighDefinition;
using UnityEngine.SceneManagement;

namespace Echo.M15
{
    [InitializeOnLoad]
    internal static class HallIntegration
    {
        const string ScenePath = "Assets/_Project/Scenes/Station.unity";
        const string Models = "Assets/_Project/Art/Environment/M1_5/";
        const string Prefabs = "Assets/_Project/Prefabs/Environment/M1_5/";
        const string Evidence = "Docs/Evidence/Stage4_M1_5/";
        const string State = "Echo.M15.Capture";
        const string Request = "Temp/M15-Hall.request";
        static readonly List<float> frames = new List<float>();
        static int previousFrame;
        static double start;
        static readonly FrameTiming[] timing = new FrameTiming[1];
        static readonly List<double> cpu = new List<double>(), gpu = new List<double>(), render = new List<double>();
        static string Mean(List<double> values) => values.Count==0 ? "unavailable" : values.Average().ToString("F2");
        static string shot;
        static Animator visitor;
        static Transform leftToe,rightToe;
        static float lowestSole,highestSole,animFirst,animLast;
        static float blinkMin,blinkMax;
        static SkinnedMeshRenderer faceSkin;
        static int blinkShape;
        static EditorWindow game;

        static HallIntegration() => EditorApplication.update += Tick;
        static void Log(string message)
        {
            Directory.CreateDirectory(Evidence);
            File.AppendAllText(Evidence + "Hall.log", DateTime.Now.ToString("s") + " " + message + Environment.NewLine);
        }

        [MenuItem("Tools/Echo/M1.5/Integrate and capture hall")]
        public static void Run()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode) throw new InvalidOperationException("Editor is playing");
            for(int i=0; i<SceneManager.sceneCount; ++i)
                if (SceneManager.GetSceneAt(i).isDirty) throw new InvalidOperationException("Unsaved scene " + SceneManager.GetSceneAt(i).path);
            var scene = EditorSceneManager.OpenScene(ScenePath);
            var hall = GameObject.Find("Station/Environment/WaitingHall").transform;
            HallSurfaces.Prepare();
            if (!AssetDatabase.IsValidFolder(Prefabs.TrimEnd('/')))
                AssetDatabase.CreateFolder("Assets/_Project/Prefabs/Environment","M1_5");
            var bench = BuildPrefab("HallSettee");
            var bracket = BuildPrefab("PiercedVaultBracket");
            var column = BuildPrefab("HallColumn");
            var sash = BuildPrefab("HallSash");
            var pendant = BuildPrefab("HallPendant");
            var oldBenches = hall.Find("Hall_SlattedSettees").GetComponent<Renderer>();
            var changes = new Dictionary<string,string> {
                {"Station Aged Clear Glass","HallGlass"},{"Station Terrazzo Paving","Terrazzo"},{"Station Aged Walnut","AgedWood"},
                {"Station Smoked Oak","DarkWood"},{"Station Aged Oat Plaster","OldPlaster"} };
            foreach (var renderer in hall.GetComponentsInChildren<MeshRenderer>())
            {
                var slots = renderer.sharedMaterials;
                bool changed=false;
                for (int i=0;i<slots.Length;++i)
                    if (slots[i] && changes.TryGetValue(slots[i].name,out var name))
                    {
                        slots[i]=Load<Material>(HallSurfaces.Materials+name+".mat");
                        changed=true;
                    }
                if(changed) { renderer.sharedMaterials=slots; PrefabUtility.RecordPrefabInstancePropertyModifications(renderer); }
            }
            var group=hall.Find("M1_5 Hall fittings");
            if(!group)
            {
                group=new GameObject("M1_5 Hall fittings").transform;
                group.SetParent(hall,false);
            }
            int index=0;
            foreach (int side in new[]{-1,1})
            {
                foreach(float z in new[]{-6.8f,-.4f,6.5f})
                    Place(bench,group,index++,new Vector3(side*3.05f,0,z),-side*90f);
                foreach(float z in new[]{-9.6f,-6f,-2f,2f,6f,9.6f})
                    Place(bracket,group,index++,new Vector3(side*5.48f,5.61f,z),side<0?0:180);
            }
            foreach (int side in new[]{-1,1})
            {
                foreach(float z in new[]{-9.6f,-6f,-2f,2f,6f,9.6f})
                    Place(column,group,index++,new Vector3(side*5.48f,0,z),0);
                foreach(float x in new[]{-4.85f,-2.91f,-.97f,.97f,2.91f,4.85f})
                    Place(sash,group,index++,new Vector3(x,3.7f,side*9.84f),side>0?0:180);
            }
            var lights=GameObject.Find("Station/Lighting/InteriorLights").transform;
            foreach(Transform light in lights)
            {
                if(light.name=="Window bounce")
                {
                    // Diffuse window fill represents indirect skylight. A point highlight in the glass has no physical fixture.
                    light.GetComponent<HDAdditionalLightData>().affectSpecular=false;
                }
                if(light.name!="Hall pendant") continue;
                var practical=light.Find("Warm pool").GetComponent<Light>();
                var hd=practical.GetComponent<HDAdditionalLightData>();
                practical.transform.localPosition=new Vector3(0,-.48f,0);
                practical.intensity=1000;
                hd.shapeRadius=.21f;
                hd.volumetricDimmer=.65f;
                var fill=light.Find("Bowl indirect");
                if(!fill)
                {
                    fill=new GameObject("Bowl indirect").transform;
                    fill.SetParent(light,false);
                    fill.localPosition=Vector3.up*.45f;
                    fill.localRotation=Quaternion.Euler(-90,0,0);
                    var bounce=fill.gameObject.AddComponent<Light>();
                    bounce.type=LightType.Spot;
                    bounce.spotAngle=124;
                    bounce.color=new Color(1,.86f,.70f);
                    bounce.intensity=520;
                    bounce.range=6f;
                    var extra=bounce.GetComponent<HDAdditionalLightData>();
                    if(!extra) extra=bounce.gameObject.AddComponent<HDAdditionalLightData>();
                    extra.affectSpecular=false; extra.volumetricDimmer=0;
                }
                foreach (var r in light.GetComponentsInChildren<MeshRenderer>())
                    r.enabled=false;
                Place(pendant,group,index++,group.InverseTransformPoint(light.position),0);
            }
            // Broad reflected light from the warm interior and the cool window bays reveals
            // the transverse flange and column caps without changing camera exposure.
            foreach(int side in new[]{-1,1})
            {
                foreach(float z in new[]{-7f,0f,7f})
                {
                    string key=$"Hall clerestory bounce {side} {z}";
                    var transform=lights.Find(key);
                    if(!transform)
                    {
                        transform=new GameObject(key).transform;
                        transform.SetParent(lights,false);
                        transform.gameObject.AddComponent<Light>();
                    }
                    transform.position=hall.TransformPoint(new Vector3(side*2.72f,3.65f,z-1.4f));
                    transform.LookAt(hall.TransformPoint(new Vector3(side*4.95f,5.9f,z+.75f)));
                    var lamp=transform.GetComponent<Light>();
                    lamp.type=LightType.Spot;
                    lamp.range=8; lamp.spotAngle=105; lamp.innerSpotAngle=43;
                    lamp.color=side<0?new Color(1,.83f,.64f):new Color(.79f,.85f,1);
                    lamp.intensity=920; lamp.shadows=LightShadows.None;
                    var hd=lamp.GetComponent<HDAdditionalLightData>();
                    if(!hd) hd=lamp.gameObject.AddComponent<HDAdditionalLightData>();
                    hd.shapeRadius=.55f; hd.volumetricDimmer=0;
                }
            }
            Place(BuildPrefab("HallVault"),group,index++,Vector3.zero,0);
            Place(BuildPrefab("HallPaving"),group,index++,Vector3.zero,0);
            foreach(string old in new[]{"Hall_Terrazzo","Hall_BarrelVaultAndRibs"})
            {
                var r=hall.Find(old).GetComponent<Renderer>();
                r.enabled=false;
                PrefabUtility.RecordPrefabInstancePropertyModifications(r);
            }
            oldBenches.enabled=false;
            PrefabUtility.RecordPrefabInstancePropertyModifications(oldBenches);
            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene)) throw new IOException("Could not save Station");
            EditorSceneManager.OpenScene(ScenePath);
            var saved=GameObject.Find("Station/Environment/WaitingHall/M1_5 Hall fittings");
            if (!saved || saved.transform.childCount!=47) throw new IOException("Reloaded hall fittings count");
            Log("Reloaded Station with 6 settees, 12 cast brackets, 12 fluted columns, 12 sashes and 3 pendants. Replaced vault and pavement; diffuse window fill, pendant bowl bounce and softened practicals. Fixed shot anchor.");
            game=EditorWindow.GetWindow(typeof(Editor).Assembly.GetType("UnityEditor.GameView"));
            game.GetType().GetMethod("SetCustomResolution",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic)?.Invoke(game,new object[]{new Vector2(1920,1080),"Station Evidence 1080p"});
            game.Show();game.Focus();
            SessionState.SetInt(State,1);
            EditorApplication.EnterPlaymode();
        }

        static T Load<T>(string path) where T:UnityEngine.Object =>
            AssetDatabase.LoadAssetAtPath<T>(path) ?? throw new FileNotFoundException(path);

        static GameObject BuildPrefab(string name)
        {
            string path=Prefabs+name+".prefab";
            var source=Load<GameObject>(Models+name+".fbx");
            var model=(GameObject)PrefabUtility.InstantiatePrefab(source);
            try
            {
                foreach(var renderer in model.GetComponentsInChildren<MeshRenderer>())
                {
                    renderer.sharedMaterials=renderer.sharedMaterials.Select(m=>{
                        if (!m) throw new InvalidDataException("Missing FBX material slot");
                        var surface=m.name;
                        if(surface=="Grout" || surface=="Terrazzo") return Load<Material>(HallSurfaces.Materials+surface+".mat");
                        if(surface.Contains("Plaster")) return Load<Material>(HallSurfaces.Materials+"OldPlaster.mat");
                        if(surface=="Glass") return Load<Material>(HallSurfaces.Materials+"HallGlass.mat");
                        if(surface.Contains("Iron")) return Load<Material>(HallSurfaces.Materials+"CastIron.mat");
                        if(m.name.Contains("Opal")) return Load<Material>(HallSurfaces.Materials+"Opal.mat");
                        if(m.name.Contains("Wood")) return Load<Material>(HallSurfaces.Materials+"AgedWood.mat");
                        var pathName=m.name.Contains("Brass")?"Worn Brass":"Painted Dark Iron";
                        return Load<Material>("Assets/_Project/Art/Materials/Station "+pathName+".mat");
                    }).ToArray();
                }
                var prefab=PrefabUtility.SaveAsPrefabAsset(model,path);
                if (!prefab) throw new IOException(path);
                return prefab;
            }
            finally {UnityEngine.Object.DestroyImmediate(model);}
        }

        static void Place(GameObject prefab, Transform group, int index, Vector3 position, float angle)
        {
            var item=index<group.childCount ? group.GetChild(index).gameObject : (GameObject)PrefabUtility.InstantiatePrefab(prefab,group);
            if (PrefabUtility.GetCorrespondingObjectFromSource(item) != prefab) throw new IOException("Unexpected fitting in hall");
            item.transform.localPosition=position;
            item.transform.localRotation=Quaternion.Euler(0,angle,0)*prefab.transform.localRotation;
            PrefabUtility.RecordPrefabInstancePropertyModifications(item.transform);
        }

        internal static readonly string[] ShotNames={"Station_MainHall","Station_LostFound","Station_Watch","Station_NPC","Station_Platform","Station_Watch","Station_Watch"};
        internal static readonly string[] Files={"06_MainHall_Final","07_LostFound_Final","08_PocketWatch_Final","09_NPC_Final","10_Platform_Final","Watch_Caseback","Watch_Crown"};
        const string All="Echo.M15.AllShots";
        internal static void CaptureAll()
        {
            EditorEvidence.Restore();
            SessionState.SetInt(All,0);
            SessionState.SetInt(State,1);
            EditorApplication.EnterPlaymode();
        }

        static void Tick()
        {
            if(EditorApplication.isUpdating || EditorApplication.isCompiling) return;
            var state=SessionState.GetInt(State,0);
            try
            {
                if(state==0)
                {
                    if(File.Exists(Request) && !EditorApplication.isPlayingOrWillChangePlaymode) {File.Delete(Request);Run();}
                    return;
                }
                if(!EditorApplication.isPlaying) return;
                if(state==1)
                {
                    var camera=Camera.main;
                    var index=SessionState.GetInt(All,-1);
                    var anchor=GameObject.Find(index<0?"Station_MainHall":ShotNames[index]).GetComponent<Camera>();
                    camera.transform.SetPositionAndRotation(anchor.transform.position,anchor.transform.rotation);
                    camera.fieldOfView=anchor.fieldOfView; camera.nearClipPlane=anchor.nearClipPlane;
                    if(index==5 || index==6)
                    {
                        var w=GameObject.Find("Station/Props/PocketWatch").transform;
                        // These poses are used only after the fixed five shots, in Play Mode.
                        if(index==5) {w.position+=Vector3.up*.045f;w.Rotate(Vector3.forward,180,Space.Self);}
                        else w.Rotate(Vector3.forward,180,Space.Self);
                        camera.transform.position=w.position+(index==5?new Vector3(0,.095f,-.005f):new Vector3(.015f,.034f,.092f));
                        camera.transform.LookAt(w.position+(index==5?Vector3.zero:new Vector3(0,0,.024f)), index==5?Vector3.forward:Vector3.up);
                        camera.nearClipPlane=.001f;camera.fieldOfView=36;
                    }
                    game=EditorWindow.GetWindow(typeof(Editor).Assembly.GetType("UnityEditor.GameView"));
                    game.Show(); game.Focus(); Application.runInBackground=true;
                    if(Screen.width!=1920 || Screen.height!=1080)
                        game.GetType().GetMethod("SetCustomResolution",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic)?.Invoke(game,new object[]{new Vector2(1920,1080),"Station Evidence 1080p"});
                    EditorApplication.isPaused=false;
                    start=EditorApplication.timeSinceStartup;
                    frames.Clear();cpu.Clear();gpu.Clear();render.Clear();previousFrame=-1;
                    if(index==3)
                    {
                        visitor=GameObject.Find("Station/Characters/StationVisitor").GetComponentInChildren<Animator>();
                        leftToe=visitor.GetBoneTransform(HumanBodyBones.LeftToes);
                        rightToe=visitor.GetBoneTransform(HumanBodyBones.RightToes);
                        faceSkin=visitor.GetComponentsInChildren<SkinnedMeshRenderer>().Single(r=>r.name=="Skin");
                        blinkShape=Enumerable.Range(0,faceSkin.sharedMesh.blendShapeCount)
                            .First(i=>faceSkin.sharedMesh.GetBlendShapeName(i).IndexOf("blink",StringComparison.OrdinalIgnoreCase)>=0);
                        lowestSole=float.PositiveInfinity;highestSole=float.NegativeInfinity;
                        blinkMin=float.PositiveInfinity;blinkMax=float.NegativeInfinity;
                        animFirst=visitor.GetCurrentAnimatorStateInfo(0).normalizedTime;
                    }
                    SessionState.SetInt(State,2);
                    Log($"camera={anchor.name} Play={Application.isPlaying} quality={QualitySettings.names[QualitySettings.GetQualityLevel()]} GPU={SystemInfo.graphicsDeviceName} screen={Screen.width}x{Screen.height}");
                }
                game?.Repaint(); EditorApplication.QueuePlayerLoopUpdate();
                if(EditorApplication.timeSinceStartup-start>110) throw new TimeoutException("Game View capture timed out");
                if(state==2 && Time.frameCount!=previousFrame && EditorApplication.timeSinceStartup-start>2)
                {
                    if(Screen.width!=1920 || Screen.height!=1080) return;
                    previousFrame=Time.frameCount;frames.Add(Time.unscaledDeltaTime*1000);
                    FrameTimingManager.CaptureFrameTimings();
                    if(FrameTimingManager.GetLatestTimings(1,timing)>0)
                    {
                        var t=timing[0];
                        if(t.cpuMainThreadFrameTime>0) cpu.Add(t.cpuMainThreadFrameTime);
                        if(t.gpuFrameTime>0) gpu.Add(t.gpuFrameTime);
                        if(t.cpuRenderThreadFrameTime>0) render.Add(t.cpuRenderThreadFrameTime);
                    }
                    if(SessionState.GetInt(All,-1)==3)
                    {
                        float sole=Mathf.Min(leftToe.position.y,rightToe.position.y)-.02348f;
                        lowestSole=Mathf.Min(lowestSole,sole); highestSole=Mathf.Max(highestSole,sole);
                        if(faceSkin.sharedMesh.blendShapeCount>blinkShape)
                        {
                            float blink=faceSkin.GetBlendShapeWeight(blinkShape);
                            blinkMin=Mathf.Min(blinkMin,blink); blinkMax=Mathf.Max(blinkMax,blink);
                        }
                        animLast=visitor.GetCurrentAnimatorStateInfo(0).normalizedTime;
                        if(animLast-animFirst<1.65f) return;
                        File.WriteAllText(Evidence+"IdleValidation.log",$"Sampled frames={frames.Count} humanoid={visitor.isHuman} sole estimate min={lowestSole:F4}m max={highestSole:F4}m blink range={blinkMin:F1}..{blinkMax:F1}; foot datum uses toes minus 0.02348m.\n");
                    }
                    if(frames.Count<150) return;
                    if(Screen.width!=1920 || Screen.height!=1080) throw new InvalidOperationException("Resolution mismatch");
                    int index=SessionState.GetInt(All,-1);
                    shot=Path.GetFullPath(Evidence+(index<0?"Hall_"+DateTime.Now.ToString("HHmmssfff"):Files[index])+".png");
                    if(index>=0 && File.Exists(shot)) File.Move(shot, Path.Combine("Temp",Guid.NewGuid()+".png"));
                    ScreenCapture.CaptureScreenshot(shot);
                    frames.Sort();
                    Log($"n={frames.Count} FPS={1000/frames.Average():F1} P95ms={frames[(int)Math.Ceiling(frames.Count*.95)-1]:F1} peakMs={frames.Last():F1} over100={frames.Count(t=>t>100)} cpuMainMs={Mean(cpu)} gpuMs={Mean(gpu)} renderThreadMs={Mean(render)} allocatedMB={Profiler.GetTotalAllocatedMemoryLong()/1048576} batches={UnityStats.batches} draws={UnityStats.drawCalls}");
                    SessionState.SetInt(State,3);
                }
                if(state==4 && Time.frameCount-previousFrame>=24)
                {
                    Profiler.enabled=false;Profiler.enableBinaryLog=false;Profiler.logFile="";
                    Log("Saved separate 24-frame MainHall CPU profiler trace");
                    SessionState.SetInt(State,0);SessionState.SetInt("Echo.M15.Windows",1);
                    EditorApplication.ExitPlaymode();return;
                }
                if(state==3 && File.Exists(shot) && new FileInfo(shot).Length>100)
                {
                    var png=File.ReadAllBytes(shot);
                    if(png[png.Length-8]!=73 || png[png.Length-7]!=69) return;
                    Log("Game View saved "+Path.GetFileName(shot));
                    int index=SessionState.GetInt(All,-1);
                    if(index==0) EditorEvidence.Frame("11_Unity_GameView_PlayMode");
                    if(index>=0 && index<ShotNames.Length-1)
                    {
                        SessionState.SetInt(All,index+1);
                        SessionState.SetInt(State,1);
                        return;
                    }
                    SessionState.EraseInt(All);
                    if(index>=0 && !Profiler.enabled)
                    {
                        var main=GameObject.Find("Station_MainHall").GetComponent<Camera>();
                        Camera.main.transform.SetPositionAndRotation(main.transform.position,main.transform.rotation);
                        Camera.main.fieldOfView=main.fieldOfView; Camera.main.nearClipPlane=main.nearClipPlane;
                        Profiler.logFile=Path.GetFullPath(Evidence+"HallProfiler.raw");
                        Profiler.enableBinaryLog=true; Profiler.enabled=true;
                        previousFrame=Time.frameCount;
                        SessionState.SetInt(State,4); return;
                    }
                    SessionState.SetInt(State,0);EditorApplication.ExitPlaymode();
                    if(index>=0) SessionState.SetInt("Echo.M15.Windows",1);
                }
            }
            catch(Exception ex)
            {
                SessionState.EraseInt(All);SessionState.SetInt(State,0);Log("FAILED "+ex);
                if(state!=0 && EditorApplication.isPlaying) EditorApplication.ExitPlaymode();
            }
        }
    }
}
