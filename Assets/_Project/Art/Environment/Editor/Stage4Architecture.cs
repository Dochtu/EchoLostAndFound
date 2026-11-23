using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

// World-space modular architectural meshwork. Each module is a persistent mesh with
// material submeshes. Object origins correspond to the station's floor datum.
public static class Stage4Architecture
{
    const string Folder = "Assets/_Project/Art/Environment/StationMeshes";
    static Vector3 P(float x, float y, float z) => new Vector3(x,y,z);
    static readonly Vector3 X = Vector3.right, Y = Vector3.up, Z = Vector3.forward;

    sealed class Module
    {
        readonly string name;
        readonly List<Vector3> vertices = new List<Vector3>();
        readonly List<Vector2> uv = new List<Vector2>();
        readonly Dictionary<string,List<int>> faces = new Dictionary<string,List<int>>();
        public Module(string name) { this.name = name; }

        public void Quad(string mat, Vector3 a, Vector3 b, Vector3 c, Vector3 d)
        {
            if (!faces.TryGetValue(mat, out var tris)) faces.Add(mat, tris = new List<int>());
            int n = vertices.Count;
            vertices.Add(a); vertices.Add(b); vertices.Add(c); vertices.Add(d);
            float u = Vector3.Distance(a,b), v = Vector3.Distance(b,c);
            uv.Add(Vector2.zero); uv.Add(new Vector2(u,0)); uv.Add(new Vector2(u,v)); uv.Add(new Vector2(0,v));
            tris.Add(n); tris.Add(n+1); tris.Add(n+2); tris.Add(n); tris.Add(n+2); tris.Add(n+3);
        }
        void Face(string m, Vector3 center, Vector3 u, Vector3 v)
        {
            Quad(m,center-u-v,center+u-v,center+u+v,center-u+v);
        }
        public void Box(string m,float x,float y,float z,float w,float h,float d)
        {
            Block(m,P(x,y,z),X*w/2,Y*h/2,Z*d/2);
        }
        void Block(string m, Vector3 p, Vector3 x,Vector3 y,Vector3 z)
        {
            Face(m,p+x,y,z); Face(m,p-x,z,y);
            Face(m,p+y,z,x); Face(m,p-y,x,z);
            Face(m,p+z,x,y); Face(m,p-z,y,x);
        }
        public void Beam(string m,Vector3 a,Vector3 b,float width,float depth)
        {
            var axis = (b-a).normalized;
            var refAxis = Mathf.Abs(Vector3.Dot(axis,Z))>.95f ? X : Z;
            var right=Vector3.Cross(axis,refAxis).normalized;
            Block(m,(a+b)/2,right*width/2,(b-a)/2,Vector3.Cross(right,axis)*depth/2);
        }
        public void Column(string m, float x,float z,float y1,float y2,float r1,float r2,int sides=16)
        {
            for(int i=0;i<sides;i++)
            {
                float a=i*2*Mathf.PI/sides, b=(i+1)*2*Mathf.PI/sides;
                var p=P(Mathf.Cos(a),0,Mathf.Sin(a)); var q=P(Mathf.Cos(b),0,Mathf.Sin(b));
                var low=P(x,y1,z); var high=P(x,y2,z);
                Quad(m,low+r1*q,low+r1*p,high+r2*p,high+r2*q);
                Quad(m,high,high+r2*q,high+r2*p,high);
            }
        }
        public void Save(Transform parent, Dictionary<string,Material> palette)
        {
            var path=Folder+"/"+name+".asset";
            var mesh=AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if(!mesh){mesh=new Mesh(); AssetDatabase.CreateAsset(mesh,path);}
            mesh.Clear(); mesh.name=name;
            mesh.indexFormat=vertices.Count>65535 ? IndexFormat.UInt32 : IndexFormat.UInt16;
            mesh.SetVertices(vertices); mesh.SetUVs(0,uv); mesh.subMeshCount=faces.Count;
            var mats=new List<Material>(); int n=0;
            foreach(var pair in faces){mats.Add(palette[pair.Key]);mesh.SetTriangles(pair.Value,n++);}
            mesh.RecalculateNormals(); mesh.RecalculateTangents(); mesh.RecalculateBounds();
            EditorUtility.SetDirty(mesh);
            var obj=new GameObject(name); obj.transform.SetParent(parent,false);
            obj.AddComponent<MeshFilter>().sharedMesh=mesh;
            obj.AddComponent<MeshRenderer>().sharedMaterials=mats.ToArray();
            // Glass, trim and railway furniture have no bearing on walkable bounds.
        }
    }

    public static void Build(Transform lost, Transform hall, Transform platform, Dictionary<string,Material> mats)
    {
        if(!AssetDatabase.IsValidFolder(Folder))
            AssetDatabase.CreateFolder("Assets/_Project/Art/Environment","StationMeshes");
        Hall(hall,mats); Office(lost,mats); Platform(platform,mats);
    }

    static void Hall(Transform parent,Dictionary<string,Material> mats)
    {
        var floor=new Module("Hall_Terrazzo");
        floor.Box("iron",0,-.15f,0,12.4f,.26f,20.4f);
        for(int i=0;i<12;i++)
            for(int j=0;j<20;j++)
                floor.Box("concrete",i-5.5f,-.012f,j-9.5f,.993f,.023f,.993f);
        foreach(float x in new[]{-5.15f,-5.04f,5.04f,5.15f})
            floor.Box("brass",x,.002f,0,.026f,.006f,19.95f);
        floor.Save(parent,mats);

        var hall=new Module("Hall_MasonryAndCasements");
        // Openings are cut into each envelope segment, including both inter-zone doors.
        for(int side=-1;side<=1;side+=2)
        {
            float x=side*6;
            for(int bay=0;bay<5;bay++)
            {
                float z=-7+4*bay-0.05f;
                // Bay centres -7,-3,1,5,9; first bay starts at -9 and last ends at 11.
                float lo=Mathf.Max(-10,z-2), hi=Mathf.Min(10,z+2);
                if(bay==0)lo=-10;
                bool door=(side==-1&&bay==1)||(side==1&&bay==2);
                bool desk=side==-1&&bay==3;
                float cz=desk?5.2f:Mathf.Clamp(z,lo+1,hi-1);
                float half=Mathf.Min(door?1.34f:1.21f,Mathf.Min(cz-lo,hi-cz)-.14f);
                float sill=door?0:desk?1.03f:1.22f, top=door?3.18f:2.95f;
                WallX(hall,x,lo,cz-half,0,5.8f); WallX(hall,x,cz+half,hi,0,5.8f);
                WallX(hall,x,cz-half,cz+half,top,5.8f);
                if(sill>0) WallX(hall,x,cz-half,cz+half,0,sill);
                foreach(float edge in new[]{cz-half,cz+half})
                    hall.Box("iron",x,(sill+top)/2,edge,.28f,top-sill,.085f);
                hall.Box("iron",x,top,cz,.29f,.13f,2*half+.15f);
                if(!door)
                {
                    hall.Box("wood",x,sill,cz,desk?.75f:.36f,.11f,2*half+.24f);
                    hall.Box("iron",x,2.5f,cz,.15f,.054f,half*2);
                    for(int k=-1;k<=1;k++)hall.Box("iron",x,(sill+top)/2,cz+k*half/2,.065f,top-sill,.038f);
                    if(!desk)hall.Box("glass",x+.055f*side,(sill+top)/2,cz,.015f,top-sill,2*half);
                    if(desk)hall.Box("darkWood",x-.13f*side,.65f,cz,.09f,.66f,2*half);
                }
                for(int edge=0;edge<2;edge++)
                {
                    float a=edge==0?lo:cz+half,b=edge==0?cz-half:hi;
                    if(b>a)hall.Box("darkWood",x-side*.13f,.58f,(a+b)/2,.08f,1.14f,b-a);
                    if(b>a)hall.Box("wood",x-side*.17f,1.14f,(a+b)/2,.11f,.065f,b-a);
                }
            }
        }
        foreach(float z in new[]{-10f,10f})
        {
            hall.Box("plaster",0,1.4f,z,12.2f,2.8f,.25f);
            hall.Box("plaster",0,5.21f,z,12.2f,1.22f,.25f);
            for(int i=-3;i<=3;i++)
                hall.Box("iron",i*1.94f,3.7f,z,.13f,1.8f,.29f);
            hall.Box("glass",0,3.7f,z,11.85f,1.8f,.022f);
            hall.Box("iron",0,3.7f,z,12,.06f,.18f);
            hall.Box("stoneTrim",0,2.79f,z,12,.13f,.37f);
            float face=z-Mathf.Sign(z)*.17f;
            hall.Box("stoneTrim",0,.63f,face,11.82f,1.26f,.13f);
            hall.Box("wood",0,1.24f,face,11.88f,.11f,.21f);
            for(int i=-5;i<=5;i++)
            {
                hall.Box("wood",i,.63f,face-Mathf.Sign(z)*.07f,.052f,1.12f,.055f);
                hall.Box("iron",i,2.16f,face,.017f,.94f,.018f);
            }
            // A glazed pair of exterior doors terminates the hall's long axis.
            for(int side=-1;side<=1;side+=2)
            {
                float x=side*.61f, doorFace=face-Mathf.Sign(z)*.16f;
                hall.Box("darkWood",x,1.29f,doorFace,1.19f,2.57f,.095f);
                hall.Box("glass",x,1.84f,doorFace-Mathf.Sign(z)*.054f,.93f,1.02f,.014f);
                for(int k=-1;k<=1;k++)
                    hall.Box("wood",x+.4f*k,1.84f,doorFace-Mathf.Sign(z)*.068f,.032f,1.05f,.034f);
                hall.Box("wood",x,1.78f,doorFace-Mathf.Sign(z)*.069f,.97f,.04f,.037f);
                hall.Box("brass",side*.17f,1.02f,doorFace-Mathf.Sign(z)*.098f,.037f,.27f,.054f);
            }
        }
        hall.Save(parent,mats);
        var roof=new Module("Hall_BarrelVaultAndRibs");
        const int segments=24;
        for(int i=0;i<segments;i++)
        {
            var a=Arch(i,segments,0);var b=Arch(i+1,segments,0);
            roof.Quad("plaster",a-Z*10.35f,b-Z*10.35f,b+Z*10.35f,a+Z*10.35f);
            roof.Quad("iron",a+Z*10.35f,b+Z*10.35f,b-Z*10.35f,a-Z*10.35f);
            foreach(float end in new[]{-10f,10f})
            {
                var pa=a+Z*end;var pb=b+Z*end;
                roof.Quad("glass",pa,pb,P(pb.x,5.75f,end),P(pa.x,5.75f,end));
                if(i%3==1)roof.Beam("iron",P(pa.x,5.74f,end),pa,.055f,.1f);
            }
            foreach(float z in new[]{-9.6f,-6f,-2f,2f,6f,9.6f})
                roof.Beam("iron",a+Z*z-.08f*Y,b+Z*z-.08f*Y,.15f,.16f);
        }
        foreach(float z in new[]{-9.6f,-6f,-2f,2f,6f,9.6f})
        {
            foreach(float x in new[]{-5.48f,5.48f})
            {
                roof.Box("stoneTrim",x,.14f,z,.72f,.28f,.72f);
                roof.Column("iron",x,z,.28f,.52f,.35f,.237f);
                roof.Column("iron",x,z,.52f,5.02f,.225f,.19f);
                roof.Column("brass",x,z,.54f,.59f,.24f,.24f);
                roof.Column("iron",x,z,5.02f,5.34f,.19f,.38f);
                roof.Beam("iron",P(x,4.75f,z),P(x*.68f,5.72f,z),.095f,.10f);
            }
            roof.Box("iron",0,5.72f,z,11.5f,.14f,.16f);
            for(int n=-2;n<=2;n++)
                roof.Beam("iron",P(n*2,5.72f,z),P(n*2+.94f,6.66f-Mathf.Abs(n)*.15f,z),.067f,.085f);
        }
        roof.Save(parent,mats);
        var seats=new Module("Hall_SlattedSettees");
        foreach(float x in new[]{-3.05f,3.05f})
            foreach(float z in new[]{-6.8f,-.4f,6.5f}) Bench(seats,x,z,x>0?1:-1);
        seats.Save(parent,mats);
    }
    static Vector3 Arch(int i,int total,float z)
    {
        float t=Mathf.PI*i/total;
        return P(-6.2f*Mathf.Cos(t),5.76f+1.65f*Mathf.Sin(t),z);
    }
    static void WallX(Module m,float x,float a,float b,float low,float top)
    {
        if(b>a&&top>low)m.Box("plaster",x,(low+top)/2,(a+b)/2,.235f,top-low,b-a);
    }
    static void Bench(Module m,float x,float z,int side)
    {
        for(int k=0;k<5;k++)m.Box("wood",x+(k-2)*.112f,.47f,z,.103f,.074f,2.83f);
        for(int k=0;k<3;k++)m.Box("wood",x+side*(.26f+k*.028f),.67f+k*.14f,z,.078f,.118f,2.83f);
        foreach(float dz in new[]{-1.11f,1.11f})
        {
            foreach(int s in new[]{-1,1})
                m.Beam("iron",P(x+s*.31f,.045f,z+dz),P(x+s*.18f,.44f,z+dz),.075f,.095f);
            m.Box("iron",x,.42f,z+dz,.61f,.085f,.085f);
            m.Beam("iron",P(x+side*.23f,.42f,z+dz),P(x+side*.36f,1.01f,z+dz),.06f,.075f);
            m.Box("iron",x,.69f,z+dz,.48f,.05f,.06f);
        }
    }
    static void Office(Transform parent, Dictionary<string,Material> mats)
    {
        var m=new Module("Office_PanelledShell");
        m.Box("darkWood",-9.55f,-.11f,-4,6.95f,.21f,8);
        for(int i=0;i<31;i++)
            m.Box("wood",-12.84f+i*.222f,-.012f,-4,.218f,.023f,7.97f);
        m.Box("plaster",-13,1.84f,-4,.19f,3.68f,8.2f);
        m.Box("plaster",-9.5f,1.84f,-8,7.2f,3.68f,.19f);
        m.Box("plaster",-9.5f,.62f,0,7.2f,1.24f,.19f);
        m.Box("plaster",-9.5f,3.31f,0,7.2f,.75f,.19f);
        for(int i=0;i<6;i++)m.Box("wood",-12.8f+1.28f*i,2.1f,0,.11f,1.78f,.23f);
        m.Box("glass",-9.5f,2.1f,0,6.92f,1.75f,.02f);
        m.Box("wood",-9.5f,2.43f,0,7.05f,.08f,.22f);
        m.Box("wood",-9.5f,1.24f,0,7.08f,.085f,.34f);
        // Enamelled cable trunking and a small wall vent below the ceiling.
        m.Box("iron",-9.45f,3.05f,-7.84f,6.9f,.039f,.04f);
        m.Box("iron",-11.85f,2.77f,-7.84f,.80f,.48f,.086f);
        for(int i=0;i<8;i++)m.Box("stoneTrim",-11.85f,2.56f+i*.056f,-7.78f,.73f,.025f,.045f);
        m.Box("plaster",-9.5f,3.71f,-4,7.35f,.18f,8.32f);
        for(int i=0;i<6;i++)
            m.Box("darkWood",-9.5f,3.57f,-7.75f+i*1.5f,7.04f,.17f,.16f);
        foreach(float z in new[]{-7.86f,-.15f})
        {
            m.Box("darkWood",-9.52f,.55f,z,6.86f,1.10f,.08f);
            m.Box("wood",-9.52f,1.1f,z,6.9f,.064f,.14f);
            for(int i=0;i<10;i++)m.Box("wood",-12.72f+i*.714f,.56f,z+.05f*(z<-1?1:-1),.046f,1,.042f);
        }
        m.Save(parent,mats);
    }
    static void Platform(Transform parent,Dictionary<string,Material> mats)
    {
        var deck=new Module("Platform_CopingAndDrains");
        deck.Box("stoneTrim",10.48f,-.44f,0,9.05f,.84f,36.3f);
        for(int i=0;i<18;i++)
        {
            float z=-17+i*2;
            deck.Box("concrete",8.91f,-.027f,z,5.82f,.053f,1.991f);
            deck.Box("wet",13.27f,-.027f,z,2.88f,.053f,1.991f);
            deck.Box("stoneTrim",14.86f,-.04f,z,.285f,.10f,1.989f);
            deck.Box("brass",14.33f,.004f,z,.13f,.008f,1.99f);
            deck.Box("iron",11.82f,.001f,z,.147f,.012f,1.98f);
            for(int j=0;j<15;j++) deck.Box("stoneTrim",11.82f,.009f,z-.90f+j*.13f,.125f,.009f,.032f);
        }
        deck.Save(parent,mats);
        var pools=new Module("Platform_RainPools");
        for(int i=0;i<14;i++)
        {
            float rx=.26f+.17f*(i%4),rz=.47f+.26f*(i%5);
            var center=P(12.36f+.82f*Mathf.Abs(Mathf.Sin(i*1.7f)),.008f,-16.4f+2.52f*i);
            Vector3 Rim(int j)
            {
                float a=j*2*Mathf.PI/40;
                float radius=.82f+.10f*Mathf.Sin(3*a+i)+.08f*Mathf.Sin(5*a+.8f*i);
                return center+P(rx*Mathf.Cos(a),0,rz*Mathf.Sin(a))*radius;
            }
            for(int j=0;j<40;j++)pools.Quad("puddle",center,Rim(j+1),Rim(j),center);
        }
        pools.Save(parent,mats);
        var iron=new Module("Platform_CantileverCanopy");
        for(int i=0;i<7;i++)
        {
            float z=-15+5*i, x=8.13f;
            iron.Box("stoneTrim",x,.16f,z,.62f,.32f,.62f);
            iron.Column("iron",x,z,.32f,.58f,.27f,.185f);
            iron.Column("iron",x,z,.58f,3.65f,.178f,.145f);
            iron.Column("brass",x,z,.6f,.65f,.195f,.195f);
            iron.Column("iron",x,z,3.65f,4,.15f,.28f);
            iron.Beam("iron",P(x,3.02f,z),P(10.32f,4.04f,z),.115f,.105f);
            iron.Beam("iron",P(x,3.17f,z),P(6.36f,4.2f,z),.10f,.105f);
            iron.Beam("iron",P(5.93f,4.28f,z),P(11.82f,3.88f,z),.13f,.21f);
        }
        for(int i=0;i<30;i++)
        {
            float x=5.98f+i*.199f;
            iron.Box("iron",x,4.36f-i*.0134f,0,.21f,.062f,35.3f);
            iron.Box("stoneTrim",x+.095f,4.40f-i*.0134f,0,.026f,.047f,35.3f);
        }
        iron.Box("iron",11.85f,3.94f,0,.19f,.24f,35.5f);
        iron.Box("brass",11.94f,3.91f,0,.035f,.065f,35.48f);
        for(int i=0;i<19;i++)
        {
            float z=-17.5f+i*1.94f;
            iron.Column("iron",14.04f,z,0,1.02f,.047f,.041f,10);
            iron.Column("brass",14.04f,z,1.02f,1.06f,.064f,.049f,12);
        }
        foreach(float h in new[]{.39f,.92f})iron.Box("iron",14.04f,h,-.04f,.052f,.06f,34.92f);
        iron.Save(parent,mats);
        var rail=new Module("Platform_TrackBed");
        rail.Box("stoneTrim",21,-.91f,0,12,.19f,91);
        foreach(float x in new[]{17.8f,21.4f})
        {
            for(int i=0;i<105;i++)rail.Box("darkWood",x,-.746f,-41.6f+i*.8f,2.55f,.14f,.219f);
            foreach(float rx in new[]{x-.7175f,x+.7175f})
            {
                rail.Box("iron",rx,-.66f,0,.139f,.035f,84);
                rail.Box("iron",rx,-.603f,0,.057f,.10f,84);
                rail.Box("steel",rx,-.542f,0,.078f,.041f,84);
            }
        }
        // Distant overhead poles and cross arms carry the sightline past the canopy.
        for(int i=0;i<7;i++)
        {
            float z=-45+i*15;
            rail.Column("iron",24,z,-.85f,5.5f,.13f,.085f);
            rail.Box("iron",21.25f,5.38f,z,5.55f,.092f,.095f);
            rail.Beam("iron",P(24,4.53f,z),P(21.5f,5.38f,z),.068f,.07f);
            if(i<6)
                foreach(float x in new[]{19.1f,22.9f})
                    for(int j=0;j<6;j++)
                    {
                        float h1=5.34f-.45f*Mathf.Sin(j*Mathf.PI/6);
                        float h2=5.34f-.45f*Mathf.Sin((j+1)*Mathf.PI/6);
                        rail.Beam("iron",P(x,h1,z+2.5f*j),P(x,h2,z+2.5f*(j+1)),.026f,.026f);
                    }
        }
        rail.Box("wet",28f,.56f,1,1.1f,2.76f,89);
        for(int i=0;i<17;i++)
            rail.Box("iron",27.40f,.59f,-42+i*5.3f,.20f,2.9f,.36f);
        rail.Save(parent,mats);
        var cabinet=new Module("Platform_MaintenanceCabinet");
        cabinet.Box("iron",7.14f,.98f,6.1f,.68f,1.96f,1.42f);
        cabinet.Box("stoneTrim",7.14f,2.01f,6.1f,.79f,.095f,1.56f);
        foreach(float z in new[]{5.76f,6.44f})
        {
            cabinet.Box("iron",7.51f,1.04f,z,.068f,1.74f,.64f);
            cabinet.Box("brass",7.56f,1.07f,z,.06f,.16f,.046f);
            for(int i=0;i<5;i++)cabinet.Box("stoneTrim",7.55f,1.5f+i*.052f,z,.018f,.016f,.43f);
        }
        cabinet.Save(parent,mats);
    }
}
