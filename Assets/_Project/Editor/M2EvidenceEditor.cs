using System;
using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEditor.TestTools.TestRunner.Api;
using UnityEngine;
using UnityEngine.SceneManagement;

// One-shot jobs for the editor already holding Station open.
[InitializeOnLoad]
internal static class M2EvidenceEditor
{
    const string Request = "Library/M2/request";
    const string Output = "Docs/Evidence/Stage4_M2/";
    const string Station = "Assets/_Project/Scenes/Station.unity";
    const string TestJob = "Echo.M2.TestJob";

    static M2EvidenceEditor()
    {
        EditorApplication.update += Tick;
        ScriptableObject.CreateInstance<TestRunnerApi>().RegisterCallbacks(new Results());
        EditorApplication.playModeStateChanged += state =>
        {
            var job = SessionState.GetString("Echo.M2.Capture", "");
            if (state != PlayModeStateChange.EnteredPlayMode || job == "") return;
            SessionState.EraseString("Echo.M2.Capture");
            var runner = new GameObject("M2 input replay").AddComponent<M2EvidenceReplay>();
            runner.Job = job;
        };
    }

    sealed class Results : ICallbacks
    {
        public void RunStarted(ITestAdaptor t) { }
        public void TestStarted(ITestAdaptor t) { }
        public void TestFinished(ITestResultAdaptor t) { }
        public void RunFinished(ITestResultAdaptor t)
        {
            string job = SessionState.GetString(TestJob, "");
            if (job == "") return;
            TestRunnerApi.SaveResultToFile(t, Path.GetFullPath(Output + job + ".xml"));
            SessionState.EraseString(TestJob);
            Log(job + " " + t.TestStatus + " pass=" + t.PassCount + " fail=" + t.FailCount);
        }
    }

    static void Log(string message) => File.AppendAllText(Output + "EditorJobs.log", DateTime.Now.ToString("s") + " " + message + "\n");

    static void Tick()
    {
        if (!File.Exists(Request) || EditorApplication.isCompiling || EditorApplication.isUpdating ||
            EditorApplication.isPlayingOrWillChangePlaymode) return;
        var job = File.ReadAllText(Request).Trim();
        File.Delete(Request);
        try
        {
            Log(job + " started");
            if (job == "refresh") { AssetDatabase.Refresh(); return; }
            if (SceneManager.GetActiveScene().isDirty) throw new InvalidOperationException("Open scene has unsaved changes");
            if (job == "EditMode" || job == "PlayMode")
            {
                SessionState.SetString(TestJob, job);
                var filter = new Filter { testMode = (TestMode)Enum.Parse(typeof(TestMode), job), groupNames = new[] { "M2" } };
                ScriptableObject.CreateInstance<TestRunnerApi>().Execute(new ExecutionSettings(filter));
                return;
            }
            if (job == "setup")
            {
                M2StationSetup.Apply();
                Log("Station integration returned");
                return;
            }
            EditorSceneManager.OpenScene(Station);
            if (job == "build")
            {
                var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                    scenes = new[] { Station }, target = BuildTarget.StandaloneWindows64,
                    locationPathName = "Builds/M2/Station.exe", options = BuildOptions.Development });
                Log($"build {report.summary.result} errors={report.summary.totalErrors} warnings={report.summary.totalWarnings}");
                return;
            }
            if (job != "Route" && job != "Interaction") throw new ArgumentException(job);
            var view = EditorWindow.GetWindow(typeof(Editor).Assembly.GetType("UnityEditor.GameView"));
            view.GetType().GetMethod("SetCustomResolution", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                ?.Invoke(view, new object[] { new Vector2(1280,720), "M2 Evidence" });
            view.Show();
            view.Focus();
            SessionState.SetString("Echo.M2.Capture", job);
            EditorApplication.EnterPlaymode();
        }
        catch (Exception e) { Log(e.ToString()); }
    }
}
