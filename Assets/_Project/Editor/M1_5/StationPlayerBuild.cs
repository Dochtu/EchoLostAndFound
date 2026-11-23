using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace Echo.M15
{
    [InitializeOnLoad]
    internal static class StationPlayerBuild
    {
        const string Request="Temp/M15-PlayerBuild.request";
        const string Log="Docs/Evidence/Stage4_M1_5/PlayerBuild.log";
        static StationPlayerBuild() => EditorApplication.update+=Poll;
        static void Poll()
        {
            if(!File.Exists(Request) || EditorApplication.isUpdating || EditorApplication.isCompiling || EditorApplication.isPlayingOrWillChangePlaymode) return;
            File.Delete(Request);
            string dir="Builds/M1_5_QA_"+DateTime.Now.ToString("yyyyMMdd_HHmmss");
            try
            {
                StationAudit.Run();
                var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{
                    scenes=new[]{"Assets/_Project/Scenes/Station.unity"},target=BuildTarget.StandaloneWindows64,
                    locationPathName=dir+"/EchoStation.exe", options=BuildOptions.Development});
                File.AppendAllText(Log,$"{DateTime.Now:s} {report.summary.result} {report.summary.outputPath} errors={report.summary.totalErrors} warnings={report.summary.totalWarnings}\n");
            }
            catch(Exception e){File.AppendAllText(Log,e+Environment.NewLine);}
        }
    }
}

