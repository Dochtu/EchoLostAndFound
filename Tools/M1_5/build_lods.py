"""Derive two geometric LODs from each of the three repeated hall fixtures."""
from pathlib import Path

import bpy

MODELS = Path(__file__).resolve().parents[2] / "Assets/_Project/Art/Environment/M1_5"
LOD_DIRECTORY = MODELS / "Detail"
LOD_DIRECTORY.mkdir(exist_ok=True)


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path))
    models = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    assert len(models) == 1, (path, len(models))
    model = models[0]
    bpy.context.view_layer.objects.active = model
    bpy.ops.object.select_all(action="DESELECT")
    model.select_set(True)
    return model


def dimensions(model):
    vertices = [model.matrix_world @ vertex.co for vertex in model.data.vertices]
    return [(min(p[axis] for p in vertices), max(p[axis] for p in vertices)) for axis in range(3)]


def triangles(model):
    model.data.calc_loop_triangles()
    return len(model.data.loop_triangles)


def slots(model):
    return [slot.material.name for slot in model.material_slots]


def export_lod(name, level, ratio, bake_space_transform):
    model = load(MODELS / f"{name}.fbx")
    expected_size, expected_slots, original_triangles = dimensions(model), slots(model), triangles(model)
    simplify = model.modifiers.new("Reduce topology for distance", "DECIMATE")
    simplify.ratio = ratio
    simplify.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=simplify.name)
    model.name = model.data.name = f"{name}_LOD{level}"
    target = LOD_DIRECTORY / f"{model.name}.fbx"
    bpy.ops.export_scene.fbx(
        filepath=str(target), use_selection=True, object_types={"MESH"},
        axis_forward="-Z",axis_up="Y",bake_space_transform=bake_space_transform,
        add_leaf_bones=False,bake_anim=False,
    )
    model = load(target)
    assert slots(model) == expected_slots, (target, slots(model), expected_slots)
    assert len(model.data.uv_layers), target
    assert set(polygon.material_index for polygon in model.data.polygons) == set(range(len(expected_slots))), target
    for actual, expected in zip(dimensions(model), expected_size):
        tolerance = max(.004, .045*(expected[1]-expected[0]))
        assert all(abs(a-b) <= tolerance for a,b in zip(actual, expected)), (target, actual, expected)
    simplified = triangles(model)
    assert simplified < original_triangles * (ratio+.07), (target, original_triangles, simplified)
    print(f"Verified {target.name}: {original_triangles:,} -> {simplified:,} triangles, {len(expected_slots)} slots")


for model_name, baked_axis in [("HallColumn",False),("HallSettee",False),("HallPendant",True)]:
    export_lod(model_name,1,.46,baked_axis)
    export_lod(model_name,2,.19,baked_axis)
