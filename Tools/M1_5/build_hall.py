"""Build the authored station furniture and cast spandrel in metres with Blender 4.5."""
import bpy
import math
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parents[2] / "Assets/_Project/Art/Environment/M1_5"
bpy.ops.wm.read_factory_settings(use_empty=True)
wood, iron, brass = [bpy.data.materials.new(name) for name in ("SeasonedWood", "PaintedIron", "BrassFasteners")]
for mat, color in [(wood,(.29,.13,.06)), (iron,(.065,.085,.078)),(brass,(.48,.32,.16))]:
    mat.diffuse_color = (*color, 1)

def bevel(obj, radius):
    mod=obj.modifiers.new("Rounded edges", "BEVEL")
    mod.width=radius
    mod.segments=3
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.modifiers.new("Corner normals","WEIGHTED_NORMAL")
    bpy.ops.object.modifier_apply(modifier="Corner normals")

def plank(name, loc, dims, tilt=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    obj=bpy.context.object
    obj.name=name
    obj.dimensions=dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bevel(obj,.012)
    uv=obj.data.uv_layers.active.data
    for face in obj.data.polygons:
        for idx in face.loop_indices:
            v=obj.data.vertices[obj.data.loops[idx].vertex_index].co
            uv[idx].uv=((v.x if abs(face.normal.x)<.7 else v.y)/.6, (v.y if abs(face.normal.z)>.7 else v.z)/.6 + loc[2]*3)
    obj.rotation_euler.x=tilt
    obj.data.materials.append(wood)

def casting(name, path, radius, mat=iron, closed=False):
    curve=bpy.data.curves.new(name, "CURVE")
    curve.dimensions="3D"
    curve.resolution_u=9
    curve.bevel_depth=radius
    curve.bevel_resolution=3
    curve.use_fill_caps=True
    spline=curve.splines.new("BEZIER")
    spline.bezier_points.add(len(path)-1)
    for p, pos in zip(spline.bezier_points,path):
        p.co=pos
        p.handle_left_type=p.handle_right_type="AUTO"
    spline.use_cyclic_u=closed
    obj=bpy.data.objects.new(name,curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)

def bolt(pos, tilt=0):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,location=pos)
    obj=bpy.context.object
    obj.scale=(.014,.014,.005)
    obj.rotation_euler.x=tilt
    obj.data.materials.append(brass)

def export(name):
    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active=bpy.context.selected_objects[0]
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.join()
    obj=bpy.context.object
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    obj.name=name
    obj.data.name=name
    bpy.ops.export_scene.fbx(filepath=str(OUT/(name+".fbx")),use_selection=True,object_types={"MESH"},axis_forward="-Z",axis_up="Y",add_leaf_bones=False,bake_anim=False,use_mesh_modifiers=True)
    print(name, len(obj.data.vertices), "vertices")
    bpy.data.objects.remove(obj,do_unlink=True)

for i in range(6):
    y=(i-2.5)*.094
    z=.464+.032*(y/.235)**2
    angle=math.atan(.064*y/.235**2)
    plank("Seat lath",(0,y,z),(2.83,.089,.044),angle)
    for x in (-1.1,1.1):
        bolt((x,y,z+.023),angle)
for i in range(4):
    z=.615+i*.119
    y=.258+i*.032
    plank("Back lath",(0,y,z),(2.83,.108,.043),1.31)
    for x in (-1.1,1.1):
        bolt((x,y-.022,z),1.31)
for x in (-1.1,1.1):
    def side(name,yz,r):
        casting(name,[(x,y,z) for y,z in yz],r)
    side("Splayed cast trestle",[(-.32,.026),(-.30,.08),(-.198,.39),(-.13,.427),(.19,.43),(.25,.38),(.32,.04)],.034)
    side("Seat cradle",[(-.28,.467),(-.14,.432),(0,.426),(.19,.441),(.28,.485),(.40,.985)],.030)
    side("Scrolled arm rail",[(-.23,.515),(-.24,.62),(-.27,.666),(-.22,.691),(.02,.706),(.23,.716),(.32,.76)],.024)
    side("Pierced central web",[(-.19,.35),(-.11,.32),(0,.245),(.14,.30),(.24,.35)],.023)
    for sign in (-1,1):
        side("Inward scroll",[(0,.25),(sign*.069,.31),(sign*.084,.367),(sign*.05,.382),(sign*.042,.355)],.014)
        bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.068,depth=.025,location=(x,sign*.32,.016))
        foot=bpy.context.object
        foot.scale.y=.76
        bevel(foot,.005)
        foot.data.materials.append(iron)
casting("Longitudinal tie rod",[(-1.13,0,.247),(0,0,.247),(1.13,0,.247)],.019)
export("HallSettee")

# A pierced quarter spandrel. The outer flange and concentric cast ribs share a common spring point.
for depth in (-.042,.042):
    def rib(name,xz,r):
        casting(name,[(x,depth,z) for x,z in xz],r)
    rib("Top flange",[(0,0),(.80,.04),(1.52,.15)],.035)
    rib("Wall bracket",[(0,-.89),(0,-.46),(0,0)],.043)
    rib("Lower arch",[(0,-.89),(.18,-.55),(.53,-.24),(1.02,-.033),(1.52,.15)],.04)
    for i,(x,z,r) in enumerate([(.19,-.22,.14),(.49,-.107,.089),(.77,-.033,.054)]):
        points=[(x+math.cos(t*math.tau/12)*r,depth,z+math.sin(t*math.tau/12)*r) for t in range(12)]
        casting("Open cast annulus",points,.018,closed=True)
for x,z in [(0,-.7),(0,-.1),(.5,-.21),(1.44,.13)]:
    casting("Cross pin",[(x,-.06,z),(x,.06,z)],.028,brass)
export("PiercedVaultBracket")
