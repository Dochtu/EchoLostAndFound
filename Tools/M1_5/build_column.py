"""Author the fluted waiting-room stanchion to the existing spring-beam datum."""
from math import cos, sin, pi, tau, hypot
from pathlib import Path

import bpy


OUTPUT = Path(__file__).resolve().parents[2] / "Assets/_Project/Art/Environment/M1_5/HallColumn.fbx"
bpy.ops.wm.read_factory_settings(use_empty=True)
parts = []
iron = bpy.data.materials.new("PaintedIron")
iron.diffuse_color = (.065, .085, .078, 1)
brass = bpy.data.materials.new("BrassFasteners")
brass.diffuse_color = (.48, .32, .16, 1)


def turned(name, sections, sides, material, flutes=0, location=(0, 0, 0)):
    """Cast profile with outward winding, open UV seam and independently mapped end caps."""
    verts, faces, maps = [], [], []
    distance = 0
    vcoords = []
    for i, (z, r, depth) in enumerate(sections):
        if i:
            distance += hypot(z-sections[i-1][0], r-sections[i-1][1])
        vcoords.append(distance)
        for j in range(sides):
            angle = tau*j/sides
            radius = r - depth * ((1+cos(angle*flutes))*.5)**.75
            verts.append((radius*cos(angle), radius*sin(angle), z))
    circumference = tau * max(s[1] for s in sections)
    for i in range(len(sections)-1):
        for j in range(sides):
            a = i*sides+j
            b = i*sides+(j+1)%sides
            faces.append((a, b, b+sides, a+sides))
            u0, u1 = circumference*j/sides, circumference*(j+1)/sides
            maps.append(((u0,vcoords[i]), (u1,vcoords[i]), (u1,vcoords[i+1]), (u0,vcoords[i+1])))
    bottom = tuple(reversed(range(sides)))
    top = tuple(range(len(verts)-sides, len(verts)))
    for cap in (bottom, top):
        faces.append(cap)
        maps.append([(verts[index][0], verts[index][1]) for index in cap])

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    uvs = mesh.uv_layers.new(name="SurfaceMetres")
    for poly, uv in zip(mesh.polygons, maps):
        poly.use_smooth = poly.index < len(faces)-2 and sides > 12
        for index, coord in zip(poly.loop_indices, uv):
            uvs.data[index].uv = coord
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.data.materials.append(material)
    parts.append(obj)
    return obj


def flange(name, elevation, width, depth, thickness, radius):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, elevation + thickness/2))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = (width, depth, thickness)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    fillet = obj.modifiers.new("Foundry fillet", "BEVEL")
    fillet.width = radius
    fillet.segments = 3
    bpy.ops.object.modifier_apply(modifier=fillet.name)
    normals = obj.modifiers.new("Face weighted normals", "WEIGHTED_NORMAL")
    bpy.ops.object.modifier_apply(modifier=normals.name)
    obj.data.uv_layers.active.name = "SurfaceMetres"
    obj.data.materials.append(iron)
    parts.append(obj)


def stud(x, y, z):
    turned("Washer", [(0,.025,0),(.003,.028,0),(.008,.028,0),(.010,.025,0)],
           16, iron, location=(x,y,z))
    turned("Hexagonal nut", [(.009,.018,0),(.012,.024,0),(.032,.024,0),(.036,.019,0)],
           6, brass, location=(x,y,z))


# Shallow, square mounting steps enclose the existing 720 mm masonry pedestal.
flange("Plinth foot", 0, .765,.765,.065,.010)
flange("Plinth waist", .047, .739,.739,.205,.007)
flange("Plinth cap", .239, .772,.772,.053,.009)
for x in (-.325,.325):
    for y in (-.325,.325):
        stud(x,y,.292)

# The troughs clear the original 450 mm shaft. The flute ends run out into the two collars.
turned("Turned heel", [
    (.286,.366,0),(.295,.371,0),(.319,.371,0),(.330,.363,0),(.346,.339,0),
    (.360,.327,0),(.380,.326,0),(.390,.342,0),(.406,.346,0),(.420,.336,0),
    (.444,.309,0),(.474,.281,0),(.505,.267,0),(.528,.265,0),(.541,.270,0),
    (.557,.270,0),(.566,.265,0)], 64,iron)
turned("Raised collar",[(.558,.265,0),(.564,.272,0),(.581,.272,0),(.586,.265,0)],
       64, brass)
turned("Sixteen stopped flutes", [
    (.579,.263,0),(.598,.265,0),(.617,.257,0),(.651,.248,.001),
    (.704,.248,.011),(.759,.250,.018),(2.45,.243,.019),
    (4.74,.219,.017),(4.85,.219,.012),(4.91,.217,.002),
    (4.94,.218,0),(4.953,.235,0),(4.968,.241,0),(4.986,.241,0),
    (4.998,.233,0),(5.010,.233,0)], 96,iron,flutes=16)
turned("Head collar", [(5.002,.234,0),(5.009,.245,0),(5.034,.245,0),(5.041,.241,0)],
       64,brass)

# The lobed bell opens in two stages under the architrave with a bead at either shoulder.
turned("Pressed leaf capital", [
    (5.031,.238,0),(5.047,.250,0),(5.064,.250,0),(5.079,.239,0),
    (5.11,.258,.004),(5.15,.287,.011),(5.21,.332,.024),(5.27,.378,.031),
    (5.335,.420,.023),(5.357,.425,.008),(5.373,.427,0),(5.384,.442,0),
    (5.399,.448,0),(5.419,.448,0),(5.430,.438,0),(5.439,.418,0),
    (5.452,.414,0),(5.465,.421,0),(5.478,.430,0)], 96,iron,flutes=12)
flange("Abacus lower bead",5.474,.862,.862,.046,.016)
flange("Abacus upper table",5.513,.878,.878,.064,.009)
flange("Beam shoe",5.569,.558,.362,.080,.011)
flange("Bolted beam flange",5.638,.752,.486,.054,.009)
for x in (-.318,.318):
    for y in (-.189,.189):
        stud(x,y,5.692)

bpy.ops.object.select_all(action="DESELECT")
for obj in parts:
    obj.select_set(True)
bpy.context.view_layer.objects.active = parts[0]
bpy.ops.object.join()
model = bpy.context.object
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
model.name = model.data.name = "HallColumn"
model.data.calc_loop_triangles()
assert len(model.data.uv_layers) == 1 and {m.name for m in model.data.materials} == {"PaintedIron", "BrassFasteners"}
assert not model.data.validate()
assert all(tri.area > 1e-12 for tri in model.data.loop_triangles)
assert min(v.co.z for v in model.data.vertices) >= -1e-5
print("HallColumn", tuple(round(v,3) for v in model.dimensions), len(model.data.loop_triangles), "triangles")
bpy.ops.export_scene.fbx(filepath=str(OUTPUT), use_selection=True, object_types={"MESH"},
                          axis_forward="-Z", axis_up="Y", bake_anim=False, add_leaf_bones=False)
