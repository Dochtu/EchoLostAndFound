"""Refine a verified M1.5 visitor in Blender 4.5. Run blender -b -P this_file -- --help."""
import argparse
import hashlib
import math
import random
import sys
import tempfile
import zipfile
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

ROOT = Path(__file__).resolve().parents[2]
MODEL = Path("Assets/_Project/Art/Characters/M1_5/StationVisitor.fbx")
BASE_SHA = "fa02edafb8efbd19195811dd061217c75286646281c255c36ee2c09b63d0c25b"
parser = argparse.ArgumentParser()
parser.add_argument("--baseline", type=Path, default=ROOT / "Stage4_M1_5_VisualUpgrade_Delivery.zip")
parser.add_argument("--output", type=Path, default=ROOT / MODEL)
args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
rng = random.Random(917212)


def world_mesh(obj):
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def hair_layers(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    triangles = list(mesh.loop_triangles)
    vertices = world_mesh(obj)
    tree = BVHTree.FromPolygons(vertices, [t.vertices[:] for t in triangles], all_triangles=True)
    atlas = bpy.data.images.load(str(ROOT / MODEL.parent / "Hair_Color.png"))
    w,h = atlas.size
    pixels = np.empty(4*w*h, np.float32)
    atlas.pixels.foreach_get(pixels)
    rgba = pixels.reshape(h,w,4)
    uv = mesh.uv_layers.active.data
    center = Vector((-.001, -.047, 1.554))
    def sample(yaw, elevation):
        radial = Vector((math.sin(yaw)*math.cos(elevation), -math.cos(yaw)*math.cos(elevation), math.sin(elevation)))
        origin = center + radial*.22
        for _ in range(10):
            pt, normal, index, _ = tree.ray_cast(origin,-radial,.20)
            if pt is None:
                return None
            tri = triangles[index]
            tex = barycentric_transform(pt, *(vertices[i] for i in tri.vertices),
                        *(Vector((*uv[i].uv,0)) for i in tri.loops))
            if rgba[min(h-1,max(0,int(tex.y*h))),min(w-1,max(0,int(tex.x*w))),3]>.52:
                if normal.dot(radial)<0:
                    normal.negate()
                return pt,normal
            origin = pt - radial*.0001
        return None
    bm = bmesh.new()
    bm.from_mesh(mesh)
    deform = bm.verts.layers.deform.active
    uv_layer = bm.loops.layers.uv.active
    head = obj.vertex_groups["mixamorig:Head"].index
    # Use opaque, brown source pixels for the interior of individual tapered locks.
    good = (rgba[:,:,3]>.97) & (rgba[:,:,0]>.018) & (rgba[:,:,0]<.17)
    for dy,dx in [(4,0),(-4,0),(0,4),(0,-4)]:
        good &= np.roll(good,(dy,dx),(0,1))
    ys,xs = np.where(good)
    if not len(xs):
        raise ValueError("No usable hair atlas samples")
    inv = obj.matrix_world.inverted()
    count = [0,0,0]
    for layer, target in enumerate((260,370,240)):
        for j in range(target):
            # Lowest opaque shell hit follows the actual sideburn and fringe silhouette.
            yaw = rng.uniform(-2.9,2.9) if layer==0 else rng.uniform(-1.85,1.85)
            limit = next((z for z in np.arange(-1.1,.97,.026) if sample(yaw,z)), None)
            if limit is None:
                continue
            tip = limit + rng.uniform(-.025,.10) + (rng.uniform(.15,.92) if layer==0 else 0)
            span = rng.uniform(.28,.74) if layer!=2 else rng.uniform(.17,.43)
            drift = (-1 if yaw<-.38 else 1)*rng.uniform(.10,.44)
            path = []
            coords = []
            for i in range(10):
                t=i/9
                hit=sample(yaw-drift*(1-t)**1.3, tip + span*(1-t))
                if not hit:
                    if len(path)>=2 and i>=6:
                        path.append(path[-1]+(path[-1]-path[-2])*.85)
                        coords.append(coords[-1])
                        continue
                    break
                pos,normal=hit
                lift=(.0005,.0009,.0013)[layer] + (.0025,.002,.001)[layer]*math.sin(math.pi*t)
                path.append(pos+normal*lift)
                coords.append(normal)
            if len(path)<8:
                continue
            path[-1]+=Vector((drift*.005,-.0015,-(.002 if layer==0 else rng.uniform(.003,.009))))
            pick=rng.randrange(len(xs))
            tex=Vector(((xs[pick]+.5)/w,(ys[pick]+.5)/h))
            width=rng.uniform(*[(.0013,.0028),(.00064,.00155),(.00027,.00072)][layer])
            rows=[]
            for i,(pt,normal) in enumerate(zip(path,coords)):
                t=i/(len(path)-1)
                tangent=(path[min(i+1,len(path)-1)]-path[max(i-1,0)]).normalized()
                lateral=tangent.cross(normal).normalized()
                halfwidth=width*max(.035,(1-t)**.63)*(.5+.5*min(1,t*6))
                row=[]
                for k in (-1,0,1):
                    v=bm.verts.new(inv@(pt+lateral*(k*halfwidth)+normal*(halfwidth*.34 if k==0 else 0)))
                    v[deform][head]=1.
                    row.append(v)
                if rows:
                    for k in (0,1):
                        f=bm.faces.new((rows[-1][k],rows[-1][k+1],row[k+1],row[k]))
                        f.smooth=True
                        for loop,ds,dt in zip(f.loops,(0,1,1,0),(0,0,1,1)):
                            loop[uv_layer].uv=tex+Vector(((k+ds-1)/w,(i-5+dt)/h))
                rows.append(row)
            count[layer]+=1
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    print("R1 tapered scalp locks by layer", count,flush=True)
    if min(count)<100:
        raise ValueError("Incomplete hair coverage")


def relief(skin, wardrobe):
    # Follow real blink deltas when displacing the lid ridge, preserving blink topology.
    coords=world_mesh(skin)
    keys=skin.data.shape_keys.key_blocks
    inv=skin.matrix_world.inverted().to_3x3()
    lids=0
    for i,p in enumerate(coords):
        if p.y>-.124 or abs(abs(p.x)-.030)>.020 or abs(p.z-1.535)>.012:
            continue
        closure=(keys["Blink"].data[i].co-keys["Basis"].data[i].co).length
        if closure<.0003:
            continue
        x=(abs(p.x)-.030)/.018
        ridge=1.536+.0042*(1-x*x)+.001*x
        dz=p.z-ridge
        amount=.0017*math.exp(-(dz/.0028)**2)-.0009*math.exp(-((dz-.004)/.0018)**2)
        shift=inv@Vector((0,-amount,amount*.20))
        for key in keys:
            key.data[i].co+=shift
        skin.data.vertices[i].co=keys["Basis"].data[i].co
        lids+=1
    count=0
    max_fold=0.
    cloth=wardrobe.data
    # Drive compression folds by diagonal distance about elbow, knee, waist and ankle.
    for v,p in zip(cloth.vertices,world_mesh(wardrobe)):
        x=abs(p.x)
        joints=[(.385,1.08,.090,.110,.0075,83),(.14,.48,.100,.13,.008,80),
                (.175,.16,.072,.080,.0058,112),(.10,.91,.16,.075,.0048,90)]
        relief_mm=0.
        for cx,cz,rx,rz,amp,freq in joints:
            env=math.exp(-((x-cx)/rx)**2-((p.z-cz)/rz)**2)
            phase=(p.z-cz+.38*(x-cx)+.28*p.y)*freq+(1.1 if p.x<0 else 0)
            relief_mm+=env*amp*(.69*math.sin(phase)+.31*math.sin(phase*1.78+.7))
        if abs(relief_mm)>.0001:
            v.co+=v.normal.normalized()*relief_mm
            max_fold=max(max_fold,abs(relief_mm))
            count+=1
    print("R1 lid vertices",lids,"cloth vertices",count,"max fold m",max_fold,flush=True)
    if lids<10 or count<150:
        raise ValueError("Registration outside approved character topology")


def animate(rig,scene):
    channels={
        "Spine2": ((0,0,1),-.85,.52,.11),
        "LeftShoulder": ((0,0,1),-2.6,.74,.20),
        "RightShoulder": ((0,0,1),1.4,-.39,.35),
        "LeftArm": ((1,0,0),-2.9,.82,.08),
        "RightArm": ((1,0,0),1.9,-.63,.18),
        "LeftForeArm": ((0,0,1),3.7,.85,.23),
        "RightForeArm": ((0,0,1),-2.1,.55,.4),
        "LeftHand": ((0,1,0),3.,1.0,.21),
        "RightHand": ((0,1,0),-1.8,-.65,.41),
        "LeftEye": ((0,0,1),0,1.65,.29),
        "RightEye": ((0,0,1),0,1.65,.29),
    }
    bones={k:rig.pose.bones["mixamorig:"+k] for k in channels}
    frames=list(range(scene.frame_start, scene.frame_end+1,4))
    base={}
    for frame in frames:
        scene.frame_set(frame)
        base[frame]={name:pb.rotation_quaternion.copy() for name,pb in bones.items()}
    for frame in frames:
        t=(frame-scene.frame_start)/(scene.frame_end-scene.frame_start)
        for name,(axis,static,amplitude,phase) in channels.items():
            pb=bones[name]
            angle=static+amplitude*math.sin(2*math.pi*(t+phase))
            pb.rotation_quaternion=base[frame][name]@Quaternion(axis,math.radians(angle))
            pb.keyframe_insert(data_path="rotation_quaternion",frame=frame)
    scene.frame_set(scene.frame_start)


def validate(path,expected):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path),anim_offset=0)
    rig=bpy.data.objects['StationVisitor']
    assert tuple(p.name for p in rig.data.bones)==expected
    names={o.name for o in bpy.data.objects if o.type=="MESH"}
    assert names=={"Skin","Eyes","Brows","Hair","Wardrobe","Shoes","Teeth","Lashes"}
    for name in names:
        obj=bpy.data.objects[name]
        assert obj.find_armature()==rig and len(obj.data.materials)==1
        assert all(v.groups for v in obj.data.vertices)
    assert bpy.data.objects['Skin'].data.shape_keys.key_blocks.get('Blink')
    clip=rig.animation_data.action
    start,end=map(int,clip.frame_range)
    assert end-start==120 and bpy.context.scene.render.fps==30
    points=[]
    for f in (start,start+36,start+60,end):
        bpy.context.scene.frame_set(f)
        points.append([rig.pose.bones["mixamorig:"+key].tail.copy() for key in ("LeftHand","RightHand","Head","LeftFoot","RightFoot")])
    seam=max((a-b).length for a,b in zip(points[0],points[-1]))
    travel=[round(max((p[i]-points[0][i]).length for p in points)*1000,3) for i in range(5)]
    assert seam<.0002 and max(travel[:3])>.5
    print("R1 FBX reimport verified",len(expected),"bones",end-start,"intervals, seam m",seam,"motion mm",travel,flush=True)


with tempfile.TemporaryDirectory(dir=ROOT / "Temp") as stage:
    stage=Path(stage)
    baseline=stage/"Source.fbx"
    raw=(zipfile.ZipFile(args.baseline).read(MODEL.as_posix()) if args.baseline.suffix.lower()==".zip" else args.baseline.read_bytes())
    if hashlib.sha256(raw).hexdigest()!=BASE_SHA:
        raise ValueError("Unrecognized baseline; use the original M1.5 delivery FBX")
    baseline.write_bytes(raw)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(baseline),anim_offset=0)
    rig=bpy.data.objects["StationVisitor"]
    bones=tuple(p.name for p in rig.data.bones)
    scene=bpy.context.scene
    scene.frame_start,scene.frame_end=map(int,rig.animation_data.action.frame_range)
    hair_layers(bpy.data.objects["Hair"])
    relief(bpy.data.objects["Skin"],bpy.data.objects["Wardrobe"])
    animate(rig,scene)
    out=stage/"StationVisitor.fbx"
    bpy.ops.export_scene.fbx(filepath=str(out),object_types={"MESH","ARMATURE"},use_mesh_modifiers=False,
        add_leaf_bones=False,bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,
        bake_anim_simplify_factor=.16,axis_forward="-Z",axis_up="Y",path_mode="STRIP")
    validate(out,bones)
    args.output.write_bytes(out.read_bytes())

