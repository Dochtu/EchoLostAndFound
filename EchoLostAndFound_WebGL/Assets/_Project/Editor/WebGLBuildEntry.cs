// Adapted from Tools/Build/WebGLBuildEntry.cs.txt for the M3-A URP project.
using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;
using UnityEngine.Rendering;

namespace EchoLostAndFound.Build
{
    public static class WebGLBuildEntry
    {
        [MenuItem("Echo/Build/WebGL (CI Entry)")]
        public static void BuildFromMenu()
        {
            BuildInternal();
        }

        public static void Build()
        {
            try
            {
                BuildInternal();
                EditorApplication.Exit(0);
            }
            catch (Exception exception)
            {
                Debug.LogError("WebGL build failed: " + exception);
                EditorApplication.Exit(1);
            }
        }

        private static void BuildInternal()
        {
            var output = Environment.GetEnvironmentVariable("DSH_WEBGL_OUTPUT");
            if (string.IsNullOrWhiteSpace(output))
            {
                throw new InvalidOperationException("DSH_WEBGL_OUTPUT is not set.");
            }

            var target = Path.GetFullPath(output);
            var assets = Path.GetFullPath(Application.dataPath);
            if (target.Equals(assets, StringComparison.OrdinalIgnoreCase) ||
                target.StartsWith(assets + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) ||
                Directory.Exists(target) && Directory.EnumerateFileSystemEntries(target).Any(path =>
                    !string.Equals(Path.GetFullPath(path), Path.GetFullPath(Application.consoleLogPath), StringComparison.OrdinalIgnoreCase)))
                throw new InvalidOperationException("Choose a new, empty build directory outside Assets: " + target);

            if (!(GraphicsSettings.currentRenderPipeline is UnityEngine.Rendering.Universal.UniversalRenderPipelineAsset))
                throw new InvalidOperationException("Select the URP asset before building.");

            ApplyCompression(Environment.GetEnvironmentVariable("DSH_WEBGL_COMPRESSION"));
            PlayerSettings.WebGL.decompressionFallback = false;
            PlayerSettings.WebGL.threadsSupport = false;
            PlayerSettings.WebGL.dataCaching = true;
            PlayerSettings.WebGL.exceptionSupport = WebGLExceptionSupport.ExplicitlyThrownExceptionsOnly;

            Directory.CreateDirectory(target);

            var scenes = EditorBuildSettings.scenes
                .Where(scene => scene.enabled)
                .Select(scene => scene.path)
                .ToArray();
            if (scenes.Length == 0)
            {
                throw new InvalidOperationException("No enabled scenes in EditorBuildSettings.");
            }

            Debug.Log("WebGL scenes: " + string.Join(", ", scenes));

            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = scenes,
                locationPathName = target,
                target = BuildTarget.WebGL,
                options = BuildOptions.None,
            });

            var summary = report.summary;
            Debug.Log($"WebGL build {summary.result}: {summary.totalSize} bytes, {summary.totalTime}, errors {summary.totalErrors}");

            if (summary.result != BuildResult.Succeeded)
            {
                throw new InvalidOperationException("BuildResult was " + summary.result);
            }

            if (!File.Exists(Path.Combine(target, "index.html")))
            {
                throw new InvalidOperationException("Build succeeded but index.html is missing in " + target);
            }

            // 记录体量明细，便于与 WebGLCompatibility.md 的预算对照。
            var breakdown = Directory
                .GetFiles(target, "*", SearchOption.AllDirectories)
                .Select(path => new FileInfo(path))
                .OrderByDescending(info => info.Length)
                .Take(15)
                .Select(info => $"  {info.Length,12:N0} B  {Path.GetRelativePath(target, info.FullName)}");
            Debug.Log("WebGL artifact sizes (top 15):\n" + string.Join("\n", breakdown));
        }

        private static void ApplyCompression(string value)
        {
            switch ((value ?? string.Empty).Trim().ToLowerInvariant())
            {
                case "disabled":
                    PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
                    break;
                case "gzip":
                    PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Gzip;
                    break;
                case "":
                case "brotli":
                    PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Brotli;
                    break;
                default:
                    throw new ArgumentException("Unknown DSH_WEBGL_COMPRESSION: " + value);
            }
        }
    }
}
