"""Station terrazzo bays, flush divider strips and a closed plinth, authored in metres."""
import bisect
import math
from pathlib import Path
from random import Random

import bmesh
import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
TARGET = Path(__file__).resolve().parents[2] / "Assets/_Project/Art/Environment/M1_5/HallPaving.fbx"
STONE, BRASS, GROUT = range(3)
width, length, depth = 12.4, 20.4, .28
grout_width, brass_width = .004, .015
# Five principal bays between continuous brass borders, with smaller fields against the wall.
x_joints = [-5.15, -3.09, -1.03, 1.03, 3.09, 5.15]
y_joints = [-7.65, -5.10, -2.55, 0, 2.55, 5.10, 7.65]
brass_ends = 9.975


def divisions(half_size, joints, widths, extra=()):
    cuts = {-half_size, half_size, *extra}
    for center, span in zip(joints, widths):
        cuts.update((center-span/2, center+span/2))
    return sorted(cuts)


xcuts=divisions(width/2,x_joints,[brass_width,grout_width,grout_width,grout_width,grout_width,brass_width])
ycuts=divisions(length/2,y_joints,[grout_width]*len(y_joints),[-brass_ends,brass_ends])
positions, indices, faces, materials, coordinates = [], {}, [], [], []


def vertex(p):
    if p not in indices:
        indices[p]=len(positions)
        positions.append(p)
    return indices[p]


def face(points, slot, uv):
    faces.append([vertex(p) for p in points])
    materials.append(slot)
    coordinates.append(uv)


def uv_basis(x, y):
    # Independently rotated stock for each pour; incidental cuts at brass ends
    # must preserve UV continuity on their adjacent panels.
    bay_x=bisect.bisect(x_joints,x)
    bay_y=bisect.bisect(y_joints,y)
    r=Random(2471+bay_x*7919+bay_y)
    angle=r.randrange(4)*math.pi/2
    a,b=round(math.cos(angle)),round(math.sin(angle))
    phase_u,phase_v=r.uniform(0,1.5),r.uniform(0,1.5)
    return lambda p:(a*p[0]-b*p[1]+phase_u,b*p[0]+a*p[1]+phase_v)


for xa,xb in zip(xcuts,xcuts[1:]):
    x=(xa+xb)/2
    brass_band=abs(abs(x)-5.15)<.00001
    longitudinal_joint=any(abs(x-j)<.00001 for j in x_joints)
    for ya,yb in zip(ycuts,ycuts[1:]):
        y=(ya+yb)/2
        transverse_joint=any(abs(y-j)<.00001 for j in y_joints)
        if brass_band and abs(y)<brass_ends:
            material=BRASS
        elif longitudinal_joint or transverse_joint:
            material=GROUT
        else:
            material=STONE
        top=[(xa,ya,0),(xb,ya,0),(xb,yb,0),(xa,yb,0)]
        bottom=[(px,py,-depth) for px,py,h in reversed(top)]
        transform=uv_basis(x,y)
        face(top,material,[transform(p) for p in top])
        face(bottom,GROUT,[(p[0],p[1]) for p in bottom])

# The side faces share the exact edge vertices of the top and bottom grids.
perimeter=([(x,ycuts[0]) for x in xcuts]+
           [(xcuts[-1],y) for y in ycuts[1:]]+
           [(x,ycuts[-1]) for x in reversed(xcuts[:-1])]+
           [(xcuts[0],y) for y in reversed(ycuts[1:-1])])
distance=0.
for (a,b) in zip(perimeter,perimeter[1:]+perimeter[:1]):
    xa,ya=a
    xb,yb=b
    end=distance+math.dist(a,b)
    face([(xa,ya,-depth),(xb,yb,-depth),(xb,yb,0),(xa,ya,0)],
         GROUT,[(distance,-depth),(end,-depth),(end,0),(distance,0)])
    distance=end

mesh=bpy.data.meshes.new("HallPaving")
mesh.from_pydata(positions,[],faces)
mesh.update()
for name,color in [("Terrazzo",(.42,.39,.35)),("BrassFasteners",(.47,.32,.16)),("Grout",(.36,.33,.30))]:
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1)
    mesh.materials.append(mat)
layer=mesh.uv_layers.new(name="MetricPaving")
for polygon,slot,uv_points in zip(mesh.polygons,materials,coordinates):
    polygon.material_index=slot
    for loop,point in zip(polygon.loop_indices,uv_points):
        layer.data[loop].uv=point
bm=bmesh.new()
bm.from_mesh(mesh)
assert all(edge.is_manifold and edge.is_contiguous for edge in bm.edges)
assert abs(bm.calc_volume(signed=True)-width*length*depth)<.0001
assert all(face.normal.z>.99999 for face in bm.faces if all(abs(v.co.z)<1e-7 for v in face.verts))
bm.free()
obj=bpy.data.objects.new("HallPaving",mesh)
bpy.context.collection.objects.link(obj)
obj.select_set(True)
bpy.context.view_layer.objects.active=obj
bpy.ops.export_scene.fbx(filepath=str(TARGET),use_selection=True,object_types={"MESH"},axis_forward="-Z",axis_up="Y",bake_space_transform=True,bake_anim=False)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(TARGET))
obj=next(o for o in bpy.context.scene.objects if o.type=="MESH")
mesh=obj.data
mesh.calc_loop_triangles()
world=[obj.matrix_world@v.co for v in mesh.vertices]
bounds=[(min(p[i] for p in world),max(p[i] for p in world)) for i in range(3)]
assert [m.name for m in mesh.materials]==["Terrazzo","BrassFasteners","Grout"]
assert abs(bounds[0][1]-bounds[0][0]-width)<.0001
assert abs(bounds[1][1]-bounds[1][0]-length)<.0001
assert abs(bounds[2][1])<.0001
assert len(mesh.uv_layers)==1
print("Verified HallPaving",len(mesh.vertices),"vertices",len(mesh.loop_triangles),"triangles",bounds)
