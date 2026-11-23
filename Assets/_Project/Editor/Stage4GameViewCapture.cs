using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.Rendering;
using Object = UnityEngine.Object;

[InitializeOnLoad]
public static class Stage4GameViewCapture
{
    const string ScenePath = "Assets/_Project/Scenes/Station.unity";
    const string Output = "Docs/Evidence/Stage4_M0_M1/";
    const string Marker = "Temp/Stage4QA.request";
    const string State = "Echo.Stage4.Capture.State";
    const string RuntimeLog = Output + "StationRuntime.log";
    static readonly string[] Shots = {
        "01_GameView_StationOverview", "02_GameView_LostAndFound", "03_GameView_PocketWatch",
        "04_GameView_NPC", "05_GameView_PlatformRainNight"
    };
    static readonly List<float> FrameTimes = new List<float>();
    static readonly List<double> CpuTimes = new List<double>();
    static readonly List<double> GpuTimes = new List<double>();
    static readonly FrameTiming[] Timing = new FrameTiming[1];
    static double started;
    static int shotIndex, lastFrame;
    static DateTime requestTime;
    static bool waitingForPng;
    static double lastProgress;
    static EditorWindow gameView;
    enum Step { Idle, StartPlay, Capture, LeavePlay, SceneWindow, ConsoleWindow }
    static Step Phase {
        get => (Step)SessionState.GetInt(State, 0);
        set { SessionState.SetInt(State,(int)value); started = EditorApplication.timeSinceStartup; }
    }
    static double Elapsed => EditorApplication.timeSinceStartup - started;
    static void Log(string text) => File.AppendAllText(RuntimeLog,DateTime.Now.ToString("s") + " " + text + Environment.NewLine);
    static Stage4GameViewCapture() { EditorApplication.update += Tick; }

    [MenuItem("Tools/Echo/Validate Station and Capture Game View")]
    public static void Run()
    {
        if (Application.isBatchMode || EditorApplication.isPlayingOrWillChangePlaymode || Phase != Step.Idle)
            throw new InvalidOperationException("Capture requires an idle interactive editor.");
        for(int i = 0; i < SceneManager.sceneCount; i++)
            if(SceneManager.GetSceneAt(i).isDirty) throw new InvalidOperationException("Unsaved scene: " + SceneManager.GetSceneAt(i).name);
        Directory.CreateDirectory(Output);
        EditorSceneManager.OpenScene(ScenePath);
        Stage4SceneValidationTests.Run();
        Log("Starting independent capture");
        Log("Reopened " + ScenePath + " " + Counts());
        var game = EditorWindow.GetWindow(typeof(Editor).Assembly.GetType("UnityEditor.GameView"));
        game.GetType().GetMethod("SetCustomResolution",Bind)?.Invoke(game,new object[]{new Vector2(1920,1080),"Station Evidence 1080p"});
        game.Show(); game.Focus(); game.Repaint();
        Phase = Step.StartPlay;
        EditorApplication.EnterPlaymode();
    }

    static void Tick()
    {
        if(EditorApplication.isCompiling || EditorApplication.isUpdating) return;
        try
        {
            if (Phase == Step.Idle)
            {
                if(File.Exists(Marker) && !EditorApplication.isPlayingOrWillChangePlaymode) { File.Delete(Marker); Run(); }
                const string hierarchyMarker = "Temp/Stage4Hierarchy.request";
                if(File.Exists(hierarchyMarker) && !EditorApplication.isPlayingOrWillChangePlaymode)
                {
                    File.Delete(hierarchyMarker);
                    if(SceneManager.GetActiveScene().path==ScenePath) Phase=Step.LeavePlay;
                }
                return;
            }
            if (Phase == Step.StartPlay && EditorApplication.isPlaying)
            {
                shotIndex = 0;
                EditorApplication.isPaused = false;
                Application.runInBackground = true;
                gameView=EditorWindow.GetWindow(typeof(Editor).Assembly.GetType("UnityEditor.GameView"));
                gameView.Focus(); gameView.Repaint();
                Log($"Play={Application.isPlaying} Camera={Camera.main.name} Resolution={Screen.width}x{Screen.height} CPU={SystemInfo.processorType} GPU={SystemInfo.graphicsDeviceName} Graphics={SystemInfo.graphicsDeviceType} Quality={QualitySettings.names[QualitySettings.GetQualityLevel()]} Pipeline={GraphicsSettings.currentRenderPipeline.name}");
                Aim(); return;
            }
            if(Phase == Step.Capture) { CaptureShot(); return; }
            if(Phase == Step.LeavePlay && !EditorApplication.isPlayingOrWillChangePlaymode)
            {
                var cam = Camera.main;
                var scene = SceneView.lastActiveSceneView ?? EditorWindow.GetWindow<SceneView>();
                scene.Focus();
                if(cam) scene.LookAtDirect(cam.transform.position + cam.transform.forward * 10f,cam.transform.rotation,10f);
                var hierarchyType = typeof(Editor).Assembly.GetType("UnityEditor.SceneHierarchyWindow");
                var hierarchy = EditorWindow.GetWindow(hierarchyType);
                var expand = hierarchyType.GetMethod("SetExpanded",Bind,null,new[]{typeof(int),typeof(bool)},null)
                    ?? throw new MissingMethodException(hierarchyType.FullName,"SetExpanded");
                foreach(var root in SceneManager.GetActiveScene().GetRootGameObjects())
                {
                    expand.Invoke(hierarchy,new object[]{root.GetInstanceID(),true});
                    foreach(Transform top in root.transform)
                    {
                        expand.Invoke(hierarchy,new object[]{top.GetInstanceID(),true});
                        foreach(Transform child in top)
                            expand.Invoke(hierarchy,new object[]{child.GetInstanceID(),false});
                    }
                }
                var hall = GameObject.Find("Station/Environment/WaitingHall");
                if(hall) {Selection.activeGameObject = hall; EditorGUIUtility.PingObject(hall);}
                hierarchy.Repaint(); scene.Focus(); scene.Repaint(); Phase=Step.SceneWindow; return;
            }
            if(Phase == Step.SceneWindow && Elapsed>2)
            {
                EditorFrame("07_Editor_SceneHierarchy");
                var console=EditorWindow.GetWindow(typeof(Editor).Assembly.GetType("UnityEditor.ConsoleWindow"));
                console.Show(); console.Focus(); console.Repaint(); Phase=Step.ConsoleWindow; return;
            }
            if(Phase == Step.ConsoleWindow && Elapsed>2)
            {
                EditorFrame("08_Editor_Console");
                Log("Capture completed " + Counts()); Phase=Step.Idle;
            }
        }
        catch(Exception ex)
        {
            Directory.CreateDirectory(Output); Log("FAILED " + ex);
            bool owned = Phase != Step.Idle;
            Phase=Step.Idle;
            if(owned && EditorApplication.isPlaying) EditorApplication.ExitPlaymode();
        }
    }
    const BindingFlags Bind = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;
    static string Counts()
    {
        var method=typeof(Editor).Assembly.GetType("UnityEditor.LogEntries")?.GetMethod("GetCountsByType",Bind);
        if(method==null) return "Console counts unavailable";
        object[] values={0,0,0}; method.Invoke(null,values);
        return $"Console errors={values[0]} warnings={values[1]} messages={values[2]}";
    }
    static void Aim()
    {
        string name=Stage4SceneValidationTests.Anchors[shotIndex];
        Camera anchor=GameObject.Find(name).GetComponent<Camera>(), cam=Camera.main;
        cam.transform.SetPositionAndRotation(anchor.transform.position,anchor.transform.rotation);
        cam.fieldOfView=anchor.fieldOfView; cam.nearClipPlane=anchor.nearClipPlane;
        lastFrame = Time.frameCount; FrameTimes.Clear(); CpuTimes.Clear(); GpuTimes.Clear();
        waitingForPng=false; Phase=Step.Capture;
    }
    static void CaptureShot()
    {
        if(!Application.isPlaying || SceneManager.GetActiveScene().path!=ScenePath) throw new InvalidOperationException("Play session interrupted");
        string path=Path.GetFullPath(Output + Shots[shotIndex] + ".png");
        gameView?.Repaint(); EditorApplication.QueuePlayerLoopUpdate();
        if(EditorApplication.timeSinceStartup-lastProgress>8)
        {
            lastProgress=EditorApplication.timeSinceStartup;
            Log($"Progress shot={shotIndex} t={Elapsed:F1} frame={Time.frameCount} paused={EditorApplication.isPaused} samples={FrameTimes.Count} waitingForPNG={waitingForPng} focused={EditorWindow.focusedWindow?.GetType().Name}");
        }
        if(Elapsed>120) throw new TimeoutException("No rendered frame or capture " + path);
        if(!waitingForPng)
        {
            if(lastFrame!=Time.frameCount)
            {
                lastFrame=Time.frameCount;
                bool timingAvailable = FrameTimingManager.IsFeatureEnabled();
                if(timingAvailable) FrameTimingManager.CaptureFrameTimings();
                if(Elapsed >= 1.5)
                {
                    FrameTimes.Add(Time.unscaledDeltaTime);
                    if(timingAvailable && FrameTimingManager.GetLatestTimings(1,Timing)>0)
                    {
                        if(Timing[0].cpuMainThreadFrameTime>0) CpuTimes.Add(Timing[0].cpuMainThreadFrameTime);
                        if(Timing[0].gpuFrameTime>0) GpuTimes.Add(Timing[0].gpuFrameTime);
                    }
                }
            }
            if(FrameTimes.Count < 24 || Elapsed<3) return;
            requestTime=DateTime.UtcNow.AddMilliseconds(-250);
            ScreenCapture.CaptureScreenshot(path); waitingForPng=true; return;
        }
        if(!File.Exists(path) || File.GetLastWriteTimeUtc(path)<requestTime || new FileInfo(path).Length < 100) return;
        byte[] bytes=File.ReadAllBytes(path);
        if(bytes.Length<12 || bytes[bytes.Length-8]!=73 || bytes[bytes.Length-7]!=69) return;
        string TimingMean(List<double> samples) => samples.Count==0?"unavailable":samples.Average().ToString("F1");
        Log($"{Shots[shotIndex]} real Game View {Screen.width}x{Screen.height} samples={FrameTimes.Count} FPS={1/FrameTimes.Average():F1} peakFrameMs={1000*FrameTimes.Max():F1} framesOver100ms={FrameTimes.Count(x=>x>.1f)} cpuMainThreadMs={TimingMean(CpuTimes)} gpuFrameMs={TimingMean(GpuTimes)} bytes={bytes.Length}");
        if(shotIndex==0) EditorFrame("06_Editor_GameView_PlayMode");
        if(++shotIndex<Shots.Length) { Aim(); return; }
        Phase=Step.LeavePlay;
        Log("Leaving Play Mode " + Counts()); EditorApplication.ExitPlaymode();
    }

    // Print only Unity's top-level window, including its actual tab strip, toolbar and docked panes.
    [StructLayout(LayoutKind.Sequential)] struct RectI { public int left,top,right,bottom; }
    [StructLayout(LayoutKind.Sequential)] struct BitmapInfo {
        public uint header; public int width,height; public ushort planes,bits;
        public uint compression,size; public int xppm,yppm; public uint colors,important;
    }
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr hwnd,out RectI rect);
    [DllImport("user32.dll")] static extern IntPtr GetDC(IntPtr hwnd);
    [DllImport("user32.dll")] static extern int ReleaseDC(IntPtr hwnd,IntPtr dc);
    [DllImport("user32.dll")] static extern bool PrintWindow(IntPtr hwnd,IntPtr dc,uint flags);
    [DllImport("gdi32.dll")] static extern IntPtr CreateCompatibleDC(IntPtr dc);
    [DllImport("gdi32.dll")] static extern IntPtr CreateCompatibleBitmap(IntPtr dc,int w,int h);
    [DllImport("gdi32.dll")] static extern IntPtr SelectObject(IntPtr dc,IntPtr obj);
    [DllImport("gdi32.dll")] static extern bool DeleteObject(IntPtr obj);
    [DllImport("gdi32.dll")] static extern bool DeleteDC(IntPtr dc);
    [DllImport("gdi32.dll")] static extern int GetDIBits(IntPtr dc,IntPtr bmp,uint start,uint lines,byte[] buffer,ref BitmapInfo info,uint usage);
    static void EditorFrame(string name)
    {
        using var process = Process.GetCurrentProcess();
        IntPtr hwnd=process.MainWindowHandle;
        if(hwnd==IntPtr.Zero || !GetWindowRect(hwnd,out RectI r)) throw new InvalidOperationException("Cannot locate Editor window");
        int w=r.right-r.left,h=r.bottom-r.top;
        if(w<256 || h<256 || w>16384 || h>16384) throw new InvalidOperationException("Invalid window dimensions");
        var src=GetDC(hwnd); var dc=CreateCompatibleDC(src); var bmp=CreateCompatibleBitmap(src,w,h);
        var prev=SelectObject(dc,bmp);
        Texture2D texture=null;
        try
        {
            if(!PrintWindow(hwnd,dc,2)) throw new IOException("PrintWindow failed");
            SelectObject(dc,prev);
            var info=new BitmapInfo{header=40,width=w,height=h,planes=1,bits=32};
            byte[] pixels=new byte[4*w*h];
            if(GetDIBits(dc,bmp,0,(uint)h,pixels,ref info,0)!=h) throw new IOException("Incomplete window pixel readback");
            for(int i=3;i<pixels.Length;i+=4) pixels[i]=255;
            texture=new Texture2D(w,h,TextureFormat.BGRA32,false);
            texture.LoadRawTextureData(pixels); texture.Apply();
            File.WriteAllBytes(Output+name+".png",texture.EncodeToPNG());
            Log($"{name} Unity window {w}x{h} Play={Application.isPlaying}");
        }
        finally
        {
            SelectObject(dc,prev); DeleteObject(bmp); DeleteDC(dc); ReleaseDC(hwnd,src);
            if(texture) Object.DestroyImmediate(texture);
        }
    }
}
