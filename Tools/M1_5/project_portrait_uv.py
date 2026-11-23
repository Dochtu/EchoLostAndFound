import sys
import bpy
import numpy as np
from pathlib import Path
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
from mathutils import Vector
fbx,out=map(Path,sys.argv[sys.argv.index('--')+1:])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(fbx))
skin=bpy.data.objects['Skin'];s=skin.data;s.calc_loop_triangles()
sv=[skin.matrix_world@v.co for v in s.vertices]
tris=[t for t in s.loop_triangles]
bvh=BVHTree.FromPolygons(sv,[t.vertices for t in tris],all_triangles=True)
def projected(point):
    p,n,i,d=bvh.find_nearest(point)
    t=tris[i]
    coords=[Vector((*s.uv_layers.active.data[idx].uv,0)) for idx in t.loops]
    return barycentric_transform(p,*(sv[k] for k in t.vertices),*coords).xy,d

for name in ['Hair','Brows','Lashes']:
 o=bpy.data.objects[name];m=o.data
 world=[o.matrix_world@v.co for v in m.vertices]
 uvl=m.uv_layers.active.data
 m.calc_loop_triangles()
 trirows=[]
 for t in m.loop_triangles:
    row=[]
    for idx,j in zip(t.vertices,t.loops):
        uv,d=projected(world[idx])
        row.append([*uvl[j].uv,*uv,d,*world[idx]])
    trirows.append(row)
 np.save(out/(name+'_uv.npy'),np.array(trirows))
 if name!='Hair':continue
 edges={}
 for t in m.polygons:
    ids=list(t.loop_indices)
    for i,j in zip(ids,ids[1:]+ids[:1]):
        a,b=m.loops[i].vertex_index,m.loops[j].vertex_index
        edges.setdefault(tuple(sorted((a,b))),[]).append((i,j))
 lines=[]
 for (a,b),sides in edges.items():
    if len(sides)!=1:continue
    p=(world[a]+world[b])/2
    if p.y>-.045 or p.z<1.46 or p.z>1.60:continue
    if (world[a]-world[b]).length<.003:continue
    lines.append([list(uvl[i].uv) for i in sides[0]])
 np.save(out/'hair_boundary.npy',np.array(lines))
 print(name,len(lines),'boundary edges')
