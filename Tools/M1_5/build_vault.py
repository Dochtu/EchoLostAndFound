"""Waiting hall barrel vault, triangulated bowstring frames and two glazed fanlights."""
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


OUT = Path(__file__).resolve().parents[2] / "Assets/_Project/Art/Environment/M1_5/HallVault.fbx"
SPAN, RISE, SPRING = 6.2, 1.65, 5.76
TRUSSES = (-9.6, -6.0, -2.0, 2.0, 6.0, 9.6)
IRON, PLASTER, WOOD, GLASS = range(4)
positions, faces, uv_faces, material_ids, smooth_flags = [], [], [], [], []


def add_face(indices, coords, material, smooth=False):
    faces.append(tuple(indices))
    uv_faces.append(coords)
    material_ids.append(material)
    smooth_flags.append(smooth)


def loft(frames, profile, material, smooth=False):
    """Each frame carries a centre and two section axes. Unwrap perimeter and length in metres."""
    rings = []
    length = [0.0]
    perimeter = [0.0]
    for i, p in enumerate(profile):
        previous = profile[i - 1]
        if i:
            perimeter.append(perimeter[-1] + math.dist(previous, p))
    perimeter.append(perimeter[-1] + math.dist(profile[-1], profile[0]))
    for index, (centre, u, v) in enumerate(frames):
        if index:
            length.append(length[-1] + (centre - frames[index-1][0]).length)
        ring = []
        for x, y in profile:
            ring.append(len(positions))
            positions.append(tuple(centre + x*u + y*v))
        rings.append(ring)
    for i in range(len(rings)-1):
        for j in range(len(profile)):
            k = (j+1) % len(profile)
            add_face((rings[i][j],rings[i][k],rings[i+1][k],rings[i+1][j]),
                     ((perimeter[j],length[i]),(perimeter[j+1],length[i]),
                      (perimeter[j+1],length[i+1]),(perimeter[j],length[i+1])),
                     material,smooth)
    add_face(rings[0][::-1],profile[::-1],material)
    add_face(rings[-1],profile,material)


def rect(w,h):
    return [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]


def i_section(w, h, flange, web):
    a,b,c,t=w/2,h/2,web/2,flange
    return [(-a,-b),(a,-b),(a,-b+t),(c,-b+t),(c,b-t),(a,b-t),
            (a,b),(-a,b),(-a,b-t),(-c,b-t),(-c,-b+t),(-a,-b+t)]


def angle_for_x(x):
    return math.acos(-x/SPAN)


def frame(angle, depth, inset):
    nx, nz = -math.cos(angle)/SPAN, math.sin(angle)/RISE
    radius = math.hypot(nx,nz)
    normal = Vector((nx/radius,0,nz/radius))
    p = Vector((-SPAN*math.cos(angle),depth,SPRING+RISE*math.sin(angle)))
    return p - inset*normal, Vector((0,1,0)), normal


def arch(depth,inset,a,b,n,profile,material,smooth=False):
    loft([frame(a+(b-a)*i/n, depth, inset) for i in range(n+1)],profile,material,smooth)


def bar(a,b,profile,material,reference=(0,1,0)):
    a,b = Vector(a),Vector(b)
    direction = (b-a).normalized()
    v = Vector(reference).cross(direction).normalized()
    u = direction.cross(v).normalized()
    loft([(a,u,v),(b,u,v)],profile,material)


def rod_profile(radius,n=8):
    return [(radius*math.cos(t*math.tau/n),radius*math.sin(t*math.tau/n)) for t in range(n)]


def connector(x, depth, z):
    # The web plate joins two stays at their common work point. Rivets sit on both visible faces.
    for side in (-1,1):
        plate_y=depth+side*.049
        bar((x-.092,plate_y,z),(x+.092,plate_y,z),rect(.012,.119),IRON)
        for off in (-.061,.061):
            bar((x+off,plate_y,z),(x+off,plate_y+side*.012,z),rod_profile(.014),IRON,(1,0,0))


# Longitudinal staves span under the weather skin. Each joint has real depth and a rebated edge.
# The thin lining panels are drawn across bays, with their timber beads broken at the iron ribs.
bays = (-10.35,) + TRUSSES + (10.35,)
for z0,z1 in zip(bays,bays[1:]):
    centre=(z0+z1)/2
    for panel in range(18):
        a=panel*math.pi/18
        b=(panel+1)*math.pi/18
        arch(centre,-.023,a,b,5,rect(z1-z0,.044),PLASTER)
    for joint in range(1,18):
        p,u,n=frame(joint*math.pi/18,centre,.006)
        tangent=n.cross(u).normalized()
        width=.058 if joint==9 else .023
        profile=[(-width/2,.009),(-width/2,0),(-width*.25,-.007),
                 (width*.25,-.007),(width/2,0),(width/2,.009)]
        loft([(p+u*(z0-centre),tangent,n),(p+u*(z1-centre),tangent,n)],profile,WOOD)

for depth in TRUSSES:
    # Continuous rolled I-section from spring to spring. Cap plates conceal the field splices.
    arch(depth,.090,0,math.pi,72,i_section(.153,.182,.019,.024),IRON)
    for join in (math.pi/4,math.pi/2,3*math.pi/4):
        arch(depth,.174,join-.014,join+.014,3,rect(.178,.028),IRON)
    bar((-5.62,depth,5.72),(5.62,depth,5.72),i_section(.158,.163,.017,.021),IRON)
    # Warren webs; each top node is evaluated directly on the centreline of the curved chord.
    lower=(0,2.18,4.30,5.48)
    for side in (-1,1):
        for start,end in zip(lower,lower[1:]):
            x=side*(start+end)/2
            top=frame(angle_for_x(x),depth,.100)[0]
            for foot in (start,end):
                bar((side*foot,depth,5.745),top,rect(.063,.072),IRON)
            connector(top.x,depth,top.z)
        for x in (2.18,4.30,5.48):
            connector(side*x,depth,5.72)
        # Stanchion over the cap at the sidewall; upper chord and beam have a common seat.
        cap=(side*5.48,depth,5.72)
        bar(cap,frame(angle_for_x(side*5.48),depth,.09)[0],i_section(.117,.124,.014,.020),IRON)
    connector(0,depth,5.72)

# The middle luminaire is between the central trusses. A longitudinal saddle completes its load path.
bar((0,-2.03,5.77),(0,2.03,5.77),i_section(.105,.109,.014,.018),IRON,(1,0,0))
for depth in (-6,0,6):
    bar((-.117,depth,5.704),(.117,depth,5.704),rect(.144,.031),IRON)

# Sealed fanlights with a sill, a perimeter bar, radiating glazing bars and a concentric ring.
# Glazing is a closed lens-ended prism at each segment, supporting views from either end.
def glazepane(a,b,d):
    count=6
    sill=SPRING
    contour=[(0,sill)]
    for i in range(count+1):
        angle=a+(b-a)*i/count
        contour.append((-SPAN*math.cos(angle),sill+RISE*math.sin(angle)))
    loft([(Vector((0,d-.010,0)),Vector((1,0,0)),Vector((0,0,1))),
          (Vector((0,d+.010,0)),Vector((1,0,0)),Vector((0,0,1)))],contour,GLASS)


for depth in (-10,10):
    # Place the rebates centrally on the glass, with their beads visible from the hall.
    arch(depth,.044,0,math.pi,72,rect(.105,.075),IRON)
    bar((-6.2,depth,SPRING),(6.2,depth,SPRING),rect(.125,.094),IRON)
    for i in range(10):
        glazepane(i*math.pi/10,(i+1)*math.pi/10,depth)
    for i in range(1,10):
        angle=i*math.pi/10
        p=frame(angle,depth,.035)[0]
        bar((0,depth,SPRING),p,rect(.065,.052),IRON)
    arc_frames=[]
    for i in range(73):
        p,u,n=frame(math.pi*i/72,depth,0)
        p.x*=.43
        p.z=SPRING+(p.z-SPRING)*.43
        arc_frames.append((p,u,n))
    loft(arc_frames,rect(.081,.054),IRON)

bpy.ops.wm.read_factory_settings(use_empty=True)
mesh=bpy.data.meshes.new("HallVault")
mesh.from_pydata(positions,[],faces)
mesh.update()
for name,color in [("PaintedIron",(.065,.085,.078)),("LimePlaster",(.70,.64,.53)),
                   ("SeasonedWood",(.29,.13,.06)),("Glass",(.47,.63,.67))]:
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1)
    mesh.materials.append(mat)
uv=mesh.uv_layers.new(name="SurfaceMetres")
for face,coords,material,smooth in zip(mesh.polygons,uv_faces,material_ids,smooth_flags):
    face.material_index=material
    face.use_smooth=smooth
    for loop,p in zip(face.loop_indices,coords):
        uv.data[loop].uv=p

# Every extrusion is a sealed solid. Winding must face the hall on the underside of the liner.
bm=bmesh.new()
bm.from_mesh(mesh)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
assert all(e.is_manifold for e in bm.edges)
bm.to_mesh(mesh)
bm.free()
mesh.update()
mesh.calc_loop_triangles()
assert not mesh.validate() and all(tri.area>1e-10 for tri in mesh.loop_triangles)
obj=bpy.data.objects.new("HallVault",mesh)
bpy.context.collection.objects.link(obj)
obj.select_set(True)
bpy.context.view_layer.objects.active=obj
print("HallVault",len(mesh.loop_triangles),"triangles",len(mesh.uv_layers),"UV layer")
bpy.ops.export_scene.fbx(filepath=str(OUT),use_selection=True,object_types={"MESH"},
                         axis_forward="-Z",axis_up="Y",bake_anim=False,add_leaf_bones=False)
