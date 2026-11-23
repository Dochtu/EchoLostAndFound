using System;
using System.IO;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;
using UnityEngine.SceneManagement;

[InitializeOnLoad]
public static class Stage4StationSceneBuilder
{
    const string Root="Assets/_Project/";
    const string ScenePath=Root+"Scenes/Station.unity";
    const string Request="Temp/BuildStation.request";
    static Dictionary<string,Material> materials;
    static readonly Color Amber=new Color(1f,.84f,.65f);
    static readonly Color Blue=new Color(.32f,.52f,1f);

    static Stage4StationSceneBuilder() { EditorApplication.update += Poll; }

    static void Poll()
    {
        if (!File.Exists(Request) || EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isCompiling || EditorApplication.isUpdating) return;
        File.Delete(Request);
        try { Build(); }
        catch(Exception e) { Debug.LogException(e); }
    }

    static Vector3 V(float x,float y,float z) => new Vector3(x,y,z);
    static Transform Group(string name, Transform parent=null)
    {
        var t=new GameObject(name).transform;
        t.SetParent(parent,false);
        return t;
    }

    static void Folder(string path)
    {
        if (AssetDatabase.IsValidFolder(path)) return;
        int sep=path.LastIndexOf('/');
        string parent=path.Substring(0,sep);
        Folder(parent);
        AssetDatabase.CreateFolder(parent,path.Substring(sep+1));
    }

    static Transform Model(Transform parent,string name,PrimitiveType shape,Vector3 local,Vector3 size,string material)
    {
        var g=GameObject.CreatePrimitive(shape);
        g.name=name;
        g.transform.SetParent(parent,false);
        g.transform.localPosition=local;
        g.transform.localScale=size;
        g.GetComponent<Renderer>().sharedMaterial=materials[material];
        return g.transform;
    }

    static Transform Box(Transform p,string n,Vector3 pos,Vector3 size,string m) => Model(p,n,PrimitiveType.Cube,pos,size,m);
    static Transform Round(Transform p,string n,Vector3 pos,Vector3 size,string m) => Model(p,n,PrimitiveType.Cylinder,pos,new Vector3(size.x,size.y*.5f,size.z),m);

    static void Prefab(Transform t,string path)
    {
        Folder(Path.GetDirectoryName(Root+path).Replace('\\','/'));
        var result=PrefabUtility.SaveAsPrefabAssetAndConnect(t.gameObject,Root+path,InteractionMode.AutomatedAction);
        if (!result) throw new IOException("Could not save prefab: "+path);
    }

    [MenuItem("Tools/Echo/Build Station")]
    public static void Build()
    {
        for (int i=0;i<SceneManager.sceneCount;i++)
            if(SceneManager.GetSceneAt(i).isDirty) throw new InvalidOperationException("Save the open scene before building Station.");
        var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        materials=Stage4StationArt.Materials();
        var root=Group("Station");
        var env=Group("Environment",root);
        var lost=Group("LostAndFound",env);
        var hall=Group("WaitingHall",env);
        var platform=Group("Platform",env);
        Stage4Architecture.Build(lost,hall,platform,materials);
        Sign(lost,"Office",V(-12.03f,2.78f,-4.5f),-90,2.15f);
        Sign(hall,"Hall",V(0,3.9f,9.65f),0,2.4f);
        Sign(hall,"West",V(-5.65f,2.63f,5.2f),-90,1.63f);
        Sign(hall,"Platform",V(5.80f,3.08f,1),90,1.9f);
        Sign(platform,"Platform",V(9,2.95f,3.5f),0,1.8f);
        Sign(platform,"Cabinet",V(7.56f,1.43f,6.1f),-90,.48f);

        Furnish(lost);
        Prefab(lost,"Prefabs/Environment/LostAndFound.prefab");
        Prefab(hall,"Prefabs/Environment/WaitingHall.prefab");
        Prefab(platform,"Prefabs/Environment/Platform.prefab");

        var characters=Group("Characters",root);
        var npc=Stage4StationArt.Npc().transform;
        npc.name="NPC_VisualSample";
        Prefab(npc,"Prefabs/NPCs/NPC_VisualSample.prefab");
        npc.SetParent(characters,false); npc.localPosition=V(-4.8f,0,4.6f);
        var watch=Stage4StationArt.PocketWatch().transform;
        watch.name="PocketWatch";
        Prefab(watch,"Prefabs/Interactables/PocketWatch.prefab");
        watch.SetParent(Group("Props",root),false); watch.localPosition=V(-9.83f,1.04416f,-4.45f);
        var lighting=Group("Lighting",root);
        Atmosphere(lighting);
        Illuminate(lighting);
        Weather(Group("Weather",root));
        var cams=Group("Cameras",root);
        var anchors=Group("ShotAnchors",cams);
        var main=Shot(anchors,"Station_MainHall",V(2.1f,1.67f,-8.65f),V(-1.2f,2.18f,5.1f),60);
        Shot(anchors,"Station_LostFound",V(-7.70f,1.61f,-3.05f),V(-10.45f,1.32f,-4.75f),56);
        Shot(anchors,"Station_Watch",V(-9.815f,1.149f,-4.502f),watch.position+V(.009f,.002f,-.001f),42);
        Shot(anchors,"Station_NPC",V(-4.32f,1.21f,2.08f),V(-4.8f,.98f,4.6f),48);
        Shot(anchors,"Station_Platform",V(11.51f,1.34f,-14.8f),V(11.98f,1.20f,4.3f),65);
        var camera=Group("StationPreviewCamera",cams);
        camera.tag="MainCamera";
        camera.SetPositionAndRotation(main.position,main.rotation);
        camera.gameObject.AddComponent<Camera>().fieldOfView=60;
        camera.gameObject.AddComponent<HDAdditionalCameraData>();
        camera.gameObject.AddComponent<AudioListener>();
        Group("SceneSystems",root);
        AssetDatabase.SaveAssets();
        if (!EditorSceneManager.SaveScene(scene,ScenePath)) throw new IOException(ScenePath);
        var scenes=new List<EditorBuildSettingsScene>(EditorBuildSettings.scenes);
        scenes.RemoveAll(s=>s.path==ScenePath);
        scenes.Insert(0,new EditorBuildSettingsScene(ScenePath,true));
        EditorBuildSettings.scenes=scenes.ToArray();
        EditorSceneManager.OpenScene(ScenePath);
        SceneView.lastActiveSceneView?.LookAt(V(0,1.3f,0),Quaternion.Euler(20,24,0),16);
        Debug.Log("Station built, saved and reopened.");
    }

    static Transform Shot(Transform p,string name,Vector3 at,Vector3 subject,float fov)
    {
        var t=Group(name,p); t.position=at; t.LookAt(subject);
        var cam=t.gameObject.AddComponent<Camera>(); cam.enabled=false; cam.fieldOfView=fov; cam.nearClipPlane=.008f;
        return t;
    }

    static Material PrintMaterial(string key)
    {
        string dir=Root+"Art/Materials/StationSigns"; Folder(dir);
        string path=dir+"/"+key+".mat";
        var mat=AssetDatabase.LoadAssetAtPath<Material>(path);
        if (!mat)
        {
            var texture=AssetDatabase.LoadAssetAtPath<Texture2D>(Root+"Art/Textures/StationSigns/"+key+".png");
            if (!texture) throw new FileNotFoundException(key);
            mat=new Material(Shader.Find("HDRP/Lit"));
            mat.SetTexture("_BaseColorMap",texture);
            mat.SetFloat("_Smoothness",.32f);
            HDMaterial.ValidateMaterial(mat);
            AssetDatabase.CreateAsset(mat,path);
        }
        return mat;
    }

    static Transform Sign(Transform p,string key,Vector3 pos,float yaw,float width)
    {
        var sign=Group(key+" enamel plate",p);
        sign.localPosition=pos; sign.localRotation=Quaternion.Euler(0,yaw,0);
        Box(sign,"Folded lip",V(0,0,.016f),V(width+.026f,width*.3125f+.026f,.032f),"brass");
        var face=Model(sign,"Lettering",PrimitiveType.Quad,V(0,0,-.008f),V(width,width*.3125f,1),"paper");
        face.GetComponent<Renderer>().sharedMaterial=PrintMaterial(key);
        return sign;
    }

    static void Furnish(Transform lost)
    {
        var counter=Group("Counter",lost);
        Box(counter,"Paneled cabinet",V(0,.47f,0),V(1.09f,.91f,3.54f),"wood");
        Box(counter,"Stone kick",V(0,.08f,0),V(1.12f,.12f,3.58f),"iron");
        Box(counter,"Bullnose writing top",V(0,.95f,0),V(1.25f,.10f,3.74f),"wood");
        Box(counter,"Brass edge",V(.627f,.93f,0),V(.008f,.018f,3.7f),"brass");
        for(int i=-2;i<=2;i++)
        {
            Box(counter,"Panel stile",V(.55f,.50f,i*.82f),V(.045f,.76f,.045f),"brass");
            if(i<2) Box(counter,"Raised panel",V(.552f,.5f,(i+.5f)*.82f),V(.023f,.64f,.68f),"wood");
        }
        Box(counter,"Watch felt",V(.17f,1.019f,.05f),V(.34f,.036f,.26f),"cloth");
        var bag=Group("A-0641 LostItemBag",counter);
        bag.localPosition=V(-.10f,1f,-.69f);
        Model(bag,"Cloth holdall",PrimitiveType.Sphere,V(0,.15f,0),V(.57f,.38f,.75f),"bag");
        for(int i=-1;i<=1;i+=2)
            Model(bag,"Leather strap",PrimitiveType.Sphere,V(0,.157f,i*.19f),V(.58f,.392f,.06f),"iron");
        var tag=Sign(bag,"Bag",V(.303f,.20f,.00f),-90,.38f);
        tag.localRotation*=Quaternion.Euler(0,0,-8);
        for(int i=0;i<3;i++)
        {
            var book=Group("Ledger binding",counter);
            book.localPosition=V(.14f,1.012f+i*.055f,.81f);
            book.localRotation=Quaternion.Euler(0,7*i,0);
            Box(book,"Cloth cover",V(0,0,0),V(.39f,.023f,.53f),"cloth");
            Box(book,"Page block",V(0,.025f,0),V(.38f,.032f,.52f),"paper");
            var label=Sign(book,"Ledger",V(0,.047f,0),0,.30f);
            label.localRotation=Quaternion.Euler(90,90,0);
        }
        var lamp=Group("Banker desk lamp",counter); lamp.localPosition=V(-.28f,1, .29f);
        Round(lamp,"Cast foot",V(0,.021f,0),V(.25f,.042f,.19f),"iron");
        Round(lamp,"Brass stem",V(0,.24f,0),V(.029f,.43f,.029f),"brass");
        var shade=Model(lamp,"Enamel shade",PrimitiveType.Sphere,V(.07f,.45f,0),V(.27f,.16f,.37f),"iron");
        shade.localRotation=Quaternion.Euler(0,0,-19);
        Model(lamp,"Opal diffuser",PrimitiveType.Sphere,V(.094f,.375f,0),V(.23f,.055f,.32f),"lamp");
        Prefab(counter,"Prefabs/Environment/Counter.prefab");
        counter.localPosition=V(-10,0,-4.5f);
        var storage=Group("Shelves and pigeonholes",lost);
        storage.localPosition=V(-12.50f,0,-4.65f);
        for(int i=0;i<4;i++)
        {
            float y=.28f+i*.52f;
            Box(storage,"Shelf",V(0,y,0),V(.75f,.048f,4.6f),"wood");
            for(int j=0;j<9;j++)
            {
                if((i+2*j)%5==0) continue;
                float z=-1.97f+j*.47f;
                Box(storage,"Bound archive",V(0,y+.18f,z),V(.50f,.31f,.36f),"cloth");
                Box(storage,"Paper slip",V(.255f,y+.20f,z),V(.008f,.078f,.17f),"paper");
            }
        }
        for(int j=0;j<4;j++)
            Box(storage,"Upright",V(0,1.24f,-2.28f+j*1.52f),V(.72f,2.5f,.055f),"iron");
        for(int i=0;i<3;i++)
        {
            float z=-1.28f+i*.40f;
            Box(lost,"Locker door",V(-12.1f,1.02f,z),V(.6f,2.02f,.38f),"iron");
            for(int j=0;j<4;j++) Box(lost,"Vent",V(-11.795f,1.77f+j*.037f,z),V(.01f,.012f,.23f),"brass");
            Box(lost,"Handle",V(-11.77f,.94f,z+.10f),V(.05f,.13f,.018f),"brass");
        }
    }

    static T Override<T>(VolumeProfile profile) where T: VolumeComponent
    {
        if (profile.TryGet<T>(out var component)) return component;
        component=profile.Add<T>();
        AssetDatabase.AddObjectToAsset(component,profile);
        return component;
    }

    static void Atmosphere(Transform lights)
    {
        Folder(Root+"Settings");
        string path=Root+"Settings/StationNight.asset";
        var profile=AssetDatabase.LoadAssetAtPath<VolumeProfile>(path);
        if (!profile)
        {
            profile=ScriptableObject.CreateInstance<VolumeProfile>();
            AssetDatabase.CreateAsset(profile,path);
        }
        var exposure=Override<Exposure>(profile);
        exposure.mode.Override(ExposureMode.Fixed); exposure.fixedExposure.Override(4.95f);
        Override<Tonemapping>(profile).mode.Override(TonemappingMode.ACES);
        Override<WhiteBalance>(profile).temperature.Override(-4);
        Override<ColorAdjustments>(profile).contrast.Override(6);
        Override<VisualEnvironment>(profile).skyType.Override((int)SkyType.Gradient);
        var sky=Override<GradientSky>(profile);
        sky.top.Override(new Color(.035f,.084f,.21f)); sky.middle.Override(new Color(.085f,.20f,.40f));
        sky.bottom.Override(new Color(.025f,.035f,.07f));
        sky.skyIntensityMode.Override(SkyIntensityMode.Multiplier); sky.multiplier.Override(18);
        var fog=Override<Fog>(profile);
        fog.enabled.Override(true); fog.meanFreePath.Override(62); fog.maximumHeight.Override(19);
        fog.enableVolumetricFog.Override(true); fog.colorMode.Override(FogColorMode.SkyColor);
        foreach(var effect in profile.components) EditorUtility.SetDirty(effect);
        EditorUtility.SetDirty(profile);
        var volume=Group("GlobalVolume",lights).gameObject.AddComponent<Volume>();
        volume.isGlobal=true; volume.priority=10; volume.sharedProfile=profile;
        var probes=Group("ReflectionProbes",lights);
        Probe(probes,"Canopy reflections",V(12,1.6f,0),V(18,8,40));
        Probe(probes,"Office reflections",V(-9.9f,1.5f,-4.5f),V(7,4,8));
        Probe(probes,"Hall reflections",V(0,2,0),V(12,6,20));
    }

    static void Probe(Transform p,string name,Vector3 at,Vector3 size)
    {
        var t=Group(name,p); t.position=at;
        t.gameObject.AddComponent<ReflectionProbe>();
        var hd=t.GetComponent<HDAdditionalReflectionData>();
        if (!hd) hd=t.gameObject.AddComponent<HDAdditionalReflectionData>();
        hd.mode=ProbeSettings.Mode.Realtime; hd.realtimeMode=ProbeSettings.RealtimeMode.OnEnable;
        hd.influenceVolume.boxSize=size;
    }

    static Light LightAt(Transform p,string name,Vector3 at,LightType type,Color color,float power,float range,bool shadow)
    {
        var obj=Group(name,p); obj.position=at;
        var light=obj.gameObject.AddComponent<Light>();
        light.type=type;
        if(!obj.TryGetComponent<HDAdditionalLightData>(out _)) obj.gameObject.AddComponent<HDAdditionalLightData>();
        light.color=color; light.intensity=power; light.range=range;
        light.shadows=shadow ? LightShadows.Soft : LightShadows.None;
        return light;
    }

    static void Pendant(Transform parent,string name,Vector3 at,float ceiling,float power)
    {
        var lamp=Group(name,parent); lamp.position=at;
        float drop=Mathf.Max(.08f,ceiling-at.y);
        Round(lamp,"Suspension",V(0,drop/2,0),V(.025f,drop,.025f),"iron");
        Round(lamp,"Collar",V(0,.1f,0),V(.12f,.2f,.12f),"brass");
        Model(lamp,"Pressed steel dome",PrimitiveType.Sphere,V(0,0,0),V(.65f,.22f,.65f),"iron");
        Model(lamp,"Opaline bowl",PrimitiveType.Sphere,V(0,-.081f,0),V(.54f,.16f,.54f),"lamp");
        LightAt(lamp,"Warm pool",at+V(0,-.22f,0),LightType.Point,Amber,power,11,true);
    }

    static void Illuminate(Transform p)
    {
        var inside=Group("InteriorLights",p); var outside=Group("ExteriorLights",p);
        var moon=LightAt(outside,"Moon",V(0,12,0),LightType.Directional,Blue,22,100,true);
        moon.transform.rotation=Quaternion.Euler(39,-62,0);
        for(int i=-1;i<=1;i++)
        {
            Pendant(inside,"Hall pendant",V(0,3.86f,i*6f),5.75f,1250);
            for(int side=-1;side<=1;side+=2)
                LightAt(inside,"Window bounce",V(side*4.3f,2.25f,i*6f),LightType.Point,new Color(.71f,.81f,1),320,7,false);
        }
        Pendant(inside,"Intake pendant",V(-10.4f,2.80f,-5.6f),3.60f,520);
        Pendant(inside,"Archive pendant",V(-10.5f,2.80f,-1.75f),3.60f,450);
        var desk=LightAt(inside,"Desk lamp task light",V(-10.17f,1.36f,-4.21f),LightType.Spot,Amber,55,2,true);
        desk.spotAngle=93; desk.transform.LookAt(V(-9.85f,1,-4.54f));
        LightAt(inside,"NPC face bounce",V(-4.1f,1.88f,3.37f),LightType.Point,new Color(.96f,.95f,.94f),605,4,false);
        LightAt(inside,"Counter indirect daylight",V(-8.22f,2.18f,-3.50f),LightType.Point,new Color(.89f,.94f,1),670,6,false);
        LightAt(inside,"Character rim bounce",V(-5.65f,2.2f,5.41f),LightType.Point,new Color(.71f,.81f,1),300,3,false);
        for(int i=-2;i<=2;i++) Pendant(outside,"Platform lantern",V(10.75f,3.05f,6.4f*i),3.92f,1200);
        for(int i=-2;i<=2;i++)
        {
            var marker=Group("Wet edge lantern",outside);
            marker.position=V(14.025f,0,6.1f*i+.6f);
            Round(marker,"Foot",V(0,.045f,0),V(.18f,.09f,.18f),"iron");
            Round(marker,"Post",V(0,.56f,0),V(.093f,1.05f,.093f),"iron");
            Round(marker,"Glass lens",V(0,1.08f,0),V(.14f,.19f,.14f),"lamp");
            Round(marker,"Hood",V(0,1.201f,0),V(.19f,.055f,.19f),"brass");
            LightAt(marker,"Low amber spill",marker.position+V(-.16f,1.03f,-.08f),LightType.Point,new Color(1,.76f,.50f),285,6,false);
        }
    }

    static void Weather(Transform weather)
    {
        string dir=Root+"VFX/Rain"; Folder(dir);
        string path=dir+"/RainStreak.mat";
        var rainMat=AssetDatabase.LoadAssetAtPath<Material>(path);
        if (!rainMat)
        {
            rainMat=new Material(Shader.Find("HDRP/Unlit"));
            AssetDatabase.CreateAsset(rainMat,path);
        }
        rainMat.SetFloat("_SurfaceType",1); rainMat.SetFloat("_BlendMode",0);
        rainMat.SetTexture("_UnlitColorMap",AssetDatabase.LoadAssetAtPath<Texture2D>(dir+"/DropFalloff.png"));
        rainMat.SetColor("_UnlitColor",new Color(.82f,.85f,.9f,.72f));
        rainMat.SetColor("_EmissiveColor",new Color(.70f,.82f,1.00f));
        HDMaterial.ValidateMaterial(rainMat); EditorUtility.SetDirty(rainMat);
        Rain(weather,"OpenPlatformRain",V(16.1f,7.2f,0),V(8,.03f,36),3200,9,.031f,.21f,rainMat);
        Rain(weather,"RoofDrips",V(11.98f,3.35f,0),V(.09f,.01f,34),100,5.8f,.021f,.12f,rainMat);
        Prefab(weather,"VFX/Rain/StationRain.prefab");
    }

    static void Rain(Transform p,string name,Vector3 at,Vector3 footprint,float rate,float speed,float width,float length,Material mat)
    {
        var t=Group(name,p); t.position=at;
        var ps=t.gameObject.AddComponent<ParticleSystem>(); ps.Stop(true,ParticleSystemStopBehavior.StopEmittingAndClear);
        var main=ps.main; main.loop=true; main.prewarm=true; main.startSpeed=0; main.startLifetime=at.y/speed;
        main.simulationSpace=ParticleSystemSimulationSpace.World; main.maxParticles=5000; main.startSize3D=true;
        main.startSizeX=new ParticleSystem.MinMaxCurve(width*.40f,width); main.startSizeY=new ParticleSystem.MinMaxCurve(length*.68f,length);
        main.startSizeZ=width; main.startRotation=new ParticleSystem.MinMaxCurve(-.095f,-.026f);
        var emission=ps.emission; emission.rateOverTime=rate;
        var shape=ps.shape; shape.shapeType=ParticleSystemShapeType.Box; shape.scale=footprint;
        var velocity=ps.velocityOverLifetime; velocity.enabled=true; velocity.space=ParticleSystemSimulationSpace.World;
        velocity.x=.12f; velocity.y=-speed; velocity.z=.17f;
        var r=ps.GetComponent<ParticleSystemRenderer>(); r.renderMode=ParticleSystemRenderMode.VerticalBillboard;
        r.sharedMaterial=mat; r.shadowCastingMode=ShadowCastingMode.Off; r.receiveShadows=false;
    }
}






