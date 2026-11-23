"""Author the R1 hall threshold, railway boundary detail and surface maps in Blender."""
from math import pi, sin
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2] / "Assets/_Project/Art"
MODELS = ROOT / "Environment/M1_5"
MAPS = ROOT / "Textures/M1_5"


def begin():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"


def surface(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1)
    return mat


def finish_edges(obj, radius, mat):
    bevel = obj.modifiers.new("Eased edges", "BEVEL")
    bevel.width = radius
    bevel.segments = 3
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    obj.modifiers.new("Corner normals", "WEIGHTED_NORMAL")
    bpy.ops.object.modifier_apply(modifier="Corner normals")
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        for index in face.loop_indices:
            axes = [i for i in range(3) if i != max(range(3), key=lambda i: abs(face.normal[i]))]
            vertex = obj.matrix_world @ obj.data.vertices[obj.data.loops[index].vertex_index].co
            obj.data.uv_layers.active.data[index].uv = tuple(float(vertex[i]) for i in axes)
    return obj


def timber(label, location, size, radius, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = label
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish_edges(obj, radius, mat)


def pipe(label, location, radius, length, mat, tilt=0):
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=radius, depth=length, location=location)
    obj = bpy.context.object
    obj.name = label
    obj.rotation_euler.y = tilt
    return finish_edges(obj, min(radius*.28,.009), mat)


def export(name, max_triangles):
    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    obj.name = obj.data.name = name
    path = MODELS / f"{name}.fbx"
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={"MESH"},
                              axis_forward="-Z", axis_up="Y", bake_space_transform=True, bake_anim=False)
    slots = len(obj.data.materials)
    begin()
    bpy.ops.import_scene.fbx(filepath=str(path))
    model, = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    model.data.calc_loop_triangles()
    triangle_count = len(model.data.loop_triangles)
    assert len(model.material_slots) == slots and len(model.data.uv_layers) == 1
    assert triangle_count < max_triangles, triangle_count
    print(f"Verified {path.name}: {triangle_count:,} triangles, {slots} surfaces, measured size {tuple(model.dimensions)}.")


begin()
oak = surface("R1ThresholdOak", (.16,.093,.055))
iron = surface("R1HallIron", (.089,.102,.092))
stone = surface("R1LimeMasonry", (.36,.33,.268))
brass = surface("R1BrassFittings", (.42,.302,.128))

# Lower rails and brass push plates sit over the retained end-door fronts.
for side in (-1,1):
    x = side*.612
    for dx in (-.558,.558):
        timber("Beaded outer door stile", (x+dx,.00,1.255),(.082,.060,2.48),.012,oak)
        timber("Door inset bead", (x+dx-side*.043,.033,1.23),(.019,.034,2.40),.004,oak)
    for level in (.15,1.17,2.48):
        timber("Raised door cross rail", (x,.00,level),(1.13,.062,.114),.013,oak)
    timber("Recessed kick panel", (x,.018,.39),(.91,.044,.28),.020,oak)
    timber("Brass kick plate", (x,.045,.228),(.89,.012,.12),.008,brass)
    for level in (.193,.262):
        for dx in (-.401,.401):
            pipe("Rounded screw", (x+dx,.053,level),.006,.010,iron,pi/2)
    for dx in (-.034,.034):
        timber("Door push plate edge", (side*.18,.058+dx*.06,1.02),(.015,.015,.24),.004,brass)
for side in (-1,1):
    timber("Stone reveal", (side*1.35,-.016,1.305),(.145,.08,2.61),.017,stone)
    timber("Square return and stops", (side*1.247,.030,1.30),(.052,.079,2.6),.011,oak)
timber("Door head cornice", (0,.024,2.565),(2.825,.15,.104),.012,oak)
timber("Stone drip over door head", (0,.024,2.659),(2.934,.194,.099),.014,stone)

# Paired radiators add weight to the walls to either side of the quiet end doors.
for x in (-2.94,2.94):
    for dx in (-.57,.57):
        timber("Cast mounting foot", (x+dx,.28,.11),(.11,.32,.20),.023,iron)
        pipe("Hex end union", (x+dx,.31,.22),.057,.086,brass,pi/2)
    for dx in (-.48,-.32,-.16,0,.16,.32,.48):
        timber("Pressed cast radiator section", (x+dx,.24,.48),(.105,.204,.68),.046,iron)
        timber("Cast return rib", (x+dx,.352,.49),(.054,.046,.54),.020,iron)
    for level in (.22,.76):
        pipe("Radiator manifold", (x,.254,level),.052,1.25,iron,pi/2)
    pipe("Valve handwheel", (x-.66,.256,.84),.055,.016,iron)
    pipe("Riser and return", (x-.66,.256,.18),.028,.36,iron)
export("R1HallThreshold",24000)

begin()
coping = surface("R1ConcreteCoping", (.19,.22,.23))
masonry = surface("R1RailBoundary", (.14,.16,.16))
charcoal = surface("R1DistantRoof", (.075,.087,.094))

# The original boundary wall stays in service. Its close face receives lower
# footing, pier caps, and a continuous projecting sill and top coping.
timber("Low stepped footing", (.191,0,-.515),(.38,87.8,.40),.037,masonry)
timber("Pier footing cap", (.276,0,-.276),(.13,87.8,.072),.025,coping)
timber("Weathered wall coping", (-.10,0,1.979),(.85,88.4,.090),.026,coping)
for index in range(17):
    y = 42-index*5.3
    timber("Masonry buttress", (.477,y,.55),(.39,.68,2.78),.047,masonry)
    timber("Pier shoulder", (.493,y,1.946),(.46,.78,.13),.029,coping)
    timber("Edge of coping stone", (.501,y,2.069),(.52,.84,.128),.038,coping)
    timber("Pier foot", (.493,y,-.66),(.46,.80,.31),.041,coping)

# Dark service roofs beyond the boundary provide silhouettes at a second depth.
for x,y,w,length,level in [(-4.4,10.3,4.2,8.3,3.12),(-7.6,-.1,5.5,6.0,3.63),(-8.5,-13.3,4.6,5.8,3.31)]:
    timber("Service building volume", (x,y,level*.5), (w,length,level), .057,masonry)
    timber("Projecting roof slab", (x,y,level), (w+.46,length+.48,.204), .043,charcoal)
    timber("Upstand slab vent", (x-.62,y+length*.22,level+.30), (.59,.66,.63), .033,charcoal)
export("R1RailBoundary", 19000)


def read_pixels(path):
    img = bpy.data.images.load(str(path))
    w,h = img.size
    pixels = np.empty(w*h*4,dtype=np.float32)
    img.pixels.foreach_get(pixels)
    return pixels.reshape(h,w,4)


def save_png(name,pixels,linear):
    h,w,_ = pixels.shape
    img = bpy.data.images.new(name,width=w,height=h,alpha=True)
    if linear:
        img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(np.ascontiguousarray(pixels,dtype=np.float32).ravel())
    img.filepath_raw = str(MAPS / (name + ".png"))
    img.file_format = "PNG"
    img.save()
    assert img.filepath_raw and Path(img.filepath_raw).stat().st_size > 4096


terrazzo = read_pixels(MAPS / "Terrazzo/Base.jpg")
stone_rgb = terrazzo[...,:3]
tone = stone_rgb.mean(axis=(0,1))
stone_rgb[:] = np.clip(tone + .50*(stone_rgb-tone),0,1)
save_png("R1MutedTerrazzo",terrazzo,False)

# HDRP mask: metallic R, AO G, detail B, smoothness A. Smoothness is continuous
# across the longitudinal wrap; the transverse profile is clamped at import.
n = 1024
u = np.linspace(0,1,n,dtype=np.float32)
v = np.linspace(0,1,n,endpoint=False,dtype=np.float32)[:,None]
wet = np.clip((u-.05)/.80,0,1)
wet = wet*wet*(3-2*wet)
waver = .018*np.sin(2*pi*(2*v+.3*u))+.016*np.sin(2*pi*(5*v-.7*u))+.008*np.sin(2*pi*(9*v+.9*u))
wet_mask = np.ones((n,n,4),dtype=np.float32)
wet_mask[...,0] = 0
wet_mask[...,1] = .92
wet_mask[...,3] = .33 + wet*.29 + waver
save_png("R1WetApronMask",wet_mask,True)
