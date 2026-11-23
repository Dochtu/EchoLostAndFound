#if DEVELOPMENT_BUILD && !UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.Rendering;

namespace Echo.M15.Tests
{
    public class StationPlayerBenchmark : MonoBehaviour
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            if(Array.IndexOf(Environment.GetCommandLineArgs(),"-m15-benchmark")>=0)
                new GameObject("Station benchmark").AddComponent<StationPlayerBenchmark>();
        }
        IEnumerator Start()
        {
            var args=Environment.GetCommandLineArgs();
            int opt=Array.IndexOf(args,"-m15-output");
            if(opt<0 || opt+1>=args.Length){ Application.Quit(2); yield break; }
            string output=args[opt+1];
            var cam=Camera.main;
            int quality=Array.IndexOf(QualitySettings.names,"High Fidelity");
            if(!cam || quality<0) {Application.Quit(3);yield break;}
            QualitySettings.SetQualityLevel(quality,true);
            if(Screen.width!=1920 || Screen.height!=1080)
            {
                bool native1080=Display.main.systemWidth==1920 && Display.main.systemHeight==1080;
                Screen.SetResolution(1920,1080,native1080?FullScreenMode.FullScreenWindow:FullScreenMode.Windowed);
            }
            Application.runInBackground=true;
            yield return new WaitForSecondsRealtime(3);
            if(Screen.width!=1920 || Screen.height!=1080){File.WriteAllText(output,"Resolution mismatch"); Application.Quit(4);yield break;}
            File.WriteAllText(output,$"Standalone Development Player {Application.unityVersion} {Screen.width}x{Screen.height} High Fidelity {SystemInfo.graphicsDeviceName} {SystemInfo.graphicsDeviceType}\n");
            int rendered=0;
            void CountCamera(ScriptableRenderContext context,Camera camera)
            {
                if(camera==cam) rendered++;
            }
            RenderPipelineManager.endCameraRendering+=CountCamera;
            foreach(string shot in new[]{"Station_MainHall","Station_LostFound","Station_Watch","Station_NPC","Station_Platform"})
            {
                var anchor=GameObject.Find(shot).GetComponent<Camera>();
                cam.transform.SetPositionAndRotation(anchor.transform.position,anchor.transform.rotation);
                cam.fieldOfView=anchor.fieldOfView;cam.nearClipPlane=anchor.nearClipPlane;
                yield return new WaitForSecondsRealtime(3);
                var frames=new List<float>(300);
                int startCount=rendered;
                for(int i=0;i<300;i++) {yield return null;frames.Add(Time.unscaledDeltaTime*1000);}
                frames.Sort();
                int drawn=rendered-startCount;
                if(drawn<299)
                {
                    File.AppendAllText(output,$"{shot} invalid: only {drawn} main camera renders in 300 frames\n");
                    Application.Quit(5);
                    yield break;
                }
                File.AppendAllText(output,FormattableString.Invariant($"{shot} n=300 drawn={drawn} FPS={1000/frames.Average():F1} P95ms={frames[284]:F1} peakMs={frames.Last():F1} over100={frames.Count(t=>t>100)}\n"));
                if(shot=="Station_MainHall")
                {
                    yield return new WaitForEndOfFrame();
                    var proof=ScreenCapture.CaptureScreenshotAsTexture();
                    File.WriteAllBytes(Path.Combine(Path.GetDirectoryName(output),"Player_MainHall.png"),proof.EncodeToPNG());
                    Destroy(proof);
                }
            }
            RenderPipelineManager.endCameraRendering-=CountCamera;
            File.AppendAllText(output,"Completed\n"); Application.Quit();
        }
    }
}
#endif
