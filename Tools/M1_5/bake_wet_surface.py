"""Bake a continuous rain-exposure field over a twelve-metre section of the platform."""
from pathlib import Path
import numpy as np
from PIL import Image
root=Path(__file__).resolve().parents[2]/"Assets/_Project/Art/Textures/M1_5"
out=root/"WetConcrete";out.mkdir(exist_ok=True)
w,h=1024,2048
y,x=np.ogrid[0:h,0:w];s=x/w;t=y/h*2*np.pi
field=.5+.21*np.sin(2*t+1.1*np.sin(s*5))+.14*np.cos(t*3-s*10)+.08*np.sin(t*7+s*6)+.05*np.sin(t*15+s*17)
coverage=np.clip((s-.03)*1.55+field*.60-.31,.06,.92)
def repeat(name):
    base=Image.open(root/'Concrete'/name)
    # 0.96 metres across each tile; preserve grain scale along both axes.
    im=base.resize((342,164),Image.Resampling.LANCZOS)
    return np.tile(np.asarray(im),(13,3,1))[:h,:w]
base=repeat('Base.jpg').astype(float)/255
Image.fromarray(np.uint8((base*(.83-.10*coverage[:,:,None]))*255)).save(out/'Base.jpg',quality=94)
mask=repeat('Mask.png').copy()
mask[:,:,3]=np.uint8((.45+.14*mask[:,:,3]/255+.25*coverage)*255)
Image.fromarray(mask).save(out/'Mask.png')
n=repeat('Normal.jpg')/127.5-1;n[:,:,:2]*=(.72-.40*coverage[:,:,None]);n[:,:,2]=np.sqrt(np.maximum(0,1-(n[:,:,:2]**2).sum(axis=2)))
Image.fromarray(np.uint8(np.clip(n+1,0,2)*127.5)).save(out/'Normal.jpg',quality=94)
