"""Sew and settle the canvas A-0641 holdall in Blender; export the evaluated cloth."""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_counter import Model, outline


N, LEVELS = 108, 27
FABRIC, LEATHER, THREAD, METAL = "OldFabric", "Leather", "BindingThread", "BrassFasteners"


def loop_at(zfraction):
    """A sewn flat-bottom case with a broad lower gusset and a gathered, closed mouth."""
    h=zfraction
    halfwidth=.241+.040*math.sin(math.pi*h)**.7-.216*h**3.5
    halflength=.312+.054*math.sin(math.pi*h)**.72-.010*h**3
    radius=min(.088, halfwidth*.75)
    polygon=outline(halfwidth,halflength,radius,10)
    edges=[math.dist(p,polygon[(i+1)%len(polygon)]) for i,p in enumerate(polygon)]
    total=sum(edges)
    loop=[]
    for j in range(N):
        distance=j*total/N
        i=0
        while i+1<len(polygon) and distance>edges[i]:
            distance-=edges[i]
            i+=1
        t=min(1,distance/edges[i])
        a,b=polygon[i],polygon[(i+1)%len(polygon)]
        x=a[0]+(b[0]-a[0])*t
        y=a[1]+(b[1]-a[1])*t
        # Bias-cut canvas is drawn toward the four handle keepers. Fold amplitude dies at the bindings.
        side=min(1,abs(x)/max(.001,halfwidth))**4
        z=.006+.301*h+.027*h*h*(abs(y)/halflength)**2
        folds=(.009*math.sin(26*y+12*h+.5*math.cos(9*y))+
               .007*math.sin(52*y-7*h)+.004*math.sin(62*h+18*y))
        x+=math.copysign(1,x)*side*math.sin(math.pi*h)**.65*folds
        z+=.005*math.cos(29*y-4*h)*math.sin(math.pi*h)
        loop.append((x,y,z))
    return loop


def simulated_shell():
    rings=[loop_at(i/(LEVELS-1)) for i in range(LEVELS)]
    verts=[p for ring in rings for p in ring]
    faces=[]
    for i in range(LEVELS-1):
        for j in range(N):
            k=(j+1)%N
            faces.append((i*N+j,i*N+k,(i+1)*N+k,(i+1)*N+j))
    # Bottom and mouth have their own centre vertex to avoid unstable cloth n-gons.
    for i in (0,LEVELS-1):
        centre=len(verts)
        verts.append(tuple(sum(p[a] for p in rings[i])/N for a in range(3)))
        for j in range(N):
            a=i*N+j
            b=i*N+(j+1)%N
            faces.append((b,a,centre) if i==0 else (a,b,centre))
    mesh=bpy.data.meshes.new("GussetedCanvasPattern")
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    obj=bpy.data.objects.new("HoldallCloth",mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active=obj
    pin=obj.vertex_groups.new(name="Floor seam, mouth and strap anchors")
    for i in range(LEVELS):
        h=i/(LEVELS-1)
        for j,p in enumerate(rings[i]):
            anchor=math.exp(-((abs(p[1])-.145)/.048)**2-((h-.76)/.17)**2)
            weight=max(0,1-1.24*math.sin(math.pi*h)**.65,anchor)
            pin.add([i*N+j],weight,"REPLACE")
    pin.add([len(verts)-1,len(verts)-2],1,"REPLACE")
    cloth=obj.modifiers.new("Gravity settling of pinned stitched panels","CLOTH")
    opts=cloth.settings
    opts.vertex_group_mass=pin.name
    opts.quality=8
    opts.mass=.24
    opts.tension_stiffness=16
    opts.compression_stiffness=12
    opts.shear_stiffness=8
    opts.bending_stiffness=.35
    opts.pin_stiffness=1.2
    opts.effector_weights.gravity=.78
    cloth.point_cache.frame_start=1
    cloth.point_cache.frame_end=22
    for frame in range(1,23):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    result=[v.co.copy() for v in evaluated.data.vertices]
    max_travel=max((result[i]-Vector(p)).length for i,p in enumerate(verts))
    assert .0005<max_travel<.18, f"Unexpected cloth travel {max_travel}"
    print("Blender Cloth evaluated frames 1..22; greatest vertex displacement",round(max_travel,5),"m",flush=True)
    bpy.data.objects.remove(obj,do_unlink=True)
    base=min(p.z for p in result)
    for p in result:
        p.z-=base
    return [result[i*N:(i+1)*N] for i in range(LEVELS)]


def dashed(m,path,spacing=.012):
    lengths=[(b-a).length for a,b in zip(path,path[1:])]
    j=0
    distance=spacing*.4
    while j<len(lengths):
        if distance+.004<lengths[j]:
            a,b=path[j:j+2]
            direction=(b-a).normalized()
            p=a+direction*distance
            m.strap([p,p+direction*.004],.00072,THREAD,4)
            distance+=spacing
        else:
            distance=max(0,distance-lengths[j])
            j+=1


def handle(m,sign):
    # Leather loop cross-section includes the slightly rolled edges of its reinforcing welt.
    centres=[]
    for j in range(41):
        t=j/40
        y=-.154*math.cos(math.pi*t)
        z=.22+.255*math.sin(math.pi*t)**.88
        x=sign*(.232-.094*math.sin(math.pi*t)**.8)
        centres.append(Vector((x,y,z)))
    sections=[]
    edge_tracks=[[],[]]
    for j,p in enumerate(centres):
        tangent=centres[min(j+1,40)]-centres[max(j-1,0)]
        width=Vector((0,tangent.z,-tangent.y)).normalized()
        outward=tangent.cross(width).normalized()
        if outward.x*sign<0: outward.negate()
        profile=outline(.013,.0034,.0016,2)
        sections.append([p+width*u+outward*v for u,v in profile])
        for k,offset in enumerate((-.009,.009)):
            edge_tracks[k].append(p+width*offset+outward*.00365)
    m.loft(sections,LEATHER,True)
    for track in edge_tracks: dashed(m,track,.010)
    for end in (-1,1):
        y=end*.154
        # A broad tab bridges the gathered gusset to the handle end.
        profiles=[(.247,.175,.032),(.242,.190,.039),(.229,.222,.034),(.214,.252,.030)]
        rings=[]
        for x,z,w in profiles:
            rings.append([(sign*(x+v),y+u,z) for u,v in outline(w/2,.004,.0015,2)])
        m.loft(rings,LEATHER)
        for z,x in ((.19,.245),(.213,.234)):
            m.strap([(sign*x,y,z),(sign*(x+.005),y,z)],.006,METAL,12)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rings=simulated_shell()
    m=Model([FABRIC,LEATHER,THREAD,METAL])
    m.loft(rings,FABRIC,True)
    # Piped transverse seams are sampled on the settled mesh to follow its folds.
    for end in (-1,1):
        target=end*.252
        front=[]
        back=[]
        for ring in rings:
            for sign,track in ((-1,back),(1,front)):
                p=min((p for p in ring if p.x*sign>0),key=lambda p:abs(p.y-target))
                track.append(p+Vector((sign*.001,0,.0006)))
        contour=front+back[::-1]+[front[0]]
        m.strap(contour,.0027,LEATHER,8)
        dashed(m,[p+Vector((0,-end*.0045,.0005)) for p in contour],.0105)
    # Zipper sits at the top of the sewn mouth; both welts, interlocking teeth and the pull are distinct.
    for sign in (-1,1):
        path=[Vector((sign*.012,y/1000,.304+.027*(y/310)**2)) for y in range(-300,301,10)]
        m.strap(path,.005,LEATHER)
    for n in range(69):
        y=-.286+n*.0084
        z=.304+.027*(y/.31)**2
        m.strap([(-.010,y,z),(.008,y+.003,z+.0005)],.0024,METAL,6)
    pull=[(.013,-.225,.322),(.020,-.233,.337),(.024,-.264,.337),
          (.018,-.272,.332),(.009,-.262,.327),(.013,-.225,.322)]
    m.strap(pull,.0032,METAL,8)
    for sign in (-1,1): handle(m,sign)
    # Physical leather address label behind the project's existing printed face at local x=.311.
    # Its cant is shared with the lettering already parented to the original bag.
    theta=math.radians(8)
    m.loft([[(x,y*math.cos(theta)-h*math.sin(theta),.20+y*math.sin(theta)+h*math.cos(theta))
             for y,h in outline(.197,.068,.009)] for x in (.278,.295)],LEATHER)
    for end in (-1,1):
        m.strap([(.252,end*.168,.24),(.278,end*.170,.249),(.294,end*.170,.248)],.006,LEATHER)
    m.save("FoundHoldall")


if __name__=="__main__":
    main()
