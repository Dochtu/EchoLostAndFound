"""Fabricate a four-metre rail panel and a five-metre platform canopy bay in metres."""
from pathlib import Path
import math, sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_counter as stock
stock.OUT=Path(__file__).resolve().parents[2]/"Assets/_Project/Art/Environment/M1_5"
bpy.ops.wm.read_factory_settings(use_empty=True)

def along_y(model,section,ys,mat):
    model.loft([[(x,y,z) for x,z in section] for y in ys],mat)

rail=stock.Model(["DarkWood","PaintedIron","RunningSteel"])
profile=[(-.073,0),(.073,0),(.073,.012),(.019,.025),(.009,.036),(.008,.115),(.015,.13),(.034,.134),(.036,.15),(.031,.165),(.022,.169),(-.022,.169),(-.031,.165),(-.036,.15),(-.034,.134),(-.015,.13),(-.008,.115),(-.009,.036),(-.019,.025),(-.073,.012)]
for x in (-.7175,.7175):
    along_y(rail,[(x+u,.166+v) for u,v in profile],[-2,2],"RunningSteel")
for i in range(5):
    y=-1.6+i*.8
    stock.horizontal(rail,[(0,1.28,.122,.018),(.129,1.26,.117,.024),(.148,1.24,.102,.026)],"DarkWood",(0,y))
    for side in (-1,1):
        x=side*.7175
        stock.horizontal(rail,[(.148,.134,.083,.011),(.167,.13,.079,.012)],"PaintedIron",(x,y))
        for sign in (-1,1):
            rail.strap([(x+sign*.114,y-.036,.158),(x+sign*.116,y-.012,.202),(x+sign*.085,y+.032,.212),(x+sign*.055,y+.024,.182)],.010,"PaintedIron",8)
rail.save("PlatformRailPanel")
bay=stock.Model(["PaintedIron","RunningSteel","BrassFasteners"])
# Slight fall towards the track, individually folded standing seams.
for i in range(21):
    x=-2.96+i*.282
    z=4.26-(x+2.96)*.069
    sec=[(x,z),(x+.252,z-.017),(x+.26,z+.028),(x+.278,z+.029),(x+.28,z+.017),(x+.267,z+.016),(x+.261,z-.025),(x,z-.01)]
    along_y(bay,sec,[-2.5,2.5],"PaintedIron")
# Continuous folded underlayment seals each standing seam against driving rain.
along_y(bay,[(-2.96,4.231),(2.96,3.823),(2.96,3.812),(-2.96,4.220)],[-2.5,2.5],"PaintedIron")
# Half-round rain gutter, rolled outer lip and two cast hangers.
def gutter(y,rad):
    return [(3.04+math.cos(math.pi*t/18)*rad,y,3.85-math.sin(math.pi*t/18)*rad) for t in range(19)]
section=gutter(0,.122)+list(reversed(gutter(0,.112)))
along_y(bay,[(x,z) for x,_,z in section],[-2.5,2.5],"RunningSteel")
for y in [-1.8,1.8]:
    bay.strap(gutter(y,.128),.012,"PaintedIron",8)
bay.strap([(3.162,-2.5,3.85),(3.162,2.5,3.85)],.012,"RunningSteel",10)
# Pierced front and rear cantilever ribs, seated on a flanged post.
for side,reach in [(1,3),(-1,2.86)]:
    x0=-.73
    def rib(pts,r):
        bay.strap([(x0+side*x,0,z) for x,z in pts],r,"PaintedIron",12)
    rib([(0,3.1),(.24,3.34),(.59,3.60),(1.2,3.82),(reach-side*x0,4.025-side*.20)],.046)
    rib([(0,4.04),(reach-side*x0,4.025-side*.20)],.055)
    for j in range(3):
        x=.30+j*.45
        rib([(x,3.41+j*.18),(x+.28,4.02-j*.025)],.024)
rings=[[( -.73+math.cos(a*math.tau/32)*r, math.sin(a*math.tau/32)*r,z) for a in range(32)] for z,r in [(0,.26),(.09,.26),(.15,.19),(.30,.17),(3.64,.113),(3.70,.15),(3.79,.21),(4.03,.23)]]
bay.loft(rings,"PaintedIron",True)
bay.save("PlatformCanopyBay")

