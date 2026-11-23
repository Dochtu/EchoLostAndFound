"""Author a cast metal sash for the existing 1.94 x 1.8 m end-wall openings."""
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

TARGET = Path(__file__).resolve().parents[2] / "Assets/_Project/Art/Environment/M1_5/HallSash.fbx"
bpy.ops.wm.read_factory_settings(use_empty=True)
vertices, polygons, material_ids = [], [], []


def tube(sections, slot):
    """Stitch equal rings; keep the end faces on every solid extrusion."""
    start = len(vertices)
    count = len(sections[0])
    for section in sections:
        vertices.extend(section)
    faces = [tuple(start + i for i in reversed(range(count)))]
    for ring in range(len(sections) - 1):
        a = start + count * ring
        for side in range(count):
            b = (side + 1) % count
            faces.append((a + side, a + b, a + count + b, a + count + side))
    last = start + count * (len(sections) - 1)
    faces.append(tuple(last + i for i in range(count)))
    polygons.extend(faces)
    material_ids.extend([slot] * len(faces))


# Cross sections use a stepped glazing rebate, eased bead and recessed web.
def section(width, depth):
    silhouette = [(-.50,0),(.50,0),(.50,.27),(.38,.30),(.36,.55),
                  (.47,.62),(.47,.74),(.35,.80),(.23,.83),(.18,.96),
                  (.11,1),(-.11,1),(-.18,.96),(-.23,.83),(-.35,.80),
                  (-.47,.74),(-.47,.62),(-.36,.55),(-.38,.30),(-.50,.27)]
    return [(width * lateral, depth * outward) for lateral, outward in silhouette]


def sweep(path, profile, seat=.004):
    rings = []
    for i, (x,z) in enumerate(path):
        a, b = path[max(0,i-1)], path[min(i+1,len(path)-1)]
        tangent = Vector((b[0]-a[0],b[1]-a[1])).normalized()
        rings.append([(x - tangent.y * lateral, seat + depth, z + tangent.x * lateral)
                      for lateral, depth in profile])
    tube(rings, 0)


def rail(a,b,width,depth,seat=.004):
    sweep([a,b],section(width,depth),seat)


def fastener(x,z,seat=.049,r=.009):
    # Washer, chamfer and hexagonal head. A recessed band separates the flats.
    def crown(radius, level, sides):
        return [(x+radius*math.cos(i*math.tau/sides),level,
                 z+radius*math.sin(i*math.tau/sides)) for i in range(sides)]
    tube([crown(r*1.33,seat,16),crown(r*1.33,seat+.0017,16),crown(r*1.15,seat+.0026,16)],1)
    tube([crown(r,seat+.0026,6),crown(r,seat+.0058,6),crown(r*.83,seat+.0068,6)],1)


for x in (-.934,.934):
    rail((x,-.865),(x,.867),.072,.048)
    for z in (-.78,-.38,.38,.78):
        fastener(x,z)
rail((-.97,.866),(.97,.866),.068,.052)
rail((-.934,0),(.934,0),.057,.062)
rail((0,-.848),(0,.0),.041,.043)
for x in (-.455,.455):
    rail((x,-.845),(x,-.025),.024,.032)

# An elliptical fanlight centres the upper sash. Spokes terminate on its moulding.
a, b, spring = .889, .574, .249
arc = [(a*math.cos(i*math.pi/48), spring+b*math.sin(i*math.pi/48)) for i in range(49)]
sweep(arc,section(.040,.043))
rail((-.899,spring),(.899,spring),.036,.042)
for angle in (35,65,90,115,145):
    theta=math.radians(angle)
    rail((0,spring),(a*math.cos(theta),spring+b*math.sin(theta)),.021,.030)
rail((0,.025),(0,spring),.030,.036)
# Formed sill with rear return, drip kerf and a softly rounded projecting nose.
sill=[(-.034,.00),(.034,.00),(.031,.021),(.020,.043),(.010,.094),
      (.009,.105),(.006,.110),(-.004,.110),(-.010,.107),(-.011,.098),
      (-.010,.091),(-.005,.089),(-.005,.084),(-.015,.082),(-.017,.046),(-.034,.038)]
sweep([(-.97,-.866),(.97,-.866)],sill)
for x in (-.79,.79):
    fastener(x,0,.066)
# A pair of hinge plates and adjacent caps identify the operable lower light.
for x in (-.90,.90):
    rail((x,-.67),(x,-.54),.026,.021,.018)
    for z in (-.65,-.56):
        fastener(x,z,.039,.006)

mesh=bpy.data.meshes.new("HallSash")
mesh.from_pydata(vertices,[],polygons)
mesh.update()
for label,color in [("PaintedIron",(.075,.102,.093)),("BrassFasteners",(.40,.265,.119))]:
    mat=bpy.data.materials.new(label)
    mat.diffuse_color=(*color,1)
    mesh.materials.append(mat)
for face,slot in zip(mesh.polygons,material_ids):
    face.material_index=slot
bm=bmesh.new()
bm.from_mesh(mesh)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
assert all(e.is_manifold for e in bm.edges)
bm.to_mesh(mesh)
bm.free()
mesh.update()
uv=mesh.uv_layers.new(name="Surface")
for face in mesh.polygons:
    along=max(range(3), key=lambda n: abs(face.normal[n]))
    axes=[n for n in range(3) if n!=along]
    for loop in face.loop_indices:
        p=mesh.vertices[mesh.loops[loop].vertex_index].co
        uv.data[loop].uv=(p[axes[0]]*2,p[axes[1]]*2)
obj=bpy.data.objects.new("HallSash",mesh)
bpy.context.collection.objects.link(obj)
obj.select_set(True)
bpy.context.view_layer.objects.active=obj
bpy.ops.export_scene.fbx(filepath=str(TARGET),use_selection=True,object_types={"MESH"},axis_forward="-Z",axis_up="Y",bake_space_transform=True,bake_anim=False)
# Reload a clean FBX import for round-trip topology, materials, metre scale and UV checks.
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(TARGET))
obj=next(o for o in bpy.context.scene.objects if o.type=="MESH")
data=obj.data
data.calc_loop_triangles()
world=[obj.matrix_world@v.co for v in data.vertices]
bounds=[(min(p[i] for p in world),max(p[i] for p in world)) for i in range(3)]
assert abs(bounds[0][1]-bounds[0][0]-1.94)<.001 and abs(bounds[2][1]-bounds[2][0]-1.80)<.001,bounds
assert [m.name for m in data.materials]==["PaintedIron","BrassFasteners"]
assert len(data.uv_layers)==1
print("Verified FBX:",len(data.vertices),"vertices;",len(data.loop_triangles),"triangles; XYZ bounds",bounds)
