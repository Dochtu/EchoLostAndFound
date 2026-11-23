using System;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.Rendering.HighDefinition;

namespace Echo.M15
{
    [InitializeOnLoad]
    internal static class R1Station
    {
        const string Output="Docs/Evidence/M1_5_R1/";
        const string ScenePath="Assets/_Project/Scenes/Station.unity";
        const string Request="Library/R1Baseline/action";
        static R1Station()
        {
            EditorApplication.update+=Tick;
            EditorApplication.playModeStateChanged+=state=>{
                if(state==PlayModeStateChange.EnteredPlayMode && SessionState.GetBool("Echo.R1.capture",false))StartCapture();
            };
        }
        static double windowDeadline;
        static EditorWindow captureView;
        static void StartCapture()
        {
            SessionState.EraseBool("Echo.R1.capture");
            EditorApplication.isPaused=false;
            if(SessionState.GetBool("Echo.R1.window",false))
            {
                var c=Camera.main;var a=GameObject.Find("Station_MainHall").GetComponent<Camera>();
                c.transform.SetPositionAndRotation(a.transform.position,a.transform.rotation);c.fieldOfView=a.fieldOfView;
                captureView=EditorWindow.GetWindow(typeof(Editor).Assembly.GetType("UnityEditor.GameView"));
                captureView.Show();captureView.Focus();windowDeadline=EditorApplication.timeSinceStartup+4;
                return;
            }
            var r=new GameObject("R1 Game View capture").AddComponent<R1CaptureRunner>();
            r.WindowOnly=SessionState.GetBool("Echo.R1.window",false);
            r.CaptureWindow=()=>EditorApplication.delayCall+=()=>EditorEvidence.Frame("PlayMode",Output);
            r.Finish=()=>EditorApplication.ExitPlaymode();
            Log("Capture runner started windowOnly="+r.WindowOnly);
        }
        static void Log(string s)=>File.AppendAllText(Output+"Integration.log",DateTime.Now.ToString("s")+" "+s+"\n");
        static void Tick()
        {
            if(EditorApplication.isUpdating||EditorApplication.isCompiling)return;
            try
            {
                if(EditorApplication.isPlaying && windowDeadline>0)
                {
                    captureView.Repaint();EditorApplication.QueuePlayerLoopUpdate();
                    if(EditorApplication.timeSinceStartup<windowDeadline)return;
                    windowDeadline=0;
                    EditorEvidence.Frame("PlayMode",Output);
                    Log("Play window captured in editor update");
                    EditorApplication.ExitPlaymode();return;
                }
                if(EditorApplication.isPlaying && File.Exists("Library/R1Baseline/stop-capture"))
                {
                    File.Delete("Library/R1Baseline/stop-capture");
                    EditorApplication.ExitPlaymode();return;
                }
                if(!File.Exists(Request)||EditorApplication.isPlayingOrWillChangePlaymode)return;
                var action=File.ReadAllText(Request).Trim();File.Delete(Request);
                if(action=="profile"){
                    R1ProfilerAnalysis.Summarize("Docs/Evidence/Stage4_M1_5/HallProfiler.raw",Output+"BaselineMarkers.csv");
                    foreach(var f in Directory.GetFiles(Output,"*.raw",SearchOption.AllDirectories))
                        R1ProfilerAnalysis.Summarize(f,Path.ChangeExtension(f,".markers.csv"));
                    Log("Profiler analysis complete");return;
                }
                if(SceneManager.GetActiveScene().isDirty)throw new IOException("Unsaved active scene");
                var scene=EditorSceneManager.OpenScene(ScenePath);
                if(action=="apply")
                {
                    R1Environment.Apply();StationCharacter.Apply();Tune();
                    EditorSceneManager.MarkSceneDirty(scene);
                    if(!EditorSceneManager.SaveScene(scene))throw new IOException(ScenePath);
                    EditorSceneManager.OpenScene(ScenePath);
                    StationAudit.Run(Output+"Reload.log");Log("Scene saved and reloaded");action="capture";
                }
                if(action=="capture" || action=="window")
                {
                    SessionState.SetBool("Echo.R1.window",action=="window");
                    EditorEvidence.Restore();
                    var game=EditorWindow.GetWindow(typeof(Editor).Assembly.GetType("UnityEditor.GameView"));
                    game.GetType().GetMethod("SetCustomResolution",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic)?.Invoke(game,new object[]{new Vector2(1920,1080),"Station Evidence 1080p"});
                    game.Show();game.Focus();
                    SessionState.SetBool("Echo.R1.capture",true);EditorApplication.EnterPlaymode();
                }
                else if(action=="build"){
                    bool old=PlayerSettings.enableFrameTimingStats;
                    try{
                        PlayerSettings.enableFrameTimingStats=true;
                        var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{ScenePath},target=BuildTarget.StandaloneWindows64,locationPathName="Builds/M15R1/Station.exe",options=BuildOptions.Development});
                        Log("Player "+report.summary.result+" errors="+report.summary.totalErrors+" warnings="+report.summary.totalWarnings);
                    }finally{PlayerSettings.enableFrameTimingStats=old;}
                }
            }catch(Exception ex){Log(ex.ToString());}
        }

        static void Tune()
        {
            int fixedRenderers=0;
            foreach(var group in new[]{"Station/Environment","Station/Lighting"})
            foreach(var r in GameObject.Find(group).GetComponentsInChildren<MeshRenderer>(true)){
                if(!r.enabled)continue;
                r.staticShadowCaster=true;
                GameObjectUtility.SetStaticEditorFlags(r.gameObject,GameObjectUtility.GetStaticEditorFlags(r.gameObject)|StaticEditorFlags.BatchingStatic);
                PrefabUtility.RecordPrefabInstancePropertyModifications(r);
                PrefabUtility.RecordPrefabInstancePropertyModifications(r.gameObject);
                fixedRenderers++;
            }
            foreach(var l in GameObject.Find("Station/Lighting").GetComponentsInChildren<Light>()){
                if(l.name!="Warm pool"||l.shadows==LightShadows.None)continue;
                var data=l.GetComponent<HDAdditionalLightData>();
                data.SetShadowResolutionOverride(true);
                data.SetShadowResolution(l.transform.parent.name=="Hall pendant"?512:384);
                data.shadowUpdateMode=ShadowUpdateMode.OnEnable;data.alwaysDrawDynamicShadows=true;
                PrefabUtility.RecordPrefabInstancePropertyModifications(data);
            }
            var visitor=GameObject.Find("Station/Characters/StationVisitor").transform;
            var key=GameObject.Find("NPC face bounce").GetComponent<Light>();
            var toCamera=(GameObject.Find("Station_NPC").transform.position-visitor.position);toCamera.y=0;toCamera.Normalize();
            var across=Vector3.Cross(Vector3.up,toCamera);
            key.transform.position=visitor.position+toCamera*1.15f+across*.80f+Vector3.up*2.45f;
            key.type=LightType.Spot;key.spotAngle=84;key.innerSpotAngle=52;
            key.transform.LookAt(visitor.position+Vector3.up*.96f);key.intensity=290;key.shadows=LightShadows.Soft;
            var hd=key.GetComponent<HDAdditionalLightData>();hd.shapeRadius=.19f;hd.SetShadowResolutionOverride(true);hd.SetShadowResolution(512);
            var skin=AssetDatabase.LoadAssetAtPath<Material>("Assets/_Project/Art/Characters/M1_5/Skin.mat");
            skin.SetFloat("_SmoothnessRemapMin",.10f);skin.SetFloat("_SmoothnessRemapMax",.86f);skin.SetFloat("_NormalScale",.85f);
            HDMaterial.ValidateMaterial(skin);EditorUtility.SetDirty(skin);AssetDatabase.SaveAssetIfDirty(skin);
            Log("static renderers="+fixedRenderers+" reflection probes="+UnityEngine.Object.FindObjectsByType<ReflectionProbe>(FindObjectsSortMode.None).Length);
        }
    }
}
