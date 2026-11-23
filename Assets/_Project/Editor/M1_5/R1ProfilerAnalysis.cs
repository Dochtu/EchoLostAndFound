using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEditorInternal;
using UnityEditor.Profiling;
using UnityEngine;

namespace Echo.M15
{
    internal static class R1ProfilerAnalysis
    {
        internal static void Summarize(string source,string target)
        {
            if(!ProfilerDriver.LoadProfile(Path.GetFullPath(source),false))throw new IOException("Unable to read "+source);
            var stats=new Dictionary<string,double>();
            var peaks=new Dictionary<string,double>();
            var count=new Dictionary<string,int>();
            int frames=0;
            for(int frame=ProfilerDriver.firstFrameIndex;frame<=ProfilerDriver.lastFrameIndex;frame++)
            {
                frames++;
                for(int thread=0;thread<256;thread++)
                {
                    using var view=ProfilerDriver.GetRawFrameDataView(frame,thread);
                    if(!view.valid)break;
                    string t=view.threadName;
                    if(t!="Main Thread" && t!="Render Thread")continue;
                    var sums=new Dictionary<string,double>();
                    for(int i=0;i<view.sampleCount;i++)
                    {
                        var ms=view.GetSampleTimeMs(i);
                        if(ms<.01)continue;
                        string key=t+" / "+view.GetSampleName(i);
                        sums.TryGetValue(key,out double v);sums[key]=v+ms;
                    }
                    foreach(var item in sums)
                    {
                        stats.TryGetValue(item.Key,out double total);stats[item.Key]=total+item.Value;
                        peaks.TryGetValue(item.Key,out double peak);peaks[item.Key]=Math.Max(peak,item.Value);
                        count.TryGetValue(item.Key,out int n);count[item.Key]=n+1;
                    }
                }
            }
            var lines=new List<string>{$"Source={source} frames={frames}. Inclusive marker durations summed by name per thread per frame; nested samples overlap.","thread / marker,mean ms per captured frame,highest frame total ms,frames with marker"};
            foreach(var row in stats.OrderByDescending(x=>x.Value))
                if(row.Value/Math.Max(1,frames)>.05 || row.Key.IndexOf("Present",StringComparison.OrdinalIgnoreCase)>=0)
                    lines.Add(FormattableString.Invariant($"\"{row.Key.Replace("\"","'")}\",{row.Value/frames:F3},{peaks[row.Key]:F3},{count[row.Key]}"));
            if(frames<1||stats.Count==0) throw new InvalidDataException(source+" has no CPU samples");
            File.WriteAllLines(target,lines);
        }
    }
}
