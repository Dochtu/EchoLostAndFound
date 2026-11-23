using System;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;
using UnityEngine.SceneManagement;

[InitializeOnLoad]
public static class Stage4Baseline
{
    const string ScenePath = "Assets/_Project/Scenes/Stage4Baseline.unity";
    const string Calibration = "Assets/_Project/Scenes/Stage4Calibration";
    const string Evidence = "Docs/Evidence/Stage4_M0_M1/";
    const string Screenshot = Evidence + "00_GameView_HDRP_Baseline.png";
    const string Marker = "Temp/Stage4Baseline.request";
    const string State = "Echo.Stage4.Baseline";
    static double captureStarted;
    static int frames;
    static bool capturing;
    static DateTime requested;

    static Stage4Baseline()
    {
        EditorApplication.update += Tick;
    }

    static void Log(string line)
    {
        Directory.CreateDirectory(Evidence);
        File.AppendAllText(Evidence + "BaselineRuntime.log", DateTime.Now.ToString("s") + " " + line + Environment.NewLine);
    }

    static void Tick()
    {
        try
        {
            if (EditorApplication.isCompiling || EditorApplication.isUpdating) return;
            if (!EditorApplication.isPlayingOrWillChangePlaymode && File.Exists(Marker))
            {
                File.Delete(Marker);
                Run();
            }
            if (!EditorApplication.isPlaying || !SessionState.GetBool(State, false)) return;
            if (SceneManager.GetActiveScene().path != ScenePath) throw new Exception("Unexpected Play scene");
            if (++frames < 24 || Time.realtimeSinceStartup < 4) return;
            if (!capturing)
            {
                capturing = true;
                captureStarted = EditorApplication.timeSinceStartup;
                requested = DateTime.UtcNow.AddSeconds(-1);
                ScreenCapture.CaptureScreenshot(Path.GetFullPath(Screenshot));
                Log($"Play={Application.isPlaying} Camera={Camera.main.name} GameView={Screen.width}x{Screen.height} Frames={Time.frameCount} Quality={QualitySettings.names[QualitySettings.GetQualityLevel()]} CPU={SystemInfo.processorType} GPU={SystemInfo.graphicsDeviceName} Graphics={SystemInfo.graphicsDeviceType} Pipeline={GraphicsSettings.currentRenderPipeline.name}");
                return;
            }
            if (File.Exists(Screenshot) && File.GetLastWriteTimeUtc(Screenshot) >= requested && new FileInfo(Screenshot).Length > 1000)
            {
                Log("Game View capture saved. " + Counts());
                Finish();
            }
            else if (EditorApplication.timeSinceStartup - captureStarted > 45) throw new TimeoutException("Game View screenshot timed out");
        }
        catch(Exception e) { Log(e.ToString()); Finish(); }
    }

    static void Finish()
    {
        bool owned = SessionState.GetBool(State, false);
        SessionState.SetBool(State, false);
        if (owned && EditorApplication.isPlaying) EditorApplication.ExitPlaymode();
        capturing = false;
        frames = 0;
    }

    static string Counts()
    {
        var counts = typeof(Editor).Assembly.GetType("UnityEditor.LogEntries")?.GetMethod("GetCountsByType",BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic);
        if (counts == null) return "Console counts unavailable";
        object[] values = { 0, 0, 0 };
        counts.Invoke(null, values);
        return $"Console errors={values[0]} warnings={values[1]} messages={values[2]}";
    }

    static int Missing(Scene scene)
    {
        return scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<Transform>(true))
            .Sum(t => GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject));
    }

    [MenuItem("Tools/Echo/Run HDRP Baseline")]
    public static void Run()
    {
        if (Application.isBatchMode || EditorApplication.isPlayingOrWillChangePlaymode) throw new InvalidOperationException("Use an idle interactive Editor.");
        for (int i=0;i<SceneManager.sceneCount;i++)
            if (SceneManager.GetSceneAt(i).isDirty) throw new InvalidOperationException("Unsaved scene: " + SceneManager.GetSceneAt(i).name);
        var current = SceneManager.GetActiveScene();
        Log($"Editor={Application.unityVersion} initialScene={current.path} roots={current.rootCount} missing={Missing(current)} SceneViewPivot={SceneView.lastActiveSceneView?.pivot} {Counts()}");
        if (!File.Exists(ScenePath)) Create();
        var scene = EditorSceneManager.OpenScene(ScenePath);
        Log($"Reopened={scene.path} roots={scene.rootCount} missing={Missing(scene)} colorSpace={QualitySettings.activeColorSpace}");
        if (Missing(scene) != 0) throw new InvalidOperationException("Missing script");
        var gameView = EditorWindow.GetWindow(typeof(Editor).Assembly.GetType("UnityEditor.GameView"));
        gameView.Show(); gameView.Focus();
        SessionState.SetBool(State,true);
        EditorApplication.EnterPlaymode();
    }

    static void Create()
    {
        if (!AssetDatabase.IsValidFolder(Calibration)) AssetDatabase.CreateFolder("Assets/_Project/Scenes","Stage4Calibration");
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        var cam = new GameObject("Calibration Camera",typeof(Camera),typeof(HDAdditionalCameraData));
        cam.tag="MainCamera"; cam.transform.position=new Vector3(0,2.3f,-7);
        cam.transform.LookAt(new Vector3(0,0.95f,0));
        cam.GetComponent<Camera>().fieldOfView=39;
        var profile=AssetDatabase.LoadAssetAtPath<VolumeProfile>(Calibration+"/BaselineProfile.asset");
        if (!profile)
        {
            profile=ScriptableObject.CreateInstance<VolumeProfile>();
            AssetDatabase.CreateAsset(profile,Calibration+"/BaselineProfile.asset");
            var exposure=profile.Add<Exposure>(); exposure.mode.Override(ExposureMode.Fixed); exposure.fixedExposure.Override(7);
            var tone=profile.Add<Tonemapping>(); tone.mode.Override(TonemappingMode.ACES);
            var fog=profile.Add<Fog>(); fog.enabled.Override(true); fog.meanFreePath.Override(65);
            foreach(var effect in profile.components) AssetDatabase.AddObjectToAsset(effect,profile);
            EditorUtility.SetDirty(profile);
        }
        var volume=new GameObject("Calibration Volume").AddComponent<Volume>();
        volume.isGlobal=true; volume.priority=20; volume.sharedProfile=profile;
        var mat=AssetDatabase.LoadAssetAtPath<Material>(Calibration+"/BaselineSurface.mat");
        if(!mat)
        {
            mat=new Material(Shader.Find("HDRP/Lit")); mat.SetColor("_BaseColor",new Color(.52f,.48f,.41f)); mat.SetFloat("_Smoothness",.58f); mat.SetFloat("_Metallic",.32f);
            AssetDatabase.CreateAsset(mat,Calibration+"/BaselineSurface.mat");
        }
        Surface("Shadow receiver",PrimitiveType.Cube,new Vector3(0,-.1f,1),new Vector3(14,.2f,13),mat);
        Surface("Curvature",PrimitiveType.Sphere,new Vector3(-1.6f,.84f,0),Vector3.one*1.68f,mat);
        Surface("Flat faces",PrimitiveType.Cube,new Vector3(.17f,.66f,.3f),Vector3.one*1.32f,mat).transform.rotation=Quaternion.Euler(0,28,0);
        Surface("Vertical highlight",PrimitiveType.Capsule,new Vector3(1.8f,1.05f,.8f),Vector3.one*1.05f,mat);
        Lamp("Cool key",LightType.Directional,new Vector3(0,5,0),new Color(.67f,.82f,1),700).transform.rotation=Quaternion.Euler(40,34,0);
        Lamp("Warm point",LightType.Point,new Vector3(-2,2,-1.3f),new Color(1,.53f,.26f),350);
        Lamp("Spot fill",LightType.Spot,new Vector3(2,3,-2),Color.white,850).transform.LookAt(Vector3.right);
        var probe=new GameObject("Calibration reflections",typeof(ReflectionProbe),typeof(HDAdditionalReflectionData));
        probe.transform.position=Vector3.up;
        probe.GetComponent<ReflectionProbe>().mode=ReflectionProbeMode.Realtime;
        SceneView.lastActiveSceneView?.LookAt(new Vector3(0,1,0),cam.transform.rotation,6);
        AssetDatabase.SaveAssets();
        if(!EditorSceneManager.SaveScene(scene,ScenePath)) throw new IOException("Could not save calibration scene");
    }

    static GameObject Surface(string name,PrimitiveType shape,Vector3 at,Vector3 size,Material mat)
    {
        var obj=GameObject.CreatePrimitive(shape); obj.name=name; obj.transform.position=at;
        obj.transform.localScale=size; obj.GetComponent<Renderer>().sharedMaterial=mat; return obj;
    }

    static Light Lamp(string name,LightType kind,Vector3 at,Color color,float intensity)
    {
        var light=new GameObject(name,typeof(Light),typeof(HDAdditionalLightData)).GetComponent<Light>();
        light.type=kind; light.transform.position=at; light.color=color; light.intensity=intensity;
        light.range=14; light.shadows=LightShadows.Soft; return light;
    }
}
