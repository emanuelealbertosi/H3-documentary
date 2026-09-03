"""Illustrative, georeferenced 2.5D terrain. No modern borders or invented DEM claims."""
import math
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image,ImageDraw
import cv2
from .common import ROOT,fingerprint,write_json

SIZE=(3200,2200)

class Cartography:
    def __init__(self,spec,slug,name):
        self.spec=spec; self.name=name
        self.center=np.array(spec['center']); self.scale=np.array(spec['scale'])
        key=fingerprint([spec,'terrain-v7'])[:14]
        path=ROOT/'assets'/'maps'/slug/f'{name}-{key}.png'
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists(): self.create(path)
        self.image=np.array(Image.open(path).convert('RGB'))
        self.path=path

    def world(self,pos):
        lon,lat=pos
        return ((lon-self.center[0])*self.scale[0]+SIZE[0]/2,
                (self.center[1]-lat)*self.scale[1]+SIZE[1]/2)

    def create(self,path):
        w,h=SIZE; rng=np.random.default_rng(self.spec['seed'])
        yy,xx=np.mgrid[:h,:w].astype(np.float32)
        lon=(xx-w/2)/self.scale[0]+self.center[0]; lat=(h/2-yy)/self.scale[1]+self.center[1]
        small=rng.normal(size=(34,49)).astype(np.float32)
        noise=cv2.resize(small,(w,h),interpolation=cv2.INTER_CUBIC)
        altitude=34+.35*noise+1.2*np.sin(xx/670)*np.cos(yy/470)
        for r in self.spec.get('ridges',[]):
            altitude+=r['amplitude']*np.exp(-(((lon-r['pos'][0])/r['width'][0])**2+((lat-r['pos'][1])/r['width'][1])**2))
        grad_y,grad_x=np.gradient(gaussian_filter(altitude,5))
        shade=np.clip(1+grad_x*1.7-grad_y*3,.82,1.22)
        texture=rng.normal(0,1.9,(h,w)).astype(np.float32)
        palette=self.spec.get('palette',[89,99,76])
        base=np.stack([palette[0]+noise*4+texture,palette[1]+noise*4+texture,palette[2]+noise*3+texture],axis=-1)
        base=np.clip(base*shade[:,:,None],0,255).astype(np.uint8)
        image=Image.fromarray(base); d=ImageDraw.Draw(image,'RGBA')
        # Land parcels drawn in a stable world, with subdued colours and no modern infrastructure.
        step=95 if self.name=='battle' else 160
        for y in range(-step,h+step,step):
            for x in range(-step,w+step,step):
                dx=int(rng.integers(-25,25)); dy=int(rng.integers(-22,22)); sx=int(rng.integers(65,120))
                poly=[(x+dx,y+dy),(x+sx+dx,y+dy-17),(x+sx+dx+26,y+step-15),(x+dx+15,y+step)]
                col=[(163,145,94,26),(142,163,92,21),(82,108,63,45),(195,173,117,20)][int(rng.integers(4))]
                d.polygon(poly,fill=col,outline=(33,48,32,32))
                if rng.random()<.4:
                    for off in range(12,step-15,13):
                        d.line([(x+dx+6,y+dy+off),(x+sx+dx,y+dy+off-12)],fill=(37,48,31,19),width=1)
        # Contours follow the procedural elevation, intentionally presented as illustrative.
        for level in range(24,66,4):
            mask=(altitude>level).astype(np.uint8)*255
            contours,_=cv2.findContours(mask,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                if len(contour)>5:
                    pts=[tuple(map(int,p)) for p in contour[::2,0,:]]
                    if len(pts)>2: d.line(pts,fill=(221,214,165,27),width=1)
        # Broad waterways and urban footprints are supplied by the battle pack.
        for water in self.spec.get('water',[]):
            d.polygon([self.world(p) for p in water['points']],fill=(71,112,125,255),outline=(145,176,171,220))
        for district in self.spec.get('districts',[]):
            poly=[self.world(p) for p in district['points']]
            d.polygon(poly,fill=(118,116,101,210),outline=(150,143,120,130))
            contour=np.array(poly,dtype=np.float32)
            xmin,ymin=contour.min(axis=0);xmax,ymax=contour.max(axis=0)
            for by in range(max(0,int(ymin)),min(h,int(ymax)),24):
                for bx in range(max(0,int(xmin)),min(w,int(xmax)),27):
                    if cv2.pointPolygonTest(contour,(float(bx),float(by)),False)<0:continue
                    bw=int(rng.integers(10,21));bh=int(rng.integers(7,16))
                    d.rectangle((bx+4,by+5,bx+bw+4,by+bh+5),fill=(22,27,28,130))
                    d.rectangle((bx,by,bx+bw,by+bh),fill=(151,145,126,255),outline=(79,78,69,255))
        for river in self.spec['rivers']:
            p=[self.world(x) for x in river['points']]
            rw=river.get('width',8)
            d.line(p,fill=(32,59,59,180),width=rw+7,joint='curve')
            d.line(p,fill=(101,143,146,240),width=rw,joint='curve')
            d.line(p,fill=(165,188,183,100),width=2,joint='curve')
        for road in self.spec['roads']:
            p=[self.world(x) for x in road['points']]
            d.line(p,fill=(28,35,27,165),width=14,joint='curve')
            d.line(p,fill=(173,162,126,245),width=7,joint='curve')
            d.line(p,fill=(229,208,160,100),width=2,joint='curve')
        for forest in self.spec['forests']:
            cx,cy=self.world(forest['pos']); rx=forest['radius'][0]*self.scale[0]; ry=forest['radius'][1]*self.scale[1]
            amount=int(rx*ry/40)
            for i in range(min(amount,7000)):
                angle=rng.uniform(0,math.tau); rad=math.sqrt(rng.uniform())
                x=cx+rx*rad*math.cos(angle); y=cy+ry*rad*math.sin(angle); sz=int(rng.integers(3,9))
                d.ellipse((x-sz+3,y-sz+5,x+sz+3,y+sz+5),fill=(17,30,21,65))
                d.ellipse((x-sz,y-sz,x+sz,y+sz),fill=(42+sz,65+sz,40+sz,210))
                d.ellipse((x-sz,y-sz,x,y),fill=(104,123,75,70))
        # Extruded farm/village buildings: small shadows, wall faces, warm tiled roofs.
        for place in self.spec['landmarks']:
            if place['kind'] in ('ridge','forest'): continue
            x,y=self.world(place['pos']); count=5 if place['kind']=='farm' else (12 if self.name=='battle' else 20)
            for k in range(count):
                dx,dy=rng.normal(0,13 if count<12 else 19,2)
                bx,by=x+dx,y+dy; bw,bh=(rng.integers(7,15),rng.integers(5,10))
                d.polygon([(bx,by),(bx+bw+8,by+3),(bx+bw+8,by+bh+9),(bx+5,by+bh+9)],fill=(12,23,21,110))
                d.rectangle((bx,by+4,bx+bw,by+bh+5),fill=(171,163,133,255))
                d.polygon([(bx-2,by),(bx+bw/2,by-4),(bx+bw+2,by),(bx+bw+2,by+bh),(bx-2,by+bh)],fill=(117,77,56,255))
                d.line([(bx,by),(bx+bw,by)],fill=(210,175,128,200),width=2)
        image.save(path)
        write_json(path.with_suffix('.json'),{'method':'Procedural illustrative relief, not a surveyed DEM. Geographic coordinates in battle pack.',
          'seed':self.spec['seed'],'world_size':SIZE,'spec':self.spec})

    def frame(self,camera):
        lon,lat,z=camera; x,y=self.world([lon,lat])
        matrix=np.array([[z,0,1210-z*x],[0,z,562-z*y]],dtype=np.float32)
        return Image.fromarray(cv2.warpAffine(self.image,matrix,(1920,1080),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT))

    def screen(self,pos,camera):
        lon,lat,z=camera
        return (1210+(pos[0]-lon)*self.scale[0]*z,562+(lat-pos[1])*self.scale[1]*z)
