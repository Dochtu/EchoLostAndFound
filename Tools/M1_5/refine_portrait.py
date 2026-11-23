from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from scipy.ndimage import distance_transform_edt, gaussian_filter
import argparse
import subprocess
import tempfile

parser = argparse.ArgumentParser(description="Bake station visitor portrait textures using the authored MPFB FBX in metres.")
parser.add_argument("--blender", type=Path, required=True, help="Blender 4.5 executable")
parser.add_argument("--fbx", type=Path, required=True)
inputs_group=parser.add_mutually_exclusive_group(required=True)
inputs_group.add_argument("--source", type=Path, help="Fresh unprocessed output of build_character.py")
parser.add_argument("--output", type=Path, required=True)
inputs_group.add_argument("--cc0", type=Path, help="Extracted official MakeHuman CC0 system asset pack")
args=parser.parse_args()
src=(args.source or args.cc0).resolve()
out=args.output.resolve()
if out==src or args.cc0 and out==args.cc0.resolve():
    parser.error("choose a distinct output directory, preserving the source textures")
out.mkdir(parents=True, exist_ok=True)
inputs={label:src/(label+"_Color.png") for label in ("Skin","Hair","Brows","Lashes","Wardrobe")}
if args.cc0:
    rawfiles={
        "Skin":"skins/middleage_asian_male/middleage_lightskinned_male_diffuse2.png",
        "Hair":"hair/short02/short02_diffuse.png",
        "Brows":"eyebrows/eyebrow001/eyebrow001.png",
        "Lashes":"eyelashes/eyelashes01/eyelashes01.png",
        "Wardrobe":"clothes/male_casualsuit01/male_casualsuit01_diffuse.png"
    }
    inputs={key:args.cc0/path for key,path in rawfiles.items()}
wardrobe_base = (src/"clothes/male_casualsuit01/male_casualsuit01_ao.png" if args.cc0 else src/"Wardrobe_Mask.png")
for path in [args.fbx,args.blender,wardrobe_base,*inputs.values()]:
    if not path.is_file():
        parser.error(f"missing input {path}")
temp=tempfile.TemporaryDirectory(dir=out)
p=Path(temp.name)
subprocess.run([str(args.blender),"-b","--factory-startup","--python-exit-code","1","--python",str(Path(__file__).with_name("project_portrait_uv.py")),"--",str(args.fbx.resolve()),str(p)],check=True)
skin=np.array(Image.open(inputs['Skin']).convert('RGB'),dtype=np.float32)
N=skin.shape[0]
def to_pixel(uv,n):
    return np.stack((uv[...,0]*(n-1),(1-uv[...,1])*(n-1)),axis=-1)
for name,strength in [('Hair',.68),('Brows',.62),('Lashes',.17)]:
    source=np.asarray(Image.open(inputs[name]).convert('RGBA'),dtype=np.float32)/255.
    dest_alpha=np.zeros((N,N),np.float32)
    dest_color=np.zeros((N,N,3),np.float32)
    for tri in np.load(p/(name+'_uv.npy')):
        src_uv=to_pixel(tri[:,:2],source.shape[0])
        pts=to_pixel(tri[:,2:4],N)
        if tri[:,4].max()>(.026 if name=="Hair" else .014) or np.ptp(pts,axis=0).max()>115:continue
        lo=np.maximum(np.floor(pts.min(axis=0)).astype(int),0)
        hi=np.minimum(np.ceil(pts.max(axis=0)).astype(int),N-1)
        xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5)
        a,b,c=pts;u=b-a;v=c-a;det=u[0]*v[1]-u[1]*v[0]
        if abs(det)<1.e-7:continue
        w1=((xx-a[0])*v[1]-(yy-a[1])*v[0])/det
        w2=(u[0]*(yy-a[1])-u[1]*(xx-a[0]))/det
        mask=(w1>=0)&(w2>=0)&(w1+w2<=1)
        sx=np.clip((src_uv[0,0]+w1*(src_uv[1,0]-src_uv[0,0])+w2*(src_uv[2,0]-src_uv[0,0])).astype(int),0,source.shape[1]-1)
        sy=np.clip((src_uv[0,1]+w1*(src_uv[1,1]-src_uv[0,1])+w2*(src_uv[2,1]-src_uv[0,1])).astype(int),0,source.shape[0]-1)
        tex=source[sy,sx]
        # Average coverage rather than binary cutoff; retain natural brow density.
        alpha=tex[:,:,3]*strength*mask
        window=np.s_[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
        replace=alpha>dest_alpha[window]
        dest_alpha[window][replace]=alpha[replace]
        dest_color[window][replace]=tex[:,:,:3][replace]*255
    coverage=gaussian_filter(dest_alpha,.65)
    premul=np.stack([gaussian_filter(dest_color[:,:,k]*dest_alpha,.65) for k in range(3)],axis=2)
    if name=="Hair":
        # A low-density transition on the scalp preserves coverage below the alpha-tested bangs.
        yy,xx=np.ogrid[:N,:N]
        coverage=gaussian_filter(coverage,2.5)
        premul=np.stack([gaussian_filter(premul[:,:,k],2.5) for k in range(3)],axis=2)
        inside=coverage>.17
        dist,nearest=distance_transform_edt(~inside,return_indices=True)
        growth=1.8*np.sin(yy*.89+.12*xx)+1.2*np.sin(yy*.47-.07*xx)
        fade=.55*np.clip(1-(dist+growth)/9,0,1)**1.7
        extra=fade*(~inside)*coverage[tuple(nearest)]
        nearest_rgb=premul[tuple(nearest)]/np.maximum(coverage[tuple(nearest)][:,:,None],.01)
        premul+=extra[:,:,None]*nearest_rgb
        coverage+=extra
    skin=skin*(1-coverage[:,:,None])+premul
    print(name,'coverage texels above 2%',np.sum(coverage>.02),'peak',coverage.max())
Image.fromarray(np.uint8(np.clip(skin,0,255))).save(out/'Skin_Color.png')
# Regional micro-normal from high-passed grayscale source (exclude iris, lips and high contrast makeup).
raw=np.asarray(Image.open(inputs['Skin']),dtype=np.float32)/255.
luma=raw@np.array([.2126,.7152,.0722],np.float32)
detail=np.clip(gaussian_filter(luma,.55)-gaussian_filter(luma,3.6),-.032,.032)
yy,xx=np.ogrid[:N,:N]
face=np.exp(-(((xx-441*4)/(56*4))**4+((yy-264*4)/(82*4))**4))
lip=np.exp(-(((xx-466*4)/(5*4))**2+((yy-264*4)/(12*4))**2))
eyes=np.maximum.reduce([np.exp(-(((xx-428*4)/(8*4))**2+((yy-cy*4)/(10*4))**2)) for cy in (243,282)])
detail*=face*(1-.8*np.maximum(lip,eyes))
gy,gx=np.gradient(detail)
norm=np.stack((-gx*4, -gy*4,np.ones_like(gy)),axis=-1)
norm/=np.linalg.norm(norm,axis=-1,keepdims=True)
Image.fromarray(np.uint8(np.clip(norm*127.5+127.5,0,255))).save(out/'Skin_Normal.png')
hair=np.array(Image.open(inputs['Hair']))
hn=len(hair);edges=np.load(p/'hair_boundary.npy');pixels=to_pixel(edges,hn)
lines=Image.new('L',(hn,hn),0);draw=ImageDraw.Draw(lines)
for a,b in pixels:
    if np.linalg.norm(a-b)>320:continue
    draw.line((tuple(a),tuple(b)),fill=255,width=2)
dist=distance_transform_edt(np.array(lines)==0).astype('f')
yy,xx=np.ogrid[:hn,:hn]
axis=xx*.24+yy*.091+1.4*np.sin(yy*.022)+.9*np.sin(xx*.012)
stagger=5+4*np.sin(axis)+2.5*np.sin(axis*1.61)
coverage=np.clip((dist+1.8-stagger)/20,0,1)
o=hair[:,:,3].copy()
# The visible fringe includes contours inside the alpha image, beyond the model's open edges.
# Preserve narrow existing strands while feathering the dense alpha islands.
solid=o>=70
distance_inside=distance_transform_edt(solid)
blurred=gaussian_filter(solid.astype('f'),3.)
alpha_edge=np.clip((distance_inside+1.0+np.sin(axis)*1.8)/7.,.38,1.)
coverage*=1-(1-alpha_edge)*np.clip((blurred-.27)/.5,0,1)
hair[:,:,3]=np.rint(hair[:,:,3]*(coverage**.78))
Image.fromarray(hair).save(out/'Hair_Color.png')
print('Hair edge sample original alpha median',np.median(o[np.asarray(lines)>0]),'modified',np.median(hair[:,:,3][np.asarray(lines)>0]),'changed texels',np.sum(o!=hair[:,:,3]))
if args.cc0:
    # Matches build_character.make_surface_masks with the original AO sampled in linear space.
    ao=np.asarray(Image.open(wardrobe_base).convert("RGB"))[:,:,0].astype(np.float32)/255
    ward=np.full((*ao.shape,4),255,np.uint8)
    ward[:,:,0]=0
    ward[:,:,1]=np.rint(255*(.30+.70*ao))
    ward[:,:,3]=np.rint(255*(.22+.105*ao))
else:
    ward=np.asarray(Image.open(wardrobe_base)).copy()
cloth=np.asarray(Image.open(inputs['Wardrobe']).convert('L'),np.float32)/255
weave=gaussian_filter(cloth,1)-gaussian_filter(cloth,13)
ward[:,:,3]=np.clip(ward[:,:,3].astype(np.float32)+80*np.clip(weave,-.12,.12),0,255)
Image.fromarray(ward).save(out/'Wardrobe_Mask.png')
