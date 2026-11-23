"""Spin the pressed shade, rolled edging, fluted opal lens and mounting canopy in metres."""
from pathlib import Path
import math
import bpy
import bmesh

bpy.ops.wm.read_factory_settings(use_empty=True)
out = Path(__file__).resolve().parents[2] / "Assets/_Project/Art/Environment/M1_5/HallPendant.fbx"
verts, faces, slots, uv_faces = [], [], [], []


def spin(profile, slot, sides=72, flutes=0, center=(0,0), open_ends=True):
    """Revolve a closed edge section or end-capped outline; assign an unwrapped metric UV."""
    offset = len(verts)
    lengths = [0.]
    for i,(r,z,*amplitude) in enumerate(profile):
        if i:
            lengths.append(lengths[-1]+math.hypot(r-profile[i-1][0], z-profile[i-1][1]))
        for j in range(sides):
            angle=math.tau*j/sides
            radius=r+(amplitude[0] if amplitude else 0)*math.cos(flutes*angle)
            verts.append((center[0]+radius*math.cos(angle), center[1]+radius*math.sin(angle), z))
    for i in range(len(profile) if open_ends else len(profile)-1):
        nxt=(i+1)%len(profile)
        for j in range(sides):
            k=(j+1)%sides
            faces.append((offset+i*sides+j,offset+i*sides+k,offset+nxt*sides+k,offset+nxt*sides+j))
            slots.append(slot)
            u=j/sides; v=(j+1)/sides
            height=lengths[nxt] if nxt else lengths[-1]+.005
            uv_faces.append(((u,lengths[i]),(v,lengths[i]),(v,height),(u,height)))
    if not open_ends:
        for layer, reverse in [(0,True),(len(profile)-1,False)]:
            ids=list(range(offset+layer*sides,offset+(layer+1)*sides))
            if reverse:
                ids.reverse()
            faces.append(ids)
            slots.append(slot)
            uv_faces.append([(verts[idx][0],verts[idx][1]) for idx in ids])


# Baked profile has inside and outside surfaces, an annular aperture around the lens,
# and a rolled lip. No underside covers the original light below the glass.
spin([(.049,.146),(.064,.149),(.073,.143),(.076,.117),(.091,.107),
      (.112,.101),(.132,.093),(.159,.081),(.197,.057),(.234,.030),
      (.261,.020),(.289,.014),(.311,.013),(.327,.007),(.349,-.003),
      (.355,-.009),(.355,-.013),(.350,-.016),(.329,-.004),(.311,.004),
      (.28,.005),(.253,.012),(.221,.023),(.192,.040),(.151,.065),
      (.108,.084),(.074,.093),(.048,.108)],0)

# Solid-brass binding spun over the enamel rim.
spin([(.347,-.009),(.353,-.006),(.359,-.008),(.362,-.013),(.362,-.019),
      (.359,-.023),(.353,-.024),(.348,-.020),(.347,-.015)],1)

# Ribbed opal glass has a shallow stepped prismatic centre and a rounded shoulder.
spin([(.222,.025,0),(.243,.017,.001),(.252,-.006,.001),(.249,-.030,.0014),
      (.239,-.052,.0018),(.226,-.069,.0021),(.195,-.099,.0022),(.154,-.125,.002),
      (.116,-.141,.0017),(.088,-.147,.0011),(.076,-.147,0),(.071,-.151,0),
      (.066,-.152,0),(.062,-.148,0),(.044,-.155,0),(.018,-.162,0),(.004,-.162,0)],
     2,sides=128,flutes=32,open_ends=False)
# The glass retaining hoop is fixed to the shade by four brass thumb screws.
spin([(.246,.013),(.254,.012),(.258,.005),(.258,-.003),(.251,-.008),
      (.245,-.006),(.247,-.003)],1)
for i in range(4):
    theta=math.pi*(i+.5)/2
    center=(.258*math.cos(theta),.258*math.sin(theta))
    spin([(.005,-.011),(.008,-.011),(.010,-.008),(.010,-.003),(.007,.001),
          (.006,.007)],1,sides=12,center=center,open_ends=False)

# Lamp holder: knurled barrel, collar mouldings and separate sleeve.
spin([(.049,.139),(.068,.141),(.072,.149),(.071,.156),(.059,.158),
      (.054,.164),(.053,.196),(.056,.198),(.056,.202),(.048,.208),
      (.035,.211),(.034,.224),(.028,.227),(.026,.221),(.026,.152)],1)
spin([(.051,.165,.0004),(.055,.168,.0012),(.055,.190,.0012),(.051,.194,.0004),
      (.047,.194,0),(.047,.165,0)],1,sides=96,flutes=24)

# Flat cable collar, long suspension downrod and the compression joint.
spin([(.024,.221),(.031,.226),(.031,.236),(.023,.240),(.020,.249),
      (.015,.249),(.015,.222)],0,sides=36)
spin([(.012,.242),(.013,.248),(.013,1.81),(.011,1.82)],0,sides=32,open_ends=False)
spin([(.013,1.48),(.018,1.482),(.022,1.488),(.022,1.511),(.019,1.516),
      (.016,1.518),(.013,1.517)],1,sides=8)

# Spun mounting rose sits against the existing beam at the original 5.75 m elevation.
spin([(.016,1.795),(.025,1.795),(.029,1.8),(.029,1.808),(.027,1.814),
      (.038,1.820),(.052,1.824),(.063,1.832),(.076,1.849),
      (.087,1.859),(.103,1.864),(.111,1.866),(.114,1.872),(.114,1.884),
      (.108,1.89),(.016,1.89)],0)
spin([(.107,1.868),(.114,1.866),(.118,1.869),(.119,1.874),(.117,1.878),
      (.111,1.879),(.108,1.876)],1)
for i in range(2):
    center=(0,.090*(1 if i else -1))
    spin([(.009,1.862),(.009,1.859),(.006,1.856)],1,sides=10,center=center,open_ends=False)

mesh=bpy.data.meshes.new("HallPendant")
mesh.from_pydata(verts,[],faces)
mesh.update()
for name,color in [("PaintedIron",(.071,.096,.087)),("BrassFasteners",(.44,.29,.15)),
                   ("OpalGlass",(.94,.80,.55))]:
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1)
    mesh.materials.append(mat)
uv=mesh.uv_layers.new(name="Turning")
for face,slot,coords in zip(mesh.polygons,slots,uv_faces):
    face.material_index=slot
    face.use_smooth=len(face.vertices)==4
    for idx,coord in zip(face.loop_indices,coords):
        uv.data[idx].uv=coord

bm=bmesh.new()
bm.from_mesh(mesh)
assert all(e.is_manifold for e in bm.edges)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
bm.to_mesh(mesh)
bm.free()

obj=bpy.data.objects.new("HallPendant",mesh)
bpy.context.collection.objects.link(obj)
obj.select_set(True)
bpy.context.view_layer.objects.active=obj
bpy.ops.export_scene.fbx(filepath=str(out),use_selection=True,object_types={"MESH"},
                         axis_forward="-Z",axis_up="Y",bake_space_transform=True,bake_anim=False)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(out))
obj=next(o for o in bpy.context.scene.objects if o.type=="MESH")
m=obj.data
m.calc_loop_triangles()
world=[obj.matrix_world@v.co for v in m.vertices]
bounds=[(min(p[i] for p in world),max(p[i] for p in world)) for i in range(3)]
assert abs(bounds[2][1]-1.89)<.001 and abs(bounds[2][0]+.162)<.001
assert abs(bounds[0][1]-bounds[0][0]-.724)<.001
assert [s.name for s in m.materials]==["PaintedIron","BrassFasteners","OpalGlass"]
assert len(m.uv_layers)==1
print("Verified HallPendant",len(m.vertices),"vertices",len(m.loop_triangles),"triangles; bounds",bounds)
