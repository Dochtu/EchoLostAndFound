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

namespace Echo.M15 {
[InitializeOnLoad]
internal static class EditorEvidence {
    const string Output="Docs/Evidence/Stage4_M1_5/";
    static double since;
    static EditorEvidence() => EditorApplication.update+=Tick;
    static void Tick()
    {
        int step=SessionState.GetInt("Echo.M15.Windows",0);
        if(step==0 || EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isCompiling) return;
        if(step==1)
        {
            var w=SceneView.lastActiveSceneView ?? EditorWindow.GetWindow<SceneView>();
            w.Focus(); Selection.activeGameObject=GameObject.Find("Station/Environment/WaitingHall");
            if(Camera.main) w.LookAtDirect(Camera.main.transform.position+Camera.main.transform.forward*9,Camera.main.transform.rotation,9);
            EditorGUIUtility.PingObject(Selection.activeGameObject);
        }
        else
        {
            if(EditorApplication.timeSinceStartup-since<1.2) return;
            if(step==2)
            {
                Frame("12_Unity_SceneHierarchy");
                EditorWindow.GetWindow(typeof(Editor).Assembly.GetType("UnityEditor.ConsoleWindow")).Focus();
            }
            else {Frame("13_Unity_Console"); SessionState.SetInt("Echo.M15.Windows",0); return;}
        }
        since=EditorApplication.timeSinceStartup;
        SessionState.SetInt("Echo.M15.Windows",step+1);
    }
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
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr hwnd,int command);
    internal static void Restore()
    {
        using var process=Process.GetCurrentProcess();
        var hwnd=process.MainWindowHandle;
        if(hwnd!=IntPtr.Zero && IsIconic(hwnd)) ShowWindow(hwnd,9);
    }
    internal static void Frame(string name,string output=Output)
    {
        using var process = Process.GetCurrentProcess();
        IntPtr hwnd=process.MainWindowHandle;
        Restore();
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
            File.WriteAllBytes(output+name+".png",texture.EncodeToPNG());
            File.AppendAllText(output+"Hall.log",$"{name} Unity window {w}x{h} Play={Application.isPlaying}\n");
        }
        finally
        {
            SelectObject(dc,prev); DeleteObject(bmp); DeleteDC(dc); ReleaseDC(hwnd,src);
            if(texture) Object.DestroyImmediate(texture);
        }
    }
}}
