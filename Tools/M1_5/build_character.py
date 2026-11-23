"""Build the identity-neutral NPC from MPFB 2.0.18 and the official CC0 system pack.

Enable MPFB in an isolated Blender user repository. Point M15_MH_ASSETS at
the extracted makehuman_system_assets_cc0.zip and run Blender in background.
"""
import addon_utils
import bpy
from pathlib import Path
from mathutils import Vector, Quaternion
import math
import os
import shutil

root=Path(__file__).resolve().parents[2]
cache=root/"Temp/M15Character"
src=Path(os.environ.get("M15_MH_ASSETS",cache/"source"))
out=root/"Assets/_Project/Art/Characters/M1_5"
out.mkdir(parents=True,exist_ok=True)
def make_surface_masks():
    # HDRP mask maps contain linear R metal, G AO, B detail mask and A smoothness.
    # Place the facial response by landmarks on the CC0 hm08 skin UV atlas.
    import numpy as np
    import struct
    import zlib

    def write_png(path, pixels):
        def chunk(kind, payload):
            return struct.pack(">I",len(payload))+kind+payload+struct.pack(">I",zlib.crc32(kind+payload))
        h,w,_=pixels.shape
        header=struct.pack(">IIBBBBB",w,h,8,6,0,0,0)
        rows=b"".join(b"\0"+row.tobytes() for row in pixels)
        path.write_bytes(b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",header)+chunk(b"IDAT",zlib.compress(rows,8))+chunk(b"IEND",b""))

    h=w=2048
    y,x=np.ogrid[:h,:w]
    def patch(cx,cy,rx,ry):
        return np.exp(-((x-cx*4)/(rx*4))**2-((y-cy*4)/(ry*4))**2)
    smooth=(.34+.12*patch(408,263,14,43)+.18*patch(449,264,8,13)
            +.16*patch(466,264,4,10)+.055*patch(444,240,11,14)+.055*patch(444,285,11,14))
    pixels=np.full((h,w,4),255,np.uint8)
    pixels[:,:,0]=0
    pixels[:,:,3]=np.rint(smooth*255).astype(np.uint8)
    write_png(out/"Skin_Mask.png",pixels)

    original=bpy.data.images.load(str(src/"clothes/male_casualsuit01/male_casualsuit01_ao.png"))
    original.colorspace_settings.name="Non-Color"
    rgba=np.empty(4*w*h,np.float32)
    original.pixels.foreach_get(rgba)
    ao=np.flipud(rgba.reshape((h,w,4))[:,:,0])
    pixels[:,:,1]=np.rint(255*(.30+.70*ao)).astype(np.uint8)
    pixels[:,:,3]=np.rint(255*(.22+.105*ao)).astype(np.uint8)
    write_png(out/"Wardrobe_Mask.png",pixels)

make_surface_masks()
if "--masks-only" in __import__("sys").argv:
    raise SystemExit(0)

assert addon_utils.enable("bl_ext.user_default.mpfb",default_set=True)
from bl_ext.user_default.mpfb.services.humanservice import HumanService
from bl_ext.user_default.mpfb.services.targetservice import TargetService

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
macro=TargetService.get_default_macro_info_dict()
macro.update(gender=.88,age=.51,muscle=.41,weight=.48,race={"asian":.78,"caucasian":.12,"african":.1})
body=HumanService.create_human(macro_detail_dict=macro)
from bl_ext.user_default.mpfb.services.locationservice import LocationService
target_root=Path(LocationService.get_mpfb_data("targets"))
for area,weight in [("mouth/mouth-upperlip-middle-down",.14),
                    ("mouth/mouth-lowerlip-middle-up",.12),
                    ("expression/units/asian/mouth-compression",.10),
                    ("expression/units/asian/eyebrows-left-inner-up",.035)]:
    TargetService.load_target(body,str(target_root/(area+".target.gz")),weight=weight)
blink_keys=[TargetService.load_target(body,str(target_root/"expression/units/asian"/("eye-"+side+"-closure.target.gz")))
            for side in ("left","right")]
rig=HumanService.add_builtin_rig(body,"mixamo_unity")
assert len(rig.data.bones)>50
assets=[
    ("Wardrobe","Clothes","clothes/male_casualsuit01","male_casualsuit01_diffuse.png","male_casualsuit01_normal.png"),
    ("Shoes","Clothes","clothes/shoes02","shoes02_diffuse.png",None),
    ("Hair","Hair","hair/short02","short02_diffuse.png","short02_normal.png"),
    ("Eyes","Eyes","eyes/high-poly","../materials/brown_eye.png",None),
    ("Brows","Eyebrows","eyebrows/eyebrow001","eyebrow001.png",None),
    ("Lashes","Eyelashes","eyelashes/eyelashes01","eyelashes01.png",None),
    ("Teeth","Teeth","teeth/teeth_base","teeth.png",None)]
pieces=[(body,"Skin",src/"skins/middleage_asian_male/middleage_lightskinned_male_diffuse2.png",None)]
for label,kind,dirname,base,normal in assets:
    directory=src/dirname
    piece=HumanService.add_mhclo_asset(str(next(directory.glob("*.mhclo"))),body,asset_type=kind,
            subdiv_levels=0, material_type="NONE",import_subrig=False,import_weights=False)
    pieces.append((piece,label,directory/base,directory/normal if normal else None))

def refine_fittings(mesh,label,world):
    import bmesh
    import random
    from mathutils import Vector
    inv=world.inverted()
    if label=="Shoes":
        # The ankle shaft originally rises 19 cm, through the denim on the outer calf.
        # Keep the toe box and sole and tuck the upper 12 cm of the shaft inside the hem.
        for v in mesh.vertices:
            pt=world@v.co
            side=1 if pt.x>0 else -1
            t=max(0.,min(1.,(pt.z-.075)/.08))
            pt.x=side*.182+(pt.x-side*.182)*(1-.22*t)
            pt.y=-.018+(pt.y+.018)*(1-.18*t)
            pt.z-=.039*t
            v.co=inv@pt
    if label not in ("Wardrobe","Hair"):
        return
    bm=bmesh.new()
    bm.from_mesh(mesh)
    weights=bm.verts.layers.deform.active
    uv=bm.loops.layers.uv.active
    turned={}
    edges=[e for e in bm.edges if e.is_boundary]
    rng=random.Random(20681)
    for e in edges:
        a,b=e.verts
        pa,pb=world@a.co,world@b.co
        midpoint=(pa+pb)*.5
        base=e.link_loops[0]
        tex={base.vert:base[uv].uv.copy(),base.link_loop_next.vert:base.link_loop_next[uv].uv.copy()}
        if label=="Wardrobe":
            if max(pa.z,pb.z)>.16: continue
            shift=Vector((0,0,-.016))
            shifts=[shift,shift]
        else:
            # Fine hair groups grow from the open fringe and temple silhouette.
            if midpoint.y>-.045 or midpoint.z>1.59 or midpoint.z<1.46: continue
            root=pa.lerp(pb,.23)
            t=pa.lerp(pb,.64)
            off=Vector((-.0018, .0004,-rng.uniform(.003,.009)))
            tip=root.lerp(t,.60)+off
            a2=bm.verts.new(inv@root)
            b2=bm.verts.new(inv@t)
            c2=bm.verts.new(inv@tip)
            for v,orig in ((a2,a),(b2,b),(c2,a)):
                for g,w in orig[weights].items():v[weights][g]=w
            face=bm.faces.new((a2,b2,c2))
            face.smooth=True
            for loop,k in zip(face.loops,(.23,.64,.50)):
                loop[uv].uv=tex[a].lerp(tex[b],k)
            continue
        # Turn the hem under at the open edges; the existing skin weights and UVs
        # continue around the cuff. Retain the perimeter vertices shared by adjacent faces.
        for v,step in zip((a,b),shifts):
            if v not in turned:
                pt=world@v.co+step
                pt.x=math.copysign(.182,pt.x)+(pt.x-math.copysign(.182,pt.x))*.96
                new=bm.verts.new(inv@pt)
                for g,w in v[weights].items(): new[weights][g]=w
                turned[v]=new
        face=bm.faces.new((base.link_loop_next.vert,base.vert,
                           turned[base.vert],turned[base.link_loop_next.vert]))
        face.smooth=True
        for loop,v in zip(face.loops,(base.link_loop_next.vert,base.vert,base.vert,base.link_loop_next.vert)):
            loop[uv].uv=tex[v]
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

# Bake body morphs and clothing masks in rest pose, preserving interpolated bone weights.
for obj,label,diffuse,normal in pieces:
    obj.name=label
    for mod in list(obj.modifiers):
        if mod.type=="ARMATURE":
            obj.modifiers.remove(mod)
    bpy.context.view_layer.update()
    graph=bpy.context.evaluated_depsgraph_get()
    mesh=bpy.data.meshes.new_from_object(obj.evaluated_get(graph),preserve_all_data_layers=True,depsgraph=graph)
    blink_coords=None
    if obj==body:
        for key in blink_keys: key.value=.94
        bpy.context.view_layer.update()
        evaluated=obj.evaluated_get(graph)
        blink_coords=[v.co.copy() for v in evaluated.data.vertices]
        for key in blink_keys: key.value=0
    obj.modifiers.clear()
    obj.data=mesh
    obj.data.name=label
    refine_fittings(mesh,label,obj.matrix_world)
    if blink_coords:
        assert len(blink_coords)==len(mesh.vertices)
        obj.shape_key_add(name="Basis")
        blink=obj.shape_key_add(name="Blink")
        for vertex,co in zip(blink.data,blink_coords): vertex.co=co
        for frame,value in [(1,0),(78,0),(81,1),(84,0),(121,0)]:
            blink.value=value
            blink.keyframe_insert(data_path="value",frame=frame)
    arm=obj.modifiers.new("Skeleton","ARMATURE")
    arm.object=rig
    for group in list(obj.vertex_groups):
        if group.name not in rig.data.bones:
            obj.vertex_groups.remove(group)
    assert all(v.groups for v in obj.data.vertices),f"Unweighted vertex: {label}"
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL",limit=4)
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    obj.data.materials.clear()
    mat=bpy.data.materials.new("M15_"+label)
    obj.data.materials.append(mat)
    for poly in obj.data.polygons: poly.use_smooth=True
    for texture,kind in [(diffuse,"Color"),(normal,"Normal")]:
        if texture:
            shutil.copyfile(texture,out/(label+"_"+kind+".png"))
rig.name="StationVisitor"
scene=bpy.context.scene
scene.frame_start=1
scene.frame_end=121
scene.render.fps=30

def bone(name):
    return rig.pose.bones["mixamorig:"+name]

def aim(pb,direction):
    # Pose directions are expressed in armature space and transferred
    # back to the bone basis to respect each rest roll.
    bpy.context.view_layer.update()
    q=pb.matrix.to_quaternion()
    current=pb.tail-pb.head
    delta=current.normalized().rotation_difference(Vector(direction).normalized())
    pb.rotation_mode="QUATERNION"
    pb.rotation_quaternion=pb.rotation_quaternion @ q.inverted() @ delta @ q
    bpy.context.view_layer.update()

for side,sign in [("Left",1),("Right",-1)]:
    aim(bone(side+"Arm"),(.15*sign,.045 if sign>0 else -.09,-1))
    aim(bone(side+"ForeArm"),(.06*sign,-.40 if sign>0 else -.18,-1))
# Palm-facing curls increase from index to little finger, with a lighter curl on the right.
    for digit,bend in [("Index",9),("Middle",13),("Ring",17),("Pinky",21)]:
        for n in (1,2,3):
            pb=bone(side+"Hand"+digit+str(n))
            tangent=(pb.tail-pb.head).normalized()
            inward=Vector((-sign,-.14,0))
            axis=tangent.cross(inward).normalized()
            direction=Quaternion(axis,math.radians(bend*(1.0 if sign>0 else .74)*(.70 if n==1 else 1.0)))@tangent
            aim(pb,direction)
            for frame in (1,121):
                pb.keyframe_insert(data_path="rotation_quaternion",frame=frame)
for frame,sine in [(1,0),(31,1),(61,0),(91,-1),(121,0)]:
    for name,axis,angle in [("Spine",(1,0,0),.65),("Spine1",(1,0,0),.55),
                             ("Neck",(0,1,0),1.2),("Head",(1,0,0),.78)]:
        pb=bone(name)
        pb.rotation_mode="QUATERNION"
        tilt={"Neck":-1.25,"Head":1.7,"Spine":.8,"Spine1":-.4}[name]
        pb.rotation_quaternion=Quaternion(axis,math.radians(tilt+angle*sine))
    hips=bone("Hips")
    hips.rotation_mode="QUATERNION"
    hips.rotation_quaternion=Quaternion((0,0,1),math.radians(.55+.34*sine))
    hips.keyframe_insert(data_path="rotation_quaternion",frame=frame)
    for name in ["Spine","Spine1","Neck","Head","LeftArm","RightArm","LeftForeArm","RightForeArm"]:
        bone(name).keyframe_insert(data_path="rotation_quaternion",frame=frame)
rig.animation_data.action.name="StandingIdle"
scene.frame_set(1)
bpy.ops.object.select_all(action="DESELECT")
rig.select_set(True)
for obj,*_ in pieces: obj.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.fbx(filepath=str(out/"StationVisitor.fbx"),use_selection=True,object_types={"MESH","ARMATURE"},
    use_mesh_modifiers=False,add_leaf_bones=False,bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,
    bake_anim_simplify_factor=.25,axis_forward="-Z",axis_up="Y",path_mode="STRIP")
print("Rig:",len(rig.data.bones),"bones.",[(label,len(o.data.vertices)) for o,label,*_ in pieces])
