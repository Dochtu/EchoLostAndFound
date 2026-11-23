#if UNITY_EDITOR
using System;
using System.Collections;
using System.IO;
using UnityEngine;
using UnityEditor;

namespace Echo.M15
{
    // Executes on the Game View camera in Play Mode. Fixed simulation time gives
    // the encoded frames the same timing as the running Animator.
    public class R1CaptureRunner : MonoBehaviour
    {
        const string Output="Docs/Evidence/M1_5_R1/";
        public Action CaptureWindow;
        public Action Finish;
        public bool WindowOnly;
        Camera shot;
        Animator actor;
        string LogFile=>Output+"Capture.log";

        IEnumerator Start()
        {
            var run=Capture();
            while(true)
            {
                object yielded;
                try { if(!run.MoveNext()) break; yielded=run.Current; }
                catch(Exception e){File.AppendAllText(LogFile,e+"\n");break;}
                yield return yielded;
            }
            Time.captureFramerate=0;
            Finish?.Invoke();
        }

        IEnumerator Capture()
        {
            Directory.CreateDirectory(Output);
            shot=Camera.main;
            actor=GameObject.Find("Station/Characters/StationVisitor").GetComponentInChildren<Animator>();
            if(!actor.isHuman || !actor.avatar.isValid) throw new InvalidDataException("Humanoid Avatar");
            Application.runInBackground=true;
            Time.captureFramerate=24;
            for(int i=0;i<100;i++) yield return null;
            if(Screen.width!=1920 || Screen.height!=1080) throw new InvalidDataException("Game View "+Screen.width+"x"+Screen.height);
            File.AppendAllText(LogFile,$"{DateTime.Now:s} {Application.unityVersion} Play={Application.isPlaying} {Screen.width}x{Screen.height} {QualitySettings.names[QualitySettings.GetQualityLevel()]} {SystemInfo.graphicsDeviceName}\n");
            foreach(var entry in new[]{("Station_MainHall","Hall_After"),("Station_Platform","Platform_After"),("Station_NPC","NPC_After"),("Station_NPC","Face_Closeup")})
            {
                var anchor=GameObject.Find(entry.Item1).GetComponent<Camera>();
                shot.transform.SetPositionAndRotation(anchor.transform.position,anchor.transform.rotation);
                shot.fieldOfView=anchor.fieldOfView;shot.nearClipPlane=anchor.nearClipPlane;
                if(entry.Item2=="Face_Closeup")
                {
                    var eyes=(actor.GetBoneTransform(HumanBodyBones.LeftEye)??actor.GetBoneTransform(HumanBodyBones.Head)).position;
                    var head=actor.GetBoneTransform(HumanBodyBones.Head).position;
                    var look=head+Vector3.up*.067f;
                    if(Vector3.Distance(head,eyes)>.025f) look=(eyes+head)*.5f+Vector3.up*.015f;
                    var forward=Vector3.ProjectOnPlane(anchor.transform.position-head,Vector3.up).normalized;
                    shot.transform.position=look+forward*.82f+Vector3.up*.015f;
                    shot.transform.LookAt(look);shot.fieldOfView=29;shot.nearClipPlane=.04f;
                }
                for(int i=0;i<36;i++) yield return null;
                yield return new WaitForEndOfFrame();
                if(!WindowOnly)Save(Output+entry.Item2+".png",false);
                if(entry.Item2=="Hall_After")
                {
                    CaptureWindow?.Invoke();
                    // Keep the shot in place while the Editor captures its own window
                    // after this Game View render has ended.
                    for(int i=0;i<8;i++)yield return null;
                    if(WindowOnly)yield break;
                }
            }
            var npc=GameObject.Find("Station_NPC").GetComponent<Camera>();
            shot.transform.SetPositionAndRotation(npc.transform.position,npc.transform.rotation);
            shot.fieldOfView=npc.fieldOfView;shot.nearClipPlane=npc.nearClipPlane;
            for(int i=0;i<30;i++)yield return null;
            actor.Play(actor.GetCurrentAnimatorStateInfo(0).fullPathHash,0,0f);
            int count=Mathf.CeilToInt(actor.GetCurrentAnimatorStateInfo(0).length*24)+1;
            if(count<60 || count>241) throw new InvalidDataException("Unexpected Idle duration");
            string frames="Library/R1Baseline/IdleFrames";Directory.CreateDirectory(frames);
            float start=0,last=0;
            for(int f=0;f<count;f++)
            {
                yield return new WaitForEndOfFrame();
                last=actor.GetCurrentAnimatorStateInfo(0).normalizedTime;if(f==0)start=last;
                Save(Path.Combine(frames,f.ToString("D4")+".jpg"),true);
            }
            File.AppendAllText(LogFile,$"{DateTime.Now:s} Idle frames={count} simulationHz=24 normalizedTime={start:F4}..{last:F4} camera={npc.name}\n");
            if(last-start<.99f) throw new InvalidDataException("Incomplete animation cycle");
        }

        static void Save(string path,bool jpeg)
        {
            var image=ScreenCapture.CaptureScreenshotAsTexture();
            try
            {
                if(image.width!=1920 || image.height!=1080)throw new InvalidDataException("Unexpected readback dimensions");
                File.WriteAllBytes(path,jpeg?image.EncodeToJPG(96):image.EncodeToPNG());
            }
            finally { Destroy(image); }
        }
    }
}
#endif
