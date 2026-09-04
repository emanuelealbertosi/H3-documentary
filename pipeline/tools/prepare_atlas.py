"""Build georeferenced, shaded atlas rasters and antialiased mipmaps offline."""
from pathlib import Path
import sys,math,json,argparse
import numpy as np,cv2
from PIL import Image,ImageDraw
from scipy.ndimage import gaussian_filter,distance_transform_edt
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.common import ROOT,read_json,write_json
from tools.acquire_atlas import tilexy
Image.MAX_IMAGE_PIXELS=None
GEO=ROOT/'assets/geography';OUT=GEO/'atlas-v2';OUT.mkdir(exist_ok=True)

def merc(lat):return math.degrees(math.asinh(math.tan(math.radians(lat))))
def invmerc(y):return np.degrees(np.arctan(np.sinh(np.radians(y))))

def grade(a):
    a=a.astype(np.float32);water=(a[:,:,2]>a[:,:,0]*1.07)&(a[:,:,2]>a[:,:,1]*1.015)
    # Restrained, stable printed-atlas palette; no generated per-frame noise.
    lum=a.mean(axis=2);a=a*.72+lum[:,:,None]*.28
    a=a*np.array([.92,.97,.87],dtype=np.float32)+np.array([5,2,4],dtype=np.float32)
    a[water]=np.array([22,52,69])+np.clip((lum[water]-160)*.12,-8,8)[:,None]
    return np.clip(a,0,255).astype(np.uint8)

def save_layer(name,img,west,north,ppd,alpha=None):
    levels=[]
    for i in range(5):
        p=OUT/f'{name}-{i}.npy';np.save(p,img)
        levels.append(str(p.relative_to(ROOT)).replace('\\','/'))
        if min(img.shape[:2])<256:break
        img=cv2.resize(img,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA)
    info=dict(name=name,west=west,north=north,ppd=ppd,levels=levels)
    if alpha is not None:
        p=OUT/f'{name}-alpha.npy';np.save(p,alpha);info['alpha']=str(p.relative_to(ROOT)).replace('\\','/')
    return info

def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument('--config',default='battles/annibale/geography.json');args=parser.parse_args()
    config=read_json(ROOT/args.config);OUT=ROOT/config['output'];OUT.mkdir(parents=True,exist_ok=True)
    cv2.setNumThreads(2)
    src=Image.open(next((GEO/'naturalearth').glob('**/*.tif'))).convert('RGB')
    sw,sh=src.size
    # Cut the source before reprojection to avoid keeping the whole globe in RAM.
    west,south,east,north=config['bounds']
    x0=int((west+180)/360*sw);x1=int((east+180)/360*sw)
    y0=int((90-north)/180*sh);y1=int((90-south)/180*sh)
    raw=np.array(src.crop((x0,y0,x1,y1)));del src
    ppd=sw/360;w=raw.shape[1];h=round((merc(north)-merc(south))*ppd)
    base=np.empty((h,w,3),np.uint8)
    for y in range(0,h,128):
        end=min(h,y+128);lat=invmerc(merc(north)-np.arange(y,end)/ppd)
        mx=np.broadcast_to(np.arange(w,dtype=np.float32),(end-y,w)).copy()
        my=np.broadcast_to(((90-lat)/180*sh-y0).astype(np.float32)[:,None],(end-y,w)).copy()
        base[y:end]=grade(cv2.remap(raw,mx,my,cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE))
    print('European physical atlas',base.shape,flush=True)
    layers=[save_layer('europe',base,west,merc(north),ppd)]
    manifest=config
    land=read_json(GEO/'land.geojson')
    lakes=read_json(GEO/'lakes.geojson')
    for name,spec in manifest['patches'].items():
        bounds=spec['bounds'] if isinstance(spec,dict) else spec
        pw,ps,pe,pn=bounds
        z=int(spec.get('zoom',manifest['terrain_zoom'])) if isinstance(spec,dict) else manifest['terrain_zoom']
        tppd=256*2**z/360
        tx0,ty0=tilexy(pw,pn,z);tx1,ty1=tilexy(pe,ps,z)
        height=(ty1-ty0+1)*256;width=(tx1-tx0+1)*256
        elev=np.empty((height,width),np.float32)
        for tx in range(tx0,tx1+1):
            for ty in range(ty0,ty1+1):
                a=np.array(Image.open(GEO/f'terrain/{z}/{tx}/{ty}.png')).astype(np.float32)
                elev[(ty-ty0)*256:(ty-ty0+1)*256,(tx-tx0)*256:(tx-tx0+1)*256]=a[:,:,0]*256+a[:,:,1]+a[:,:,2]/256-32768
        pwest=tx0*256/tppd-180;pnorth=180-ty0*256/tppd
        gy,gx=np.gradient(gaussian_filter(elev,.7))
        metres=40075016.686/(256*2**z)*math.cos(math.radians(float(invmerc(pnorth-height/2/tppd))))
        dx=gx/metres*2.1;dy=gy/metres*2.1
        shade=(.55+(-dx*.55+dy*.55+.72)/np.sqrt(1+dx*dx+dy*dy)*.55)
        shade=np.clip(shade,.52,1.30)
        patch=np.empty((height,width,3),np.uint8)
        for y in range(0,height,128):
            end=min(height,y+128)
            mx=np.broadcast_to(((pwest+np.arange(width)/tppd-west)*ppd).astype(np.float32),(end-y,width)).copy()
            my=np.broadcast_to(((merc(north)-(pnorth-np.arange(y,end)/tppd))*ppd).astype(np.float32)[:,None],(end-y,width)).copy()
            colors=cv2.remap(base,mx,my,cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
            elevated=elev[y:end]>15
            strength=np.where(elevated,shade[y:end],1)[:,:,None]
            patch[y:end]=np.clip(colors*strength,0,255).astype(np.uint8)
        # Baked contours remain perfectly registered during zooms and pans.
        # They make low-relief battlefields readable without inventing roads or
        # historical terrain features.
        span=float(np.nanmax(elev)-np.nanmin(elev))
        interval=20 if pe-pw>.5 else 10 if pe-pw>.15 else 5
        if span>500:interval=max(interval,20)
        quantized=np.floor(elev/interval).astype(np.int32)
        contour=np.zeros((height,width),np.uint8)
        contour[:,1:]|=(quantized[:,1:]!=quantized[:,:-1])
        contour[1:,:]|=(quantized[1:,:]!=quantized[:-1,:])
        contour=cv2.dilate(contour,np.ones((2,2),np.uint8),iterations=1).astype(bool)
        patch[contour]=np.clip(patch[contour]*.82+np.array([35,58,43])*.18,0,255).astype(np.uint8)
        # High-resolution vector coasts remove magnified pixels from the global raster.
        lm=Image.new('L',(width,height));ld=ImageDraw.Draw(lm)
        for feature in land['features']:
            geom=feature['geometry'];polys=[geom['coordinates']] if geom['type']=='Polygon' else geom['coordinates']
            for rings in polys:
                outer=rings[0]
                if max(p[0] for p in outer)<pwest or min(p[0] for p in outer)>pwest+width/tppd:continue
                if max(p[1] for p in outer)<float(invmerc(pnorth-height/tppd)) or min(p[1] for p in outer)>float(invmerc(pnorth)):continue
                for j,ring in enumerate(rings):
                    pts=[((lon-pwest)*tppd,(pnorth-merc(max(-85,min(85,lat))))*tppd) for lon,lat in ring]
                    ld.polygon(pts,fill=255 if j==0 else 0)
        for feature in lakes['features']:
            if feature['properties'].get('featurecla')!='Lake':continue
            geom=feature['geometry'];polys=[geom['coordinates']] if geom['type']=='Polygon' else geom['coordinates']
            for rings in polys:
                outer=rings[0]
                if max(p[0] for p in outer)<pwest or min(p[0] for p in outer)>pwest+width/tppd:continue
                if max(p[1] for p in outer)<float(invmerc(pnorth-height/tppd)) or min(p[1] for p in outer)>float(invmerc(pnorth)):continue
                for j,ring in enumerate(rings):
                    ld.polygon([((lon-pwest)*tppd,(pnorth-merc(lat))*tppd) for lon,lat in ring],fill=0 if j==0 else 255)
        landmask=np.array(lm)>0
        oldwater=patch[:,:,0]<55
        repairs=landmask&oldwater
        if repairs.any():
            indices=distance_transform_edt(oldwater,return_distances=False,return_indices=True)
            patch[repairs]=patch[indices[0][repairs],indices[1][repairs]]
            del indices
        patch[~landmask]=[22,52,69]
        yy,xx=np.ogrid[:height,:width]
        alpha=np.minimum(np.minimum(xx,width-1-xx),np.minimum(yy,height-1-yy))
        alpha=(np.clip(alpha/220,0,1)*255).astype(np.uint8)
        layers.append(save_layer(name,patch,pwest,pnorth,tppd,alpha))
        print('Detailed relief',name,patch.shape,flush=True)
    write_json(OUT/'atlas.json',{'projection':'Spherical Mercator, north up','layers':layers,'credit':'Natural Earth; Mapzen terrain / EU-DEM Copernicus, USGS, NOAA','modern_geography_notice':'Physical reference, not a reconstruction of ancient coastlines or vegetation.'})
    Image.fromarray(base).resize((1080,round(h/w*1080)),Image.Resampling.LANCZOS).save(OUT/'europe-preview.jpg',quality=94)

if __name__=='__main__':main()
