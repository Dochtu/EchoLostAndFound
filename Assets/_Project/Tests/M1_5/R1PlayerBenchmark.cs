#if DEVELOPMENT_BUILD && !UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using Unity.Profiling;
using Unity.Profiling.LowLevel.Unsafe;
using UnityEngine;
using UnityEngine.Profiling;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace Echo.M15.Tests
{
    public sealed class R1PlayerBenchmark : MonoBehaviour
    {
        const double WarmSeconds = 6.0;
        const double SampleSeconds = 8.0;
        static readonly CultureInfo CI = CultureInfo.InvariantCulture;
        static readonly string[] MarkerNames = {
            "Draw Calls Count", "Batches Count", "Main Thread", "Render Thread",
            "Gfx.WaitForPresentOnGfxThread", "Gfx.PresentFrame", "WaitForTargetFPS"
        };
        readonly ProfilerRecorder[] counters = new ProfilerRecorder[MarkerNames.Length];
        readonly FrameTiming[] latest = new FrameTiming[1];
        readonly List<Sample> samples = new List<Sample>(2048);
        Camera cameraToMeasure, anchor;
        string output, summary;
        int renders;
        ulong lastStamp;
        bool recordingTrace;

        struct Sample
        {
            public int frame, renders;
            public float phase;
            public double dt;
            public Vector3 position;
            public FrameTiming timing;
            public bool fresh;
            public long draws, batches, main, render, wait, present, capWait;
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-r1-benchmark") >= 0)
                new GameObject("R1 standalone benchmark").AddComponent<R1PlayerBenchmark>();
        }

        IEnumerator Start()
        {
            var routine = Run();
            Exception failure = null;
            while (true)
            {
                bool more;
                try { more = routine.MoveNext(); }
                catch (Exception ex) { failure = ex; break; }
                if (!more) break;
                yield return routine.Current;
            }
            try
            {
                RenderPipelineManager.endCameraRendering -= CountRender;
                StopTrace();
                foreach (var counter in counters) if (counter.Valid) counter.Dispose();
                if (failure == null) Append("Completed");
                else if (summary != null) Append("FAILED " + failure);
            }
            catch (Exception cleanup) { failure = failure ?? cleanup; }
            if (failure != null) Debug.LogError(failure);
            Application.Quit(failure == null ? 0 : 10);
        }

        IEnumerator Run()
        {
            var args = Environment.GetCommandLineArgs();
            int index = Array.IndexOf(args, "-r1-output");
            if (index < 0 || index + 1 >= args.Length || args[index + 1].StartsWith("-"))
                throw new ArgumentException("Expected -r1-output <fresh directory>");
            output = Path.GetFullPath(args[index + 1]);
            Directory.CreateDirectory(output);
            if (Directory.EnumerateFileSystemEntries(output).Any(p =>
                Path.GetFileName(p).StartsWith("R1_", StringComparison.OrdinalIgnoreCase)))
                throw new IOException("R1 capture already exists in " + output);
            summary = Path.Combine(output, "R1_summary.log");
            Append("Started UTC " + DateTime.UtcNow.ToString("O"));
            Application.runInBackground = true;
            Application.targetFrameRate = -1;
            OnDemandRendering.renderFrameInterval = 1;
            Profiler.enabled = false;
            int quality = Array.IndexOf(QualitySettings.names, "High Fidelity");
            if (quality < 0 || SceneManager.GetActiveScene().name != "Station") throw new InvalidOperationException("Expected Station and High Fidelity");
            QualitySettings.SetQualityLevel(quality, true);
            if (Screen.width != 1920 || Screen.height != 1080)
                Screen.SetResolution(1920, 1080, FullScreenMode.Windowed);
            cameraToMeasure = Camera.main;
            anchor = GameObject.Find("Station_MainHall")?.GetComponent<Camera>();
            if (!anchor || !cameraToMeasure || !cameraToMeasure.isActiveAndEnabled) throw new InvalidOperationException("Missing active camera or Station_MainHall anchor");
            cameraToMeasure.fieldOfView = anchor.fieldOfView;
            cameraToMeasure.nearClipPlane = anchor.nearClipPlane;
            RenderPipelineManager.endCameraRendering += CountRender;
            Pose(false, 0);
            yield return new WaitForSecondsRealtime(2);
            OpenCounters();
            Append(FormattableString.Invariant($"Unity={Application.unityVersion} development={Debug.isDebugBuild} CPU={SystemInfo.processorType} GPU={SystemInfo.graphicsDeviceName} API={SystemInfo.graphicsDeviceType} pipeline={GraphicsSettings.currentRenderPipeline?.name} quality={QualitySettings.names[QualitySettings.GetQualityLevel()]} screen={Screen.width}x{Screen.height} mode={Screen.fullScreenMode} displayHz={Screen.currentResolution.refreshRateRatio.value:F3} targetFrameRate={Application.targetFrameRate} frameInterval={OnDemandRendering.renderFrameInterval} frameTimingEnabled={FrameTimingManager.IsFeatureEnabled()} warmSeconds={WarmSeconds} sampleSeconds={SampleSeconds}"));
            bool offFirst = Array.IndexOf(args, "-r1-off-first") >= 0;
            foreach (int sync in (offFirst ? new[] { 0, 1 } : new[] { 1, 0 }))
            {
                QualitySettings.vSyncCount = sync;
                foreach (bool moving in new[] { false, true })
                    foreach (var step in Segment(sync, moving)) yield return step;
            }
            if (Array.IndexOf(args, "-r1-profile") >= 0)
            {
                // Separate from the four timed sections. Capture the real moving hall with VSync off.
                QualitySettings.vSyncCount = 0;
                Pose(true, 0);
                yield return new WaitForSecondsRealtime(2);
                Profiler.logFile = Path.Combine(output, "R1_moving_off.raw");
                recordingTrace = true;
                Profiler.enableBinaryLog = true;
                Profiler.enabled = true;
                for (int i = 0; i < 120; i++) { Pose(true, i / 119f); yield return null; }
                StopTrace();
                Append("Profiler trace separate from samples: VSync=0 moving hall, 120 frames");
            }
        }

        void StopTrace()
        {
            if (!recordingTrace) return;
            Profiler.enabled = false;
            Profiler.enableBinaryLog = false;
            Profiler.logFile = "";
            recordingTrace = false;
        }

        void OpenCounters()
        {
            var handles = new List<ProfilerRecorderHandle>();
            ProfilerRecorderHandle.GetAvailable(handles);
            foreach (var handle in handles)
            {
                var desc = ProfilerRecorderHandle.GetDescription(handle);
                int i = Array.IndexOf(MarkerNames, desc.Name);
                if (i < 0 || counters[i].Valid) continue;
                counters[i] = new ProfilerRecorder(handle, 1, ProfilerRecorderOptions.Default | ProfilerRecorderOptions.StartImmediately);
                Append($"recorder={desc.Name} unit={desc.UnitType} category={desc.Category.Name} valid={counters[i].Valid}");
            }
            for (int i = 0; i < counters.Length; i++)
                if (!counters[i].Valid) Append("Unavailable recorder: " + MarkerNames[i]);
        }

        long Read(int i) => counters[i].Valid && counters[i].Count > 0 ? counters[i].LastValue : -1;

        void CountRender(ScriptableRenderContext context, Camera rendered)
        {
            if (rendered == cameraToMeasure) renders++;
        }

        void Pose(bool moving, float phase)
        {
            float travel = moving ? .5f - .5f * Mathf.Cos(2 * Mathf.PI * phase) : 0;
            // Travel up the central aisle, turn gently toward the hall, and return to the fixed shot.
            var position = anchor.transform.position + new Vector3(-1.75f, 0, 5.2f) * travel;
            var rotation = Quaternion.AngleAxis(11f * travel, Vector3.up) * anchor.transform.rotation;
            cameraToMeasure.transform.SetPositionAndRotation(position, rotation);
        }

        IEnumerable Segment(int sync, bool moving)
        {
            string name = $"R1_vsync{sync}_{(moving ? "moving" : "static")}";
            double start = Time.realtimeSinceStartupAsDouble;
            while (Time.realtimeSinceStartupAsDouble - start < WarmSeconds)
            {
                Pose(moving, (float)((Time.realtimeSinceStartupAsDouble - start) / WarmSeconds));
                FrameTimingManager.CaptureFrameTimings();
                yield return null;
            }
            samples.Clear();
            // A timing can lag the rendered frame. Keep the source timestamp and collect each result once.
            lastStamp = FrameTimingManager.GetLatestTimings(1, latest) > 0 ? latest[0].frameStartTimestamp : 0;
            start = Time.realtimeSinceStartupAsDouble;
            do
            {
                float phase = Mathf.Clamp01((float)((Time.realtimeSinceStartupAsDouble - start) / SampleSeconds));
                Pose(moving, phase);
                var position = cameraToMeasure.transform.position;
                int before = renders;
                int frame = Time.frameCount;
                FrameTimingManager.CaptureFrameTimings();
                yield return null;
                if (Screen.width != 1920 || Screen.height != 1080 || cameraToMeasure.pixelWidth != 1920 ||
                    cameraToMeasure.pixelHeight != 1080 || QualitySettings.vSyncCount != sync || Profiler.enabled)
                    throw new InvalidOperationException(name + " resolution, VSync or profiler state changed");
                var s = new Sample {
                    frame = frame, renders = renders - before, dt = Time.unscaledDeltaTime * 1000d,
                    phase = phase, position = position, draws = Read(0), batches = Read(1),
                    main = Read(2), render = Read(3), wait = Read(4), present = Read(5), capWait = Read(6)
                };
                if (FrameTimingManager.GetLatestTimings(1, latest) > 0 && latest[0].frameStartTimestamp > lastStamp)
                {
                    s.fresh = true;
                    s.timing = latest[0];
                    lastStamp = s.timing.frameStartTimestamp;
                }
                samples.Add(s);
            } while (Time.realtimeSinceStartupAsDouble - start < SampleSeconds);
            WriteSegment(name, sync);
        }

        static string F(double x) => x.ToString("0.######", CI);
        static string Timing(Sample s, double value) => s.fresh ? F(value) : "";
        static string Counter(long value) => value < 0 ? "" : value.ToString(CI);

        void WriteSegment(string name, int sync)
        {
            string csv = Path.Combine(output, name + ".csv");
            using (var writer = new StreamWriter(csv, false, new UTF8Encoding(false)))
            {
                writer.WriteLine("frame,phase,cameraX,cameraY,cameraZ,mainCameraRenders,dtMs,ftTimestamp,ftSyncInterval,cpuFrameMs,cpuMainMs,cpuRenderMs,cpuMainPresentWaitMs,gpuMs,drawCalls,batches,mainThreadNs,renderThreadNs,gfxWaitForPresentNs,gfxPresentNs,waitForTargetFpsNs");
                foreach (var s in samples)
                {
                    var t = s.timing;
                    writer.WriteLine(string.Join(",", s.frame.ToString(CI), F(s.phase), F(s.position.x), F(s.position.y), F(s.position.z),
                        s.renders.ToString(CI), F(s.dt), s.fresh ? t.frameStartTimestamp.ToString(CI) : "", s.fresh ? t.syncInterval.ToString(CI) : "",
                        Timing(s,t.cpuFrameTime), Timing(s,t.cpuMainThreadFrameTime), Timing(s,t.cpuRenderThreadFrameTime),
                        Timing(s,t.cpuMainThreadPresentWaitTime), Timing(s,t.gpuFrameTime), Counter(s.draws), Counter(s.batches),
                        Counter(s.main), Counter(s.render), Counter(s.wait), Counter(s.present), Counter(s.capWait)));
                }
            }
            double[] times = samples.Select(s => s.dt).OrderBy(x => x).ToArray();
            double P(double fraction) => times[(int)Math.Ceiling(times.Length * fraction)-1];
            var ft = samples.Where(s => s.fresh).Select(s => s.timing).ToArray();
            string Stats(IEnumerable<double> data)
            {
                var xs = data.ToArray();
                return xs.Length == 0 ? "NA(n=0)" : F(xs.Average()) + "(n=" + xs.Length + ")";
            }
            string Metric(Func<FrameTiming,double> select, bool includeZero = false) =>
                Stats(ft.Select(select).Where(x => includeZero ? x >= 0 : x > 0));
            string Marker(Func<Sample,long> select, double scale) =>
                Stats(samples.Select(select).Where(x => x >= 0).Select(x => x * scale));
            Append(FormattableString.Invariant($"{name} vSync={sync} actual={QualitySettings.vSyncCount} n={samples.Count} rendered={samples.Sum(s=>s.renders)} FPS={1000/times.Average():F2} P50ms={P(.5):F2} P95ms={P(.95):F2} P99ms={P(.99):F2} peakMs={times.Last():F2} over100={times.Count(x=>x>100)} cpuMainMs={Metric(t=>t.cpuMainThreadFrameTime)} cpuRenderMs={Metric(t=>t.cpuRenderThreadFrameTime)} gpuMs={Metric(t=>t.gpuFrameTime)} presentWaitMs={Metric(t=>t.cpuMainThreadPresentWaitTime,true)} draws={Marker(s=>s.draws,1)} batches={Marker(s=>s.batches,1)} mainMarkerMs={Marker(s=>s.main,1e-6)} renderMarkerMs={Marker(s=>s.render,1e-6)} gfxWaitMs={Marker(s=>s.wait,1e-6)} gfxPresentMs={Marker(s=>s.present,1e-6)} waitForTargetMs={Marker(s=>s.capWait,1e-6)}"));
            if (samples.Count < 2 || samples.Any(s => s.renders < 1 || s.dt <= 0) ||
                !samples.Any(s => s.draws > 0) || !samples.Any(s => s.batches > 0))
                throw new InvalidOperationException(name + " failed rendered-frame or draw/batch counter checks");
        }

        void Append(string line) => File.AppendAllText(summary, line + Environment.NewLine);
    }
}
#endif
