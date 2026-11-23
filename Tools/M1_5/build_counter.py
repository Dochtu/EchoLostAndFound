"""Models the intake joinery and the sewn folio register. All lengths in metres."""
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parents[2] / "Assets/_Project/Art/Props/M1_5"


class Model:
    def __init__(self, palette):
        self.palette = palette
        self.vertices, self.faces, self.uv, self.slots, self.smooth = [], [], [], [], []

    def poly(self, indices, coordinates, slot, smooth=False):
        self.faces.append(indices)
        self.uv.append(coordinates)
        self.slots.append(self.palette.index(slot))
        self.smooth.append(smooth)

    def loft(self, rings, slot, smooth=False):
        count=len(rings[0])
        offset=len(self.vertices)
        for ring in rings:
            assert len(ring)==count
            self.vertices.extend(ring)
        perimeters=[[0] for _ in rings]
        heights=[[0]*count]
        for k, ring in enumerate(rings):
            for j in range(count):
                perimeters[k].append(perimeters[k][-1] + math.dist(ring[j],ring[(j+1)%count]))
            if k:
                heights.append([heights[-1][j]+math.dist(rings[k-1][j],ring[j]) for j in range(count)])
        for k in range(len(rings)-1):
            for j in range(count):
                i=(j+1)%count
                idx=offset+k*count
                face=(idx+j,idx+i,idx+count+i,idx+count+j)
                uv=((perimeters[k][j],heights[k][j]),(perimeters[k][j+1],heights[k][i]),
                    (perimeters[k+1][j+1],heights[k+1][i]),(perimeters[k+1][j],heights[k+1][j]))
                self.poly(face,uv,slot,smooth)
        for k in (0,len(rings)-1):
            # Omit the normal's dominant axis, keeping the two metric coordinates of the end grain.
            normal=mathutils_normal(rings[k])
            axes=sorted(range(3),key=lambda a: abs(normal[a]))[:2]
            cap=[offset+k*count+j for j in range(count)]
            self.poly(cap,[(p[axes[0]],p[axes[1]]) for p in rings[k]],slot)

    def strap(self,path,radius,slot,segments=10):
        rings=[]
        reference=Vector((1,0,0))
        first=(Vector(path[1])-Vector(path[0])).normalized()
        if abs(first.dot(reference))>.91:
            reference=Vector((0,1,0))
        for j,point in enumerate(path):
            tangent=(Vector(path[min(j+1,len(path)-1)])-Vector(path[max(0,j-1)])).normalized()
            u=(reference-tangent*reference.dot(tangent)).normalized()
            if u.length_squared < .1:
                u=tangent.cross(Vector((0,0,1))).normalized()
            v=tangent.cross(u).normalized()
            rings.append([Vector(point) + radius*(u*math.cos(i*math.tau/segments)+v*math.sin(i*math.tau/segments))
                          for i in range(segments)])
            reference=u
        self.loft(rings,slot,True)

    def save(self,name,extra_objects=()):
        mesh=bpy.data.meshes.new(name)
        mesh.from_pydata(self.vertices,[],self.faces)
        mesh.update()
        for name_ in self.palette:
            mesh.materials.append(bpy.data.materials.get(name_) or bpy.data.materials.new(name_))
        uv=mesh.uv_layers.new(name="SurfaceMetres")
        for poly,coords,slot,smooth in zip(mesh.polygons,self.uv,self.slots,self.smooth):
            poly.material_index=slot
            poly.use_smooth=smooth
            for idx,p in zip(poly.loop_indices,coords):
                uv.data[idx].uv=p
        bm=bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
        obj=bpy.data.objects.new(name,mesh)
        bpy.context.collection.objects.link(obj)
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active=obj
        obj.select_set(True)
        for part in extra_objects:
            part.select_set(True)
        if extra_objects:
            bpy.ops.object.join()
        mesh=obj.data
        mesh.calc_loop_triangles()
        assert not mesh.validate()
        assert len(mesh.uv_layers)==1
        assert all(t.area>1e-12 for t in mesh.loop_triangles)
        print(name,len(mesh.loop_triangles),"triangles; bounds",tuple(round(v,3) for v in obj.dimensions),flush=True)
        OUT.mkdir(parents=True,exist_ok=True)
        bpy.ops.export_scene.fbx(filepath=str(OUT/(name+".fbx")),use_selection=True,object_types={"MESH"},
                                  axis_forward="-Z",axis_up="Y",bake_anim=False,add_leaf_bones=False)
        bpy.data.objects.remove(obj,do_unlink=True)


def mathutils_normal(points):
    from mathutils.geometry import normal
    return normal([Vector(p) for p in points])


def outline(a,b,r,n=4):
    """Rounded rectangle centred on the origin, counterclockwise."""
    corners=[(a-r,b-r),(-a+r,b-r),(-a+r,-b+r),(a-r,-b+r)]
    return [(x+r*math.cos((c+j/n)*math.pi/2),y+r*math.sin((c+j/n)*math.pi/2))
            for c,(x,y) in enumerate(corners) for j in range(n+1)]


def horizontal(m, sections, slot, centre=(0,0)):
    m.loft([[(centre[0]+x,centre[1]+y,z) for x,y in outline(a,b,r)] for z,a,b,r in sections],slot)


def face_panels(m,sections,y,z,side,slot):
    m.loft([[(side*x,y+u,z+v) for u,v in outline(w/2,h/2,rad)]
            for x,w,h,rad in sections],slot)


def cabinet():
    m=Model(["SeasonedWood","DarkWood","PaintedIron","BrassFasteners"])
    # Recessed toe kick and a moulded bottom rail, raised clear of wash water.
    horizontal(m,[(0,.519,1.715,.022),(.016,.529,1.721,.022),(.038,.548,1.754,.020),(.095,.548,1.754,.020),
                  (.108,.562,1.776,.024),(.127,.568,1.781,.024),(.142,.553,1.769,.020)],"PaintedIron")
    horizontal(m,[(.132,.529,1.757,.017),(.881,.529,1.757,.017)],"DarkWood")
    for side in (-1,1):
        for y in (-1.697,-.85,0,.85,1.697):
            face_panels(m,[(.520,.085,.734,.005),(.559,.085,.734,.005),(.564,.079,.730,.004)],
                        y,.51,side,"SeasonedWood")
        for y in (-1.276,-.425,.425,1.276):
            # A raised field with a stepped tongue and ogee moulding around each door.
            face_panels(m,[(.526,.755,.443,.009),(.549,.755,.443,.009),(.554,.747,.433,.008),
                           (.552,.724,.413,.008),(.539,.704,.394,.006),(.541,.667,.357,.006),
                           (.553,.628,.318,.008),(.556,.622,.312,.008)],y,.405,side,"SeasonedWood")
            face_panels(m,[(.524,.763,.178,.008),(.555,.763,.178,.008),(.567,.744,.159,.006)],
                        y,.772,side,"SeasonedWood")
            # Cast bail with two rosettes and a bowed central grip.
            for sign in (-1,1):
                e=y+sign*.090
                face_panels(m,[(.563,.052,.048,.016),(.573,.052,.048,.016),(.577,.043,.040,.013)],
                            e,.782,side,"BrassFasteners")
            m.strap([(side*(.574+.034*math.sin(t*math.pi/16)),y-.09+.18*t/16,
                      .782-.024*math.sin(t*math.pi/16)) for t in range(17)],.0078,"BrassFasteners")
        for z,h in ((.179,.071),(.663,.055),(.892,.075)):
            face_panels(m,[(.525,3.48,h,.007),(.560,3.48,h,.007),(.565,3.474,h-.006,.006)],
                        0,z,side,"DarkWood")
    # Matched glued boards beneath a continuous radiused writing edge with inset brass fillet.
    horizontal(m,[(.905,.580,1.815,.035),(.915,.586,1.821,.037),(.921,.610,1.845,.050),
                  (.928,.622,1.863,.058),(.935,.625,1.870,.064),(.963,.625,1.870,.064),
                  (.978,.622,1.867,.062),(.986,.617,1.862,.060)],"DarkWood")
    horizontal(m,[(.938,.6254,1.8704,.064),(.945,.6254,1.8704,.064)],"BrassFasteners")
    horizontal(m,[(.982,.614,1.858,.057),(.994,.612,1.856,.055),
                  (1,.604,1.848,.051)],"SeasonedWood")
    m.save("IntakeCabinet")


def register():
    m=Model(["OldFabric","Leather","Paper"])
    for z in (-.010,.038):
        horizontal(m,[(z,.191,.263,.006),(z+.001,.195,.265,.007),
                      (z+.005,.195,.265,.007),(z+.006,.192,.263,.006)],"OldFabric")
    # Folded signatures have differently recessed fore-edges; keep cover overhang on three sides.
    for i in range(15):
        z=-.0036+i*.00274
        wave=.0007*math.sin(i*2.37)
        horizontal(m,[(z,.186+wave,.256,.0025),(z+.0019,.188+wave,.2565,.003),
                      (z+.0027,.187+wave,.256,.0025)],"Paper",(.001,0))
    # A round-backed spine with small raised sewing cords, flush with the cover joints.
    profile=[(-.179,-.009),(-.193,-.010),(-.201,-.006),(-.205,.004),
             (-.206,.027),(-.203,.037),(-.196,.043),(-.179,.044)]
    m.loft([[(x,y,z) for x,z in profile] for y in (-.264,.264)],"Leather")
    for y in (-.206,-.147,.147,.206):
        p=[(x-.0017 if x<-.192 else x,z) for x,z in profile]
        m.loft([[(x,yy,z) for x,z in p] for yy in (y-.003,y+.003)],"Leather")
    for side in (-1,1):
        # Worn triangular leather corners on the upper board.
        xy=[(.194,side*.258),(.190,side*.264),(.116,side*.264),(.194,side*.184)]
        m.loft([[(x,y,z) for x,y in xy] for z in (.0433,.045)],"Leather")
    m.save("BoundRegister")


if __name__=="__main__":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    cabinet()
    register()
