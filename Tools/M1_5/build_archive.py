"""Folded pasteboard cartons, tied folios and the enamel desk light in metres."""
import bpy, math, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_counter import Model,horizontal,outline
bpy.ops.wm.read_factory_settings(use_empty=True)
def panel(m, poly, z1,z2,mat):
    m.loft([[(x,y,z) for x,y in poly] for z in [z1,z2]],mat)
def rim(m,x,y,z,w,h,mat):
    coords=[(x,y,z+v) for v in []]
    v=[(x,y-w/2,z-h/2),(x,y+w/2,z-h/2),(x,y+w/2,z+h/2),(x,y-w/2,z+h/2),(x,y-w/2,z-h/2)]
    for a,b in zip(v,v[1:]):m.strap([a,b],.003,mat,8)
box=Model(["Leather","Paper","BrassFasteners","OldFabric"])
horizontal(box,[(0,.244,.171,.012),(.242,.248,.175,.014)],"Leather")
horizontal(box,[(.235,.252,.179,.015),(.253,.253,.180,.015),(.259,.249,.176,.013)],"OldFabric")
for s in [-1,1]:
    rim(box,s*.249,0,.16,.157,.060,"BrassFasteners")
    box.loft([[ (s*xx,y,z) for y,z in [(-.073,.135),(.073,.135),(.073,.185),(-.073,.185)]] for xx in [.249,.251]],"Paper")
    box.strap([(s*.248,-.053,.11),(s*.26,-.043,.092),(s*.264,.04,.092),(s*.248,.053,.11)],.005,"BrassFasteners")
box.save("ArchiveCarton")
folio=Model(["Paper","Leather","OldFabric","BrassFasteners"])
for k in range(4):
    z=k*.034
    for i in range(4):
        offset=.002*math.sin((i+3*k)*1.7)
        panel(folio,[(x+offset,y) for x,y in outline(.226,.153,.006)],z+i*.007,z+(i+1)*.007-.0003,"Paper")
    panel(folio,outline(.231,.158,.007),z+.028,z+.031,"Leather")
for y in [-.087,.087]:
    for i in [-.002,.002]:
        folio.strap([(-.224,y+i,.002),(-.231,y+i,.015),(-.231,y+i,.114),(-.219,y+i,.136),(.218,y+i,.136),(.233,y+i,.129),(.233,y+i,.013),(.220,y+i,.002)],.0023,"OldFabric")
folio.save("TiedFolios")
lamp=Model(["PaintedIron","BrassFasteners","OpalGlass"])
horizontal(lamp,[(0,.13,.093,.048),(.014,.132,.095,.05),(.024,.121,.085,.045),(.04,.096,.065,.036)],"PaintedIron")
for side in [-1,1]:
    lamp.strap([(0,side*.028,.038),(0,side*.028,.1),(0,side*.056,.28),(.022,side*.152,.34),(.064,side*.156,.402)],.009,"BrassFasteners",16)
for material,r,ang in [("PaintedIron",.106,2.0),("OpalGlass",.101,1.92)]:
    def sector(y):
        out=[(.067+math.sin(t/24*ang*2-ang)*r,y,.398+math.cos(t/24*ang*2-ang)*r) for t in range(25)]
        inn=[(.067+math.sin(t/24*ang*2-ang)*(r-.003),y,.398+math.cos(t/24*ang*2-ang)*(r-.003)) for t in reversed(range(25))]
        return out+inn
    lamp.loft([sector(-.165),sector(.165)],material)
for side in [-1,1]:
    lamp.strap([(.067+math.sin(t/24*4-2)*.106,side*.165,.398+math.cos(t/24*4-2)*.106) for t in range(25)],.005,"BrassFasteners")
lamp.save("IntakeLamp")
