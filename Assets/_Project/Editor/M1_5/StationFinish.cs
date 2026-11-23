using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;
using UnityEngine.SceneManagement;

namespace Echo.M15
{
    [InitializeOnLoad]
    internal static class StationFinish
    {
        const string ScenePath="Assets/_Project/Scenes/Station.unity";
        const string Art="Assets/_Project/Art/";
        const string Evidence="Docs/Evidence/Stage4_M1_5/";
        const string Request="Temp/M15-Finish.request";
        static readonly Dictionary<string,string> Slots = new Dictionary<string,string> {
            {"SeasonedWood","PolishedWood"},{"DarkWood","DarkWood"},{"PaintedIron","CastIron"},
            {"BrassFasteners","WornBrass"},{"RunningSteel","Station Scored Steel"},{"OpalGlass","Opal"},{"Paving","WeatheredConcrete"},{"Grout","Grout"},
            {"OldFabric","OldFabric"},{"Leather","Leather"},{"Paper","Paper"},{"Thread","Paper"},{"BindingThread","Station Twill Seams"},
            {"Watch_SatinBrass","WornBrass"},{"Watch_PolishedBrass","Station Worn Brass"},
            {"Watch_Patina","Station Brass Patina"},{"Watch_BluedSteel","BluedSteel"},
            {"Watch_IvoryEnamel","Station Ivory Glaze"},{"Watch_DialInk","Station Dark Dial Ink"},
            {"Watch_EngravingRecess","Station Brass Patina"},{"Watch_Crystal","Station Clear Watch Crystal"}
        };
        static StationFinish() => EditorApplication.update+=Poll;
        static void Poll()
        {
            if(!File.Exists(Request) || EditorApplication.isUpdating || EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isCompiling) return;
            File.Delete(Request);
            try { Run(); } catch(Exception e) { File.AppendAllText(Evidence+"Finish.log",DateTime.Now+" FAILED "+e+Environment.NewLine); }
        }
        static T Load<T>(string p) where T:UnityEngine.Object => AssetDatabase.LoadAssetAtPath<T>(p) ?? throw new FileNotFoundException(p);
        static Material Mat(string name) => Load<Material>((name.StartsWith("Station ")?Art+"Materials/":HallSurfaces.Materials)+name+".mat");
        static void Folder(string p)
        {
            if(AssetDatabase.IsValidFolder(p)) return;
            string dir=p.Substring(0,p.LastIndexOf('/'));
            Folder(dir); AssetDatabase.CreateFolder(dir,Path.GetFileName(p));
        }
        static GameObject Wrapper(string name,string kind)
        {
            var model=Load<GameObject>(Art+kind+"/M1_5/"+name+".fbx");
            string dir="Assets/_Project/Prefabs/"+kind+"/M1_5";
            Folder(dir);
            var source=(GameObject)PrefabUtility.InstantiatePrefab(model);
            try
            {
                foreach(var r in source.GetComponentsInChildren<MeshRenderer>())
                {
                    if(r.sharedMaterials.Any(m=>m.name=="Watch_Crystal")) r.shadowCastingMode=UnityEngine.Rendering.ShadowCastingMode.Off;
                    r.sharedMaterials=r.sharedMaterials.Select(m=>Mat(Slots[m.name])).ToArray();
                    PrefabUtility.RecordPrefabInstancePropertyModifications(r);
                }
                return PrefabUtility.SaveAsPrefabAsset(source,dir+"/"+name+".prefab");
            }
            finally {UnityEngine.Object.DestroyImmediate(source);}
        }
        static Transform Place(GameObject prefab, Transform parent, string key, Vector3 pos)
        {
            var old=parent.Find(key);
            var t=old?old:((GameObject)PrefabUtility.InstantiatePrefab(prefab,parent)).transform;
            t.name=key;t.localPosition=pos;
            PrefabUtility.RecordPrefabInstancePropertyModifications(t);
            return t;
        }
        static void Hide(Renderer r)
        {
            r.enabled=false;PrefabUtility.RecordPrefabInstancePropertyModifications(r);
        }
        static void Prepare()
        {
            HallSurfaces.Surface("Wood","PolishedWood",1.32f,new Color(.92f,.83f,.72f),.46f);
            HallSurfaces.Surface("Canvas","OldFabric",2,new Color(.76f,.73f,.63f),.64f);
            HallSurfaces.Surface("Leather","Leather",2.2f,new Color(.72f,.64f,.54f),.56f);
            HallSurfaces.Surface("Paper","Paper",1.4f,new Color(.95f,.89f,.79f),.23f);
            HallSurfaces.Surface("Concrete","WeatheredConcrete",.8f,new Color(.74f,.75f,.73f),.45f);
            HallSurfaces.Surface("WetConcrete","WetConcrete",1f,new Color(.81f,.83f,.85f),.35f);
            HallSurfaces.Surface("WetConcrete","WetStone",.92f,new Color(.59f,.63f,.67f),.42f);
            HallSurfaces.Variant("Station Scored Steel","BluedSteel",m=>{
                m.SetColor("_BaseColor",new Color(.092f,.15f,.22f));m.SetFloat("_Smoothness",.5f);
            });
            HallSurfaces.Variant("Station Charcoal Felt","DeskFelt",m=>{
                m.SetColor("_BaseColor",new Color(.24f,.25f,.24f));m.SetFloat("_Smoothness",.12f);
                m.SetFloat("_Metallic",0);m.SetFloat("_SpecularOcclusionMode",1);
            });
            HallSurfaces.Variant("Station Worn Brass","WornBrass",m=>{
                m.SetTexture("_NormalMap",AssetDatabase.LoadAssetAtPath<Texture2D>(Art+"Textures/M1_5/Iron/Normal.jpg"));
                m.SetFloat("_NormalScale",.12f);m.SetFloat("_Metallic",.88f);m.SetFloat("_Smoothness",.59f);
            });
        }
        static void Refinish(Transform area, Dictionary<string,string> remap)
        {
            foreach(var r in area.GetComponentsInChildren<MeshRenderer>())
            {
                var mats=r.sharedMaterials;
                bool changed=false;
                for(int i=0;i<mats.Length;i++) if(mats[i] && remap.TryGetValue(mats[i].name,out string n)){mats[i]=Mat(n);changed=true;}
                if(changed){r.sharedMaterials=mats;PrefabUtility.RecordPrefabInstancePropertyModifications(r);}
            }
        }

        static void Intake()
        {
            var office=GameObject.Find("Station/Environment/LostAndFound").transform;
            var counter=office.Find("Counter");
            foreach(Transform child in counter)
                if(new[]{"Paneled cabinet","Stone kick","Bullnose writing top","Brass edge","Panel stile","Raised panel"}.Contains(child.name)) Hide(child.GetComponent<Renderer>());
            Place(Wrapper("IntakeCabinet","Props"),counter,"M1_5 Intake cabinet",Vector3.zero);
            var register=Wrapper("BoundRegister","Props");
            foreach(Transform book in counter)
            {
                if(book.name!="Ledger binding") continue;
                Hide(book.Find("Cloth cover").GetComponent<Renderer>()); Hide(book.Find("Page block").GetComponent<Renderer>());
                Place(register,book,"M1_5 Register",Vector3.zero);
            }
            var bag=counter.Find("A-0641 LostItemBag");
            var holdall=Wrapper("FoundHoldall","Props");
            foreach(Transform item in bag) if(item.name=="Cloth holdall" || item.name=="Leather strap") Hide(item.GetComponent<Renderer>());
            Place(holdall,bag,"M1_5 Holdall",Vector3.zero); Hide(bag.Find("Bag enamel plate/Folded lip").GetComponent<Renderer>());
            var watch=GameObject.Find("Station/Props/PocketWatch").transform;
            foreach(Transform original in watch) if(original.name!="M1_5 Evidence watch") foreach(var r in original.GetComponentsInChildren<Renderer>()) Hide(r);
            Place(Wrapper("EvidenceWatch","Props"),watch,"M1_5 Evidence watch",Vector3.zero);
            Refinish(office,new Dictionary<string,string>{{"Station Aged Walnut","AgedWood"},{"Station Smoked Oak","DarkWood"},{"Station Aged Oat Plaster","OldPlaster"},{"Station Charcoal Felt","OldFabric"},{"Station Ivory Ledger Paper","Paper"}});
            var felt=counter.Find("Watch felt").GetComponent<Renderer>();
            felt.sharedMaterial=Mat("DeskFelt"); PrefabUtility.RecordPrefabInstancePropertyModifications(felt);
            var lamp=counter.Find("Banker desk lamp");
            foreach(Transform part in lamp) if(part.name!="M1_5 Desk lamp") Hide(part.GetComponent<Renderer>());
            Place(Wrapper("IntakeLamp","Props"),lamp,"M1_5 Desk lamp",Vector3.zero);
            var shelves=office.Find("Shelves and pigeonholes");
            var carton=Wrapper("ArchiveCarton","Props");var folio=Wrapper("TiedFolios","Props");
            int box=0;
            foreach(var item in shelves.Cast<Transform>().ToArray())
            {
                if(item.name=="Paper slip") Hide(item.GetComponent<Renderer>());
                if(item.name!="Bound archive") continue;
                Hide(item.GetComponent<Renderer>());
                var pos=item.localPosition-Vector3.up*.153f;
                Place(box%3==0?folio:carton,shelves,"M1_5 Archive "+box,pos);
                box++;
            }
            var inside=GameObject.Find("Station/Lighting/InteriorLights").transform;
            foreach(Transform fixture in inside)
            {
                if(fixture.name!="Intake pendant" && fixture.name!="Archive pendant") continue;
                fixture.Find("Opaline bowl").GetComponent<Renderer>().sharedMaterial=Mat("Opal");
                var light=fixture.Find("Warm pool").GetComponent<Light>();
                light.transform.localPosition=new Vector3(0,-.41f,0);
                light.intensity=fixture.name=="Intake pendant"?410:350;
                light.GetComponent<HDAdditionalLightData>().shapeRadius=.22f;
            }
            var task=GameObject.Find("Desk lamp task light").GetComponent<Light>();
            task.transform.position=new Vector3(-10.17f,1.49f,-4.20f);
            task.transform.LookAt(office.TransformPoint(new Vector3(-10.05f,1.21f,-5.14f)));
            task.spotAngle=92;task.intensity=84;
        }

        // Preserve the original mesh asset. The remaining submeshes include the safety rail,
        // cable poles, distant wall and track bed. Only the replaced geometry is omitted.
        static void PreserveContext(Transform parent,string child,Func<Vector3,bool> keep)
        {
            var filter=parent.Find(child).GetComponent<MeshFilter>();
            string dir=Art+"Environment/M1_5/";
            string path=dir+child+"_Context.asset";
            var retained=AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if (!retained)
            {
                retained=UnityEngine.Object.Instantiate(filter.sharedMesh);
                var v=retained.vertices;
                for(int i=0;i<retained.subMeshCount;i++)
                {
                    var old=retained.GetTriangles(i);var next=new List<int>();
                    for(int j=0;j<old.Length;j+=3)
                    {
                        var mid=(v[old[j]]+v[old[j+1]]+v[old[j+2]])/3;
                        if(keep(mid)){ next.Add(old[j]);next.Add(old[j+1]);next.Add(old[j+2]); }
                    }
                    retained.SetTriangles(next,i,false);
                }
                AssetDatabase.CreateAsset(retained,path);
            }
            filter.sharedMesh=retained; PrefabUtility.RecordPrefabInstancePropertyModifications(filter);
        }
        static void Platform()
        {
            var area=GameObject.Find("Station/Environment/Platform").transform;
            PreserveContext(area,"Platform_CantileverCanopy",v=>v.x>13);
            PreserveContext(area,"Platform_TrackBed",v=>!(v.y>-.82f && v.y<-.50f && v.x<23.2f && v.x>16));
            var rails=Wrapper("PlatformRailPanel","Environment");
            var bay=Wrapper("PlatformCanopyBay","Environment");
            for(int i=0;i<7;i++) Place(bay,area,"M1_5 Canopy "+i,new Vector3(8.92f,0,-15+5*i));
            for(int i=0;i<21;i++) for(int j=0;j<2;j++) Place(rails,area,"M1_5 Track "+i+"-"+j,new Vector3(17.8f+3.6f*j,-.82f,-40+4*i));
            var deck=area.Find("Platform_CopingAndDrains");
            string tileMesh=Art+"Environment/M1_5/PlatformDrainageUV.asset";
            var paving=AssetDatabase.LoadAssetAtPath<Mesh>(tileMesh);
            if(!paving)
            {
                paving=UnityEngine.Object.Instantiate(deck.GetComponent<MeshFilter>().sharedMesh);
                var uv=paving.uv;var points=paving.vertices;
                var slots=deck.GetComponent<MeshRenderer>().sharedMaterials;
                int slot=Array.FindIndex(slots,m=>m.name=="WetConcrete" || m.name=="Station Rain Darkened Concrete");
                if(slot<0) throw new InvalidDataException("Wet platform band missing");
                foreach(int v in paving.GetTriangles(slot)) uv[v]=new Vector2((points[v].x-11.83f)/2.88f,(points[v].z+18)/12f);
                paving.uv=uv;AssetDatabase.CreateAsset(paving,tileMesh);
            }
            var filter=deck.GetComponent<MeshFilter>(); filter.sharedMesh=paving;
            PrefabUtility.RecordPrefabInstancePropertyModifications(filter);
            Hide(area.Find("Platform_RainPools").GetComponent<Renderer>());
            Refinish(area,new Dictionary<string,string>{{"Station Terrazzo Paving","WeatheredConcrete"},{"Station Rain Darkened Concrete","WetConcrete"},{"Station Glazed Green Wainscot","WetStone"},{"Station Painted Dark Iron","CastIron"}});
            var ext=GameObject.Find("Station/Lighting/ExteriorLights").transform;
            foreach(Transform marker in ext)
            {
                if(marker.name!="Wet edge lantern") continue;
                marker.Find("Glass lens").GetComponent<Renderer>().sharedMaterial=Mat("Opal");
                var spill=marker.Find("Low amber spill").GetComponent<Light>();
                spill.transform.localPosition=new Vector3(-.32f,1.03f,-.05f);
                spill.intensity=170;spill.GetComponent<HDAdditionalLightData>().shapeRadius=.13f;
            }
            var weather=GameObject.Find("Station/Weather").transform;
            if(!weather.Find("Drip splashes"))
            {
                var fx=new GameObject("Drip splashes").AddComponent<ParticleSystem>();
                fx.transform.SetParent(weather,false);fx.transform.position=new Vector3(11.99f,.045f,0);
                fx.Stop(true,ParticleSystemStopBehavior.StopEmittingAndClear);
                var main=fx.main;main.startLifetime=new ParticleSystem.MinMaxCurve(.11f,.22f);main.startSize=new ParticleSystem.MinMaxCurve(.012f,.031f);main.startSpeed=0;main.gravityModifier=.52f;main.playOnAwake=true;
                var emission=fx.emission;emission.rateOverTime=82;
                var shape=fx.shape;shape.shapeType=ParticleSystemShapeType.Box;shape.scale=new Vector3(.13f,.01f,34);
                var v=fx.velocityOverLifetime;v.enabled=true;v.space=ParticleSystemSimulationSpace.World;
                v.x=new ParticleSystem.MinMaxCurve(-.34f,.34f);v.y=new ParticleSystem.MinMaxCurve(.48f,1.1f);v.z=new ParticleSystem.MinMaxCurve(-.35f,.35f);
                fx.GetComponent<ParticleSystemRenderer>().sharedMaterial=weather.GetComponentInChildren<ParticleSystemRenderer>().sharedMaterial;
            }
        }

        [MenuItem("Tools/Echo/M1.5/Integrate station and capture five shots")]
        public static void Run()
        {
            if(EditorApplication.isPlayingOrWillChangePlaymode) throw new InvalidOperationException("Stop play mode first");
            for(int i=0;i<SceneManager.sceneCount;i++) if(SceneManager.GetSceneAt(i).isDirty) throw new IOException("Unsaved scene "+SceneManager.GetSceneAt(i).path);
            var scene=EditorSceneManager.OpenScene(ScenePath);
            Prepare();Intake();Platform();StationLods.Apply();
            StationCharacter.Apply();
            // Fixed architecture can share a persistent shadow map. Animated people
            // and movable evidence remain in the per-frame shadow pass.
            var hall=GameObject.Find("Station/Environment/WaitingHall");
            foreach(var surface in hall.GetComponentsInChildren<MeshRenderer>(true))
            {
                if(surface.staticShadowCaster) continue;
                surface.staticShadowCaster=true;
                PrefabUtility.RecordPrefabInstancePropertyModifications(surface);
            }
            foreach(var lamp in GameObject.Find("Station/Lighting").GetComponentsInChildren<Light>())
            {
                if(lamp.name!="Warm pool" || lamp.shadows==LightShadows.None) continue;
                var hd=lamp.GetComponent<HDAdditionalLightData>();
                hd.SetShadowResolutionOverride(true);
                bool pendant=lamp.transform.parent.name=="Hall pendant";
                hd.SetShadowResolution(pendant?768:512);
                if(pendant)
                {
                    hd.shadowUpdateMode=ShadowUpdateMode.OnEnable;
                    hd.alwaysDrawDynamicShadows=true;
                }
            }
            var face=GameObject.Find("NPC face bounce").GetComponent<Light>();
            face.transform.position=new Vector3(-3.75f,2.08f,3.52f);
            face.intensity=245;
            face.GetComponent<HDAdditionalLightData>().shapeRadius=.41f;
            GameObject.Find("Character rim bounce").GetComponent<Light>().intensity=175;
            EditorSceneManager.MarkSceneDirty(scene);
            if(!EditorSceneManager.SaveScene(scene)) throw new IOException("Station save failed");
            EditorSceneManager.OpenScene(ScenePath);
            StationAudit.Run();
            var visitor=GameObject.Find("Station/Characters/StationVisitor");
            File.AppendAllText(Evidence+"Finish.log",DateTime.Now+" reloaded Station; NPC integration present="+(visitor!=null)+Environment.NewLine);
            HallIntegration.CaptureAll();
        }
    }
}


