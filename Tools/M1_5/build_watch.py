"""Build the E01 watch in Blender 4.5. Dimensions throughout are metres."""
from math import atan2, cos, exp, pi, radians, sin, tau
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

TARGET = Path(__file__).resolve().parents[2] / "Assets/_Project/Art/Props/M1_5/EvidenceWatch.fbx"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = "METRIC"


def material(name, rgb, metal=0, roughness=.45):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*rgb, 1)
    shader.inputs["Metallic"].default_value = metal
    shader.inputs["Roughness"].default_value = roughness
    return mat


brass = material("Watch_SatinBrass", (.48,.30,.12), .91, .35)
polished = material("Watch_PolishedBrass", (.56,.36,.16), .95, .21)
dark = material("Watch_Patina", (.11,.072,.037), .83, .57)
steel = material("Watch_BluedSteel", (.042,.064,.086), .93, .28)
enamel = material("Watch_IvoryEnamel", (.83,.73,.568), 0, .35)
ink = material("Watch_DialInk", (.047,.036,.026), 0, .66)
stamp = material("Watch_EngravingRecess", (.11,.070,.037), .65, .59)
glass = material("Watch_Crystal", (.96,.982,.99), 0, .08)


def mesh(name, vertices, polygons, mat, smooth=False):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], polygons)
    data.update()
    bm = bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(data)
    bm.free()
    data.update()
    uv = data.uv_layers.new(name="Surface")
    for face in data.polygons:
        face.use_smooth = smooth
        orientation = max(range(3), key=lambda i: abs(face.normal[i]))
        axes = [i for i in range(3) if i != orientation]
        for index in face.loop_indices:
            point = data.vertices[data.loops[index].vertex_index].co
            uv.data[index].uv = tuple(point[i] / .0552 + .5 for i in axes)
    data.materials.append(mat)
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    return obj


def rings(name, sections, mat, closed=False, smooth=True):
    count = len(sections[0])
    vertices = [vertex for section in sections for vertex in section]
    polygons = []
    for section in range(len(sections) if closed else len(sections)-1):
        start = section * count
        following = (section+1) % len(sections) * count
        for i in range(count):
            j = (i+1) % count
            polygons.append((start+i, start+j, following+j, following+i))
    if not closed:
        polygons.append(tuple(reversed(range(count))))
        end = (len(sections)-1) * count
        polygons.append(tuple(end+i for i in range(count)))
    return mesh(name, vertices, polygons, mat, smooth)


def turned(name, profile, mat, origin=(0,0,0), axis=(0,0,1), sides=128, closed=False, dent=None):
    normal = Vector(axis).normalized()
    tangent = Vector((1,0,0))
    tangent = (tangent-normal*normal.dot(tangent)).normalized()
    bitangent = normal.cross(tangent)
    sections = []
    for section, (height, radius) in enumerate(profile):
        ring = []
        for i in range(sides):
            angle = i*tau/sides
            distance = dent(section,radius,angle) if dent else radius
            radial = tangent*cos(angle)+bitangent*sin(angle)
            ring.append(tuple(Vector(origin)+normal*height+radial*distance))
        sections.append(ring)
    return rings(name, sections, mat, closed)


def ring(name, radius, cross, mat, height=0):
    profile = [(height+cross*sin(tau*i/10), radius+cross*cos(tau*i/10)) for i in range(10)]
    return turned(name, profile, mat, closed=True)


def oval_link(name, position, major, minor, wire, yaw, tilt, mat, sides=32):
    across = Vector((cos(yaw),sin(yaw),0))
    side = Vector((-sin(yaw)*cos(tilt), cos(yaw)*cos(tilt), sin(tilt)))
    normal = across.cross(side)
    rings_ = []
    for point in range(sides):
        angle = point*tau/sides
        center = Vector(position)+across*(major*cos(angle))+side*(minor*sin(angle))
        outward = (across*(cos(angle)/major)+side*(sin(angle)/minor)).normalized()
        rings_.append([tuple(center+(outward*cos(j*tau/8)+normal*sin(j*tau/8))*wire)
                       for j in range(8)])
    return rings(name, rings_, mat, closed=True)


def prism(name, outline, level, depth, mat):
    lower = [(x,y,level) for x,y in outline]
    upper = [(x,y,level+depth) for x,y in outline]
    return rings(name,[lower,upper],mat,smooth=False)


def clock_position(degree, radius):
    # FBX +Y is up and Blender's negative Y points to Unity XII (+Z).
    angle = radians(degree)
    return -radius*sin(angle), -radius*cos(angle)


def mark(name, degree, inner, outer, half_width, level, mat):
    ix, iy = clock_position(degree,inner)
    ox, oy = clock_position(degree,outer)
    dx, dy = clock_position(degree+90,half_width)
    return prism(name,[(ix-dx,iy-dy),(ox-dx,oy-dy),(ox+dx,oy+dy),(ix+dx,iy+dy)],level,.000025,mat)


def text(name, body, height, point, mat, front):
    # The built-in Blender font is converted to geometry; no text runtime dependency.
    font = bpy.data.curves.new(name, "FONT")
    font.body = body
    font.align_x = "CENTER"
    font.align_y = "CENTER"
    font.size = height
    font.space_character = 1.10
    font.resolution_u = 7
    font.extrude = .000035 if front else .00023
    obj = bpy.data.objects.new(name, font)
    bpy.context.collection.objects.link(obj)
    obj.location = point
    if front:
        obj.rotation_euler.z = pi
    else:
        obj.rotation_euler.x = pi
    obj.data.materials.append(mat)
    return obj


case = turned("Spun brass case", [
    (-.00583,.00008),(-.00583,.0228),(-.00576,.0249),(-.00535,.02587),
    (-.0048,.02662),(-.00406,.02732),(-.0034,.02755),(-.0016,.0276),
    (.00148,.0276),(.00215,.02751),(.0028,.02719),(.00325,.02683),
    (.00356,.02643),(.00359,.0252),(.00275,.02445),(.00263,.00008)], brass)
turned("Bezel rebate and polished rolled lip", [
    (.00315,.02428),(.00343,.02572),(.00362,.0265),(.00403,.02640),
    (.00446,.02617),(.00476,.02579),(.00491,.0253),(.00490,.02455),
    (.00479,.02426),(.00454,.02408),(.00428,.02402),(.0042,.02423)], polished, closed=True)
for name, radius, cross, height, mat in [
    ("Lid hairline",.02547,.00011,-.00575,dark),
    ("Rolled lower case rim",.0252,.00018,-.00597,polished),
    ("Bezel hairline",.02643,.000115,.00348,dark),
    ("Crystal seat",.02416,.00015,.00452,dark),
    ("Enamel retaining fillet",.02353,.00016,.00363,polished),
]:
    ring(name,radius,cross,mat,height)

back = turned("Engraved spun dust cover", [
    (-.0071,.00009),(-.0071,.02243),(-.00706,.02332),(-.00689,.02421),
    (-.00663,.02503),(-.00629,.02547),(-.00604,.02554),(-.00582,.02535),
    (-.00581,.00009)], brass)
ring("Caseback chased inner border",.0148,.000075,dark,-.00708)
ring("Caseback chased outer border",.01795,.000065,dark,-.00708)
ring("Caseback turn line",.02361,.00008,polished,-.007025)

engraving = [
    text("Engraved_0412_middle_dot_0916","0412·0916",.00585,(0,-.001,-.00718),stamp,False),
    text("Steel_stamp_QH-283","QH-283",.00334,(0,.0204,-.00718),stamp,False),
]
for cutter in engraving:
    bpy.ops.object.select_all(action="DESELECT")
    cutter.select_set(True)
    bpy.context.view_layer.objects.active = cutter
    bpy.ops.object.convert(target="MESH")
    cutter = bpy.context.object
    cutter_mesh = bmesh.new()
    cutter_mesh.from_mesh(cutter.data)
    bmesh.ops.remove_doubles(cutter_mesh,verts=list(cutter_mesh.verts),dist=.00000005)
    bmesh.ops.recalc_face_normals(cutter_mesh,faces=list(cutter_mesh.faces))
    if cutter_mesh.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(cutter_mesh,faces=list(cutter_mesh.faces))
    assert all(edge.is_manifold for edge in cutter_mesh.edges), cutter.name
    cutter_mesh.to_mesh(cutter.data)
    cutter_mesh.free()
    # True recessed lettering. The trimmed duplicate lies against the cut floor.
    bpy.context.view_layer.objects.active = back
    back.select_set(True)
    cutter.select_set(False)
    recess = back.modifiers.new(cutter.name,"BOOLEAN")
    recess.operation = "DIFFERENCE"
    recess.solver = "MANIFOLD"
    recess.object = cutter
    faces = len(back.data.polygons)
    bpy.ops.object.modifier_apply(modifier=recess.name)
    assert len(back.data.polygons) > faces, cutter.name
    for vertex in cutter.data.vertices:
        vertex.co.z = vertex.co.z*.05-.000212
    duplicate_normals = bmesh.new()
    duplicate_normals.from_mesh(cutter.data)
    bmesh.ops.recalc_face_normals(duplicate_normals,faces=list(duplicate_normals.faces))
    duplicate_normals.to_mesh(cutter.data)
    duplicate_normals.free()

# A machined plane does not share averaged normals with the engraved walls.
for polygon in back.data.polygons:
    polygon.use_smooth = polygon.center.xy.length > .0231

turned("Ivory vitreous enamel dial", [
    (.00283,.00008),(.00283,.02341),(.00306,.02362),(.00328,.02355),
    (.00343,.02338),(.00349,.02194),(.00354,.0204),(.00357,.00008)], enamel)
for radius, cross in ((.02111,.000058),(.02276,.000074)):
    ring("Printed chapter rule",radius,cross,ink,.00353)
for i in range(60):
    strong = i%5 == 0
    mark(f"Chapter mark {i:02d}",i*6, .02115 if strong else .02158,
         .02269,.000201 if strong else .000094,.003545,ink)
roman = ["XII","I","II","III","IV","V","VI","VII","VIII","IX","X","XI"]
for i, numeral in enumerate(roman):
    x,y = clock_position(i*30,.01758)
    text("Chapter_"+numeral,numeral,.0037,(x,y,.00362),ink,True)
for radius, cross in ((.00451,.000045),(.00516,.000037)):
    ring("Turned centre surround",radius,cross,polished,.003619)


def pointer(name, degree, length, width, level):
    profile = [(-.0030,0),(-.0022,-.00038),(-.00092,-.00049),(.0011,-width*.32),
               (length*.43,-width*.30),(length*.60,-width*.50),(length*.86,-width*.24),
               (length,0),(length*.86,width*.24),(length*.60,width*.50),
               (length*.43,width*.30),(.0011,width*.32),(-.00092,.00049),(-.0022,.00038)]
    base = Vector(clock_position(degree,1))
    side = Vector(clock_position(degree+90,1))
    outer = [tuple(base*lengthwise+side*across) for lengthwise,across in profile]
    strip = prism(name,outer,level,.00019,steel)
    mod = strip.modifiers.new("Polished hand edge","BEVEL")
    mod.width = .000055
    mod.segments = 2
    return strip


pointer("HourHand_278.5deg",278.5,.01145,.00146,.00402)
pointer("MinuteHand_102deg",102,.01825,.00102,.00438)
turned("Centre pin and washer",[(.00362,.00078),(.00407,.00107),(.00452,.00104),
      (.00467,.00086),(.00478,.00064),(.00481,.00008)],polished,sides=48)

# Two opposed surfaces form the slightly convex, separate watch crystal.
turned("Domed mineral crystal", [
    (.00467,.00008),(.00464,.0130),(.00453,.0196),(.00437,.02333),(.00446,.02390),
    (.00475,.0240),(.00502,.02382),(.00532,.02294),(.00561,.0202),
    (.00584,.0160),(.00600,.0100),(.00607,.0050),(.00610,.00008)],glass)

# The exposed shaft leans away from its original bore. Knurling flattens locally
# where the impact deformed the crown; the rest of the perimeter remains machined.
crown = (0,-.0261,-.00054)
axis = (.245,-.949,.20)
turned("Bent winding shaft", [(-.0011,.00137),(.00065,.00144),
      (.00121,.00104),(.00331,.00105),(.00340,.00008)],steel,crown,axis,sides=48)
turned("Crown collar", [(-.0005,.00179),(-.00022,.00216),
      (.00048,.00210),(.00068,.00181),(.00073,.00008)],dark,crown,axis,sides=48)


def crown_impact(section, radius, angle):
    if radius < .001:
        return radius
    hit = max(0,cos(angle-.92))**12
    knurl = .000205*cos(28*angle)*(1-.93*hit) if section in (2,3,4) else 0
    return radius*(1-.31*hit)+knurl


turned("Dented knurled winding crown",
       [(.00229,.00008),(.00235,.00325),(.00291,.00394),(.00328,.00414),
        (.0050,.00411),(.00549,.00391),(.00573,.00342),(.00577,.00008)],
       brass,crown,axis,sides=168,dent=crown_impact)
oval_link("Forged winding bow",(-.0015,-.0338,.00037),.00655,.00516,.00068,0,0,brass,48)
oval_link("Bow to chain swivel",(-.0044,-.03865,-.00038),.0028,.00166,.00049,.60,.78,polished)

def chain_curve(t):
    one = 1-t
    controls = [(-.0045,-.0400),(-.0545,-.071),(-.092,-.029),(-.050,.019)]
    coefficients = [one**3, 3*one*one*t, 3*one*t*t, t**3]
    return Vector(tuple(sum(weight*point[i] for weight,point in zip(coefficients,controls)) for i in range(2)))


chain_pattern = []
last = chain_curve(0)
distance = 0
spacing = .00384
for step in range(1,401):
    point = chain_curve(step/400)
    direction = point-last
    distance += direction.length
    if distance >= spacing or not chain_pattern:
        index = len(chain_pattern)
        distance %= spacing
        tilt = radians(12 if index%2 == 0 else 69)
        height = -.0051+.00042*sin(tilt)+.0040*exp(-index*.38)
        yaw = atan2(direction.y,direction.x)
        oval_link(f"Soldered oval chain link {index+1:02d}",(point.x,point.y,height),
                  .00268,.00162,.00044,yaw,tilt,dark if index%7 == 4 else brass)
        chain_pattern.append(point)
    last = point
end = chain_pattern[-1]
oval_link("Chain split hook",(end.x+.0008,end.y+.0045,-.0058),.00404,.00235,.00057,1.02,.21,polished)
oval_link("Hook spring gate",(end.x+.0013,end.y+.0061,-.00543),.0022,.00101,.00029,1.02,.21,dark)

# Group high-frequency detail by material to keep the renderer count predictable.
def join_parts(parts, name):
    bpy.ops.object.select_all(action="DESELECT")
    for piece in parts:
        piece.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.join()
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bpy.context.object.name = name
    bpy.context.object.data.name = name


for mat in (ink,brass,polished,dark):
    parts = [obj for obj in bpy.context.scene.objects
             if obj is not back and obj.data.materials and obj.data.materials[0] is mat]
    join_parts(parts,mat.name.removeprefix("Watch_"))

bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.fbx(filepath=str(TARGET),use_selection=True,object_types={"MESH"},
                         axis_forward="-Z",axis_up="Y",bake_space_transform=True,bake_anim=False)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(TARGET))
objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
world = [obj.matrix_world@point.co for obj in objects for point in obj.data.vertices]
bounds = [(min(point[i] for point in world),max(point[i] for point in world)) for i in range(3)]
slots = sorted({slot.material.name for obj in objects for slot in obj.material_slots})
for obj in objects:
    obj.data.calc_loop_triangles()
    lowest = min((obj.matrix_world@vertex.co).z for vertex in obj.data.vertices)
    print(obj.name, "triangles", len(obj.data.loop_triangles), "min Z", lowest)
assert len(slots) == 8 and len(objects) == 12, (slots,[obj.name for obj in objects])
assert -.0072 <= bounds[2][0] <= -.0071 and abs(bounds[2][1]-.0061)<.00002, bounds
print("Verified FBX:",len(objects),"meshes;",sum(len(obj.data.loop_triangles) for obj in objects),"triangles")
print("Blender XYZ bounds in metres:",bounds)
print("Material slots:",slots)
