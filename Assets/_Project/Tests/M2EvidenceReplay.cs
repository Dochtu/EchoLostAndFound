#if UNITY_EDITOR || DEVELOPMENT_BUILD
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using EchoLostAndFound.M2;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;

// Drives only keyboard and mouse devices. Movement, aiming, hits and UI all go
// through the same input actions and CharacterController used in normal play.
public sealed class M2EvidenceReplay : MonoBehaviour
{
    public string Job;
    Keyboard keyboard;
    Mouse mouse;
    M2Player player;
    Camera view;
    string output, frames;
    int frame;
    bool recording;
    readonly List<string> samples = new List<string>();
    readonly List<float> times = new List<float>();
    readonly WaitForEndOfFrame rendered = new WaitForEndOfFrame();
    static readonly CultureInfo CI = CultureInfo.InvariantCulture;
    bool Benchmark => Job == "Benchmark";

#if !UNITY_EDITOR
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void StartIfRequested()
    {
        if (Array.IndexOf(Environment.GetCommandLineArgs(), "-m2-benchmark") >= 0)
            new GameObject("M2 traversal benchmark").AddComponent<M2EvidenceReplay>().Job = "Benchmark";
    }
#endif

    IEnumerator Start()
    {
        output = Path.GetFullPath(Path.Combine(Application.dataPath, Application.isEditor ? "../Docs/Evidence/Stage4_M2" : "../../../Docs/Evidence/Stage4_M2"));
        Directory.CreateDirectory(output);
        var stack = new Stack<IEnumerator>();
        stack.Push(Run());
        while (stack.Count > 0)
        {
            object current = null;
            try
            {
                if (!stack.Peek().MoveNext()) { stack.Pop(); continue; }
                current = stack.Peek().Current;
            }
            catch (Exception e) { Finish(e.ToString()); yield break; }
            if (current is IEnumerator nested) stack.Push(nested);
            else yield return current;
        }
        Finish("PASS");
    }

    IEnumerator Run()
    {
        Application.runInBackground = true;
        player = FindFirstObjectByType<M2Player>();
        view = player.View;
        keyboard = InputSystem.AddDevice<Keyboard>();
        mouse = InputSystem.AddDevice<Mouse>();
        frames = Path.GetFullPath("Library/M2/" + Job + "Frames");
        if (!Benchmark) { Directory.CreateDirectory(frames); Time.captureFramerate = 24; }
        File.WriteAllText(Path.Combine(output, Job + ".log"),
            $"{DateTime.Now:s} {Application.unityVersion} editor={Application.isEditor} {Screen.width}x{Screen.height} {SystemInfo.graphicsDeviceName} {SystemInfo.processorType} ramMB={SystemInfo.systemMemorySize} api={SystemInfo.graphicsDeviceType} quality={QualitySettings.names[QualitySettings.GetQualityLevel()]} vsync={QualitySettings.vSyncCount}\n");
        yield return new WaitForSecondsRealtime(Benchmark ? 6 : 1);
        var start = player.transform.position;
        recording = true;
        var route = new[] { new Vector2(-8.3f,-3.2f), new Vector2(0,-3.2f), new Vector2(0,2.8f),
            new Vector2(4.5f,2.8f), new Vector2(4.5f,.95f), new Vector2(10,.95f) };
        if (Job == "Interaction")
        {
            yield return OpenAt(new Vector3(-9.83f,1.06f,-4.45f), "Watch", "怀表");
            yield return OpenAt(new Vector3(-9.86f,1.18f,-3.69f), "Register", "登记");
            yield return OpenAt(new Vector3(-9.38f,.76f,-5.5f), "Counter", "柜台");
            yield return Walk(route[0]);
            yield return Walk(new Vector2(-4.8f,-3.2f));
            yield return Walk(new Vector2(-4.8f,3.1f));
            var npc = GameObject.Find("Station/Characters/StationVisitor").transform;
            yield return OpenAt(npc.position + Vector3.up * 1.25f, "Visitor", "");
        }
        else
        {
            foreach (var point in route) yield return Walk(point);
            yield return Aim(new Vector3(11,1.5f,9));
            yield return Hold(.8f);
            Screenshot("Platform");
            for (int i = route.Length - 2; i >= 0; --i) yield return Walk(route[i]);
            yield return Walk(new Vector2(start.x,start.z));
            yield return Aim(new Vector3(-9.83f,1.06f,-4.45f));
            yield return Hold(.6f);
            Screenshot("Office");
        }
        recording = false;
    }

    IEnumerator Walk(Vector2 point)
    {
        for (float elapsed=0; elapsed<12; elapsed+=Time.unscaledDeltaTime)
        {
            Vector3 p = view.transform.position;
            var dir = new Vector3(point.x-p.x,0,point.y-p.z);
            if (dir.magnitude < .18f)
            {
                InputSystem.QueueStateEvent(keyboard,new KeyboardState());
                Log("waypoint " + player.transform.position.ToString("F2"));
                yield return Step();
                yield break;
            }
            float angle = Turn(dir);
            InputSystem.QueueStateEvent(keyboard, angle < 12 ? new KeyboardState(Key.W) : new KeyboardState());
            yield return Step();
        }
        throw new InvalidOperationException("Cannot walk to " + point + " from " + player.transform.position + " forward=" + view.transform.forward);
    }

    float Turn(Vector3 dir)
    {
        var rotation = Quaternion.LookRotation(dir).eulerAngles;
        var current = view.transform.eulerAngles;
        float yaw = Mathf.DeltaAngle(current.y,rotation.y);
        float pitch = Mathf.DeltaAngle(current.x,rotation.x);
        float cap = 160 * Mathf.Clamp(Time.unscaledDeltaTime,.006f,.08f);
        var delta = new Vector2(Mathf.Clamp(yaw,-cap,cap),-Mathf.Clamp(pitch,-cap,cap)) / player.LookSensitivity;
        InputSystem.QueueDeltaStateEvent(mouse.delta,delta);
        return Mathf.Max(Mathf.Abs(yaw),Mathf.Abs(pitch));
    }

    IEnumerator Aim(Vector3 target)
    {
        for (float t=0;t<4;t+=Time.unscaledDeltaTime)
        {
            if (Turn(target-view.transform.position) < .35f) { yield return Step(); yield break; }
            yield return Step();
        }
        throw new InvalidOperationException("Aim timed out " + view.transform.forward);
    }

    IEnumerator OpenAt(Vector3 target,string label,string expected)
    {
        yield return Aim(target);
        yield return Hold(.55f);
        if (player.FocusedTarget == null || (expected.Length > 0 && !player.FocusedTarget.DisplayName.Contains(expected)))
        {
            foreach (var hit in Physics.RaycastAll(view.transform.position,view.transform.forward,3f))
            {
                var path = hit.transform.name;
                for (var t = hit.transform.parent; t; t = t.parent) path = t.name + "/" + path;
                Log($"ray {hit.distance:F3} {path} {hit.collider.GetType().Name}");
            }
            throw new InvalidOperationException(label + " focus " + player.FocusedTarget?.DisplayName + " camera " + view.transform.position);
        }
        var name = player.FocusedTarget.DisplayName;
        if (label == "Visitor" && player.FocusedTarget.Kind != InteractionKind.Npc) throw new InvalidOperationException(name);
        Screenshot(label + "Prompt");
        InputSystem.QueueStateEvent(keyboard,new KeyboardState(Key.E));
        yield return Step();
        InputSystem.QueueStateEvent(keyboard,new KeyboardState());
        yield return Hold(.7f);
        if (!player.IsInterfaceOpen || player.ActiveTarget.DisplayName != name) throw new InvalidOperationException(label + " open failed");
        Screenshot(label + "Panel");
        yield return Hold(.6f);
        InputSystem.QueueStateEvent(keyboard,new KeyboardState(Key.Escape));
        yield return Step();
        InputSystem.QueueStateEvent(keyboard,new KeyboardState());
        yield return Hold(.4f);
        if (player.IsInterfaceOpen) throw new InvalidOperationException(label + " close failed");
        Log("opened and closed " + name);
    }

    IEnumerator Hold(float duration)
    {
        for (float t=0;t<duration;t+=Time.unscaledDeltaTime) yield return Step();
    }

    IEnumerator Step()
    {
        // Always cross an Update boundary before reading back the render.
        yield return null;
        yield return rendered;
        if (!recording) yield break;
        var p = player.transform.position;
        if (Benchmark)
        {
            float ms = Time.unscaledDeltaTime * 1000f;
            times.Add(ms);
            samples.Add(string.Format(CI,"{0},{1:F3},{2:F3},{3:F3},{4:F3}",frame,ms,p.x,p.y,p.z));
        }
        else Save(Path.Combine(frames,frame.ToString("D5")+".jpg"),true);
        frame++;
    }

    void Screenshot(string name) { if (!Benchmark) Save(Path.Combine(output,name+".png"),false); }
    static void Save(string path,bool jpeg)
    {
        var image = ScreenCapture.CaptureScreenshotAsTexture();
        try { File.WriteAllBytes(path,jpeg ? image.EncodeToJPG(86) : image.EncodeToPNG()); }
        finally { Destroy(image); }
    }
    void Log(string message) => File.AppendAllText(Path.Combine(output, Job+".log"),message+"\n");
    void Finish(string status)
    {
        if (keyboard != null) InputSystem.RemoveDevice(keyboard);
        if (mouse != null) InputSystem.RemoveDevice(mouse);
        Time.captureFramerate = 0;
        if (Benchmark && times.Count > 0)
        {
            samples.Insert(0,"frame,ms,x,y,z");
            File.WriteAllLines(Path.Combine(output,"PlayerFrames.csv"),samples);
            times.Sort(); double total=0; foreach (var t in times) total+=t;
            Log(string.Format(CI,"frames={0} seconds={1:F3} fps={2:F2} p95_ms={3:F2} max_ms={4:F2}",times.Count,total/1000,1000*times.Count/total,times[Mathf.CeilToInt(.95f*times.Count)-1],times[times.Count-1]));
        }
        Log(status + " frames=" + frame);
#if UNITY_EDITOR
        UnityEditor.EditorApplication.ExitPlaymode();
#else
        Application.Quit(status == "PASS" ? 0 : 1);
#endif
    }
}
#endif
