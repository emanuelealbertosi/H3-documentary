"""Full-screen geographic atlas renderer, stable labels and continuous camera paths.

Geography is immutable. Trilinear mip filtering prevents terrain shimmer; overlays
are supersampled, label placement is authored, and chapters never flash to black.
"""
import math
from functools import lru_cache
import numpy as np,cv2
from PIL import Image,ImageDraw,ImageOps,ImageEnhance
from .common import ROOT,read_json,stamp
from .visuals import font,portrait,wrap

W,H=1920,1080;SS=2
INK=(13,31,42);CREAM=(249,238,211);GOLD=(239,185,93);RED=(221,109,101);MUTED=(167,190,195)

def merc(lat):return math.degrees(math.asinh(math.tan(math.radians(lat))))
def smooth(t):
    t=max(0.,min(1.,t));return t*t*t*(t*(t*6-15)+10)
def project(pos):return np.array([pos[0],merc(pos[1])],dtype=float)
def camera(s,t):
    nodes=s.get('camera_keys',[{'at':0,'view':s['camera_start']},{'at':.32,'view':s['camera_end']},{'at':1,'view':s['camera_end']}])
    q=t/s['duration']
    for a,b in zip(nodes,nodes[1:]):
        if q<=b['at']:
            f=smooth((q-a['at'])/(b['at']-a['at']))
            # Logarithmic scale interpolation maintains a perceptually smooth zoom.
            pa=project(a['view'][:2]);pb=project(b['view'][:2]);p=pa+(pb-pa)*f
            return float(p[0]),float(p[1]),math.exp(math.log(a['view'][2])*(1-f)+math.log(b['view'][2])*f)
    v=nodes[-1]['view'];return v[0],merc(v[1]),v[2]
def screen(pos,cam):
    p=project(pos);k=W/cam[2];return (W/2+(p[0]-cam[0])*k,H/2-(p[1]-cam[1])*k)
def cue_start(s,i):return s['cues'][min(i,len(s['cues'])-1)]['start']
def progress(s,item,t):
    if s.get('_still'):return item.get('_still_progress',1)
    start=cue_start(s,item.get('cue',0));end=cue_start(s,item['end_cue']) if item.get('end_cue') is not None else s['cues'][item.get('cue',0)]['end']
    return smooth((t-start)/max(2,end-start))
def partial(points,p):
    lengths=[math.dist(a,b) for a,b in zip(points,points[1:])];distance=sum(lengths)*p;result=[points[0]]
    for a,b,l in zip(points,points[1:],lengths):
        if distance>=l:result.append(b);distance-=l
        else:
            result.append(tuple(a[j]+(b[j]-a[j])*distance/max(l,1e-8) for j in range(2)));break
    return result

class RasterAtlas:
    def __init__(self,path):
        self.spec=read_json(ROOT/path);self.layers=[];self.last_key=None;self.last_frame=None
        for info in self.spec['layers']:
            layers=[np.load(ROOT/p,mmap_mode='r') for p in info['levels']]
            self.layers.append((info,layers,np.load(ROOT/info['alpha'],mmap_mode='r') if 'alpha' in info else None))

    def warp(self,info,levels,cam):
        scale=W/cam[2]/info['ppd'];lod=max(0.,min(len(levels)-1.,math.log2(max(1.,1/scale))))
        lo=int(lod);hi=min(lo+1,len(levels)-1)
        def sample(i):
            k=scale*2**i;x=(cam[0]-info['west'])*info['ppd']/2**i;y=(info['north']-cam[1])*info['ppd']/2**i
            mat=np.array([[k,0,W/2-k*x],[0,k,H/2-k*y]],np.float64)
            return cv2.warpAffine(levels[i],mat,(W,H),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=INK)
        a=sample(lo)
        return cv2.addWeighted(a,1-(lod-lo),sample(hi),lod-lo,0) if hi!=lo and lod-lo>.001 else a

    def frame(self,cam):
        if cam==self.last_key:return self.last_frame.copy()
        base=self.warp(*self.layers[0][:2],cam)
        strength=smooth((19-cam[2])/9)
        if strength>0:
            for info,levels,mask in self.layers[1:]:
                # Skip patches entirely outside the view.
                right=info['west']+levels[0].shape[1]/info['ppd'];bottom=info['north']-levels[0].shape[0]/info['ppd']
                if cam[0]+cam[2]/2<info['west'] or cam[0]-cam[2]/2>right or cam[1]+cam[2]*H/W/2<bottom or cam[1]-cam[2]*H/W/2>info['north']:continue
                k=W/cam[2]/info['ppd'];x=(cam[0]-info['west'])*info['ppd'];y=(info['north']-cam[1])*info['ppd']
                mat=np.array([[k,0,W/2-k*x],[0,k,H/2-k*y]],np.float64)
                alpha=cv2.warpAffine(mask,mat,(W,H),flags=cv2.INTER_LINEAR).astype(np.float32)*(strength/255)
                patch=self.warp(info,levels,cam)
                base=cv2.blendLinear(base,patch,1-alpha,alpha)
        self.last_key=cam;self.last_frame=Image.fromarray(base)
        return self.last_frame.copy()

@lru_cache(maxsize=200)
def label_image(text,size,color,kind='sans'):
    ft=font(size*SS,kind);box=ft.getbbox(text);w=math.ceil(ft.getlength(text))+32;h=box[3]-box[1]+28
    im=Image.new('RGBA',(w,h));d=ImageDraw.Draw(im)
    d.text((16,14-box[1]),text,font=ft,fill=color,stroke_width=3,stroke_fill=(*INK,210))
    return im

def label(im,xy,text,size=23,color=CREAM,alpha=1,kind='sans',anchor='center'):
    tile=label_image(text,size,color,kind)
    if alpha<1:
        tile=tile.copy();tile.putalpha(tile.getchannel('A').point(lambda v:round(v*max(0,alpha))))
    x,y=xy;x*=SS;y*=SS
    if anchor=='center':x-=tile.width/2
    im.alpha_composite(tile,(round(x),round(y-tile.height/2)))

def polyline(d,points,color,width=4,dashed=False):
    pts=[(x*SS,y*SS) for x,y in points]
    if len(pts)<2:return
    if dashed:
        # Static dash phase: no crawling pattern or count changes every frame.
        total=sum(math.dist(a,b) for a,b in zip(pts,pts[1:]));at=0
        while at<total:
            start=partial(pts,at/max(total,1))[-1];end=partial(pts,min(1,(at+14*SS)/max(total,1)))[-1]
            d.line((start,end),fill=color,width=width*SS);at+=25*SS
    else:d.line(pts,fill=color,width=width*SS,joint='curve')

class AtlasVisuals:
    def __init__(self,data):
        cv2.setNumThreads(1)
        self.data=data;self.total=data['duration'];self.atlas=RasterAtlas(data['atlas'])
        self.colors={f['id']:tuple(f['color']) for f in data['factions']};self.huds={};self.label_cache={}
        yy,xx=np.mgrid[:H,:W];a=np.maximum(np.clip((180-yy)/180,0,1)*.87,np.clip((yy-800)/280,0,1)*.90)
        a=np.maximum(a,np.clip(((xx-W/2)/(W*.75))**2*.13,0,.16))
        ar=np.zeros((H,W,4),np.uint8);ar[:,:,:3]=INK;ar[:,:,3]=(a*255).astype(np.uint8);self.shade=Image.fromarray(ar)
        geo=read_json(ROOT/'assets/geography/rivers.geojson');self.rivers=[]
        wanted=set(data.get('river_names',['Rhone','Rhône','Ebro','Po','Tiber','Tevere','Arno','Danube','Rhine','Seine']))
        for feat in geo['features']:
            props=feat['properties'];name=props.get('name','')
            if name not in wanted:continue
            g=feat['geometry'];lines=[g['coordinates']] if g['type']=='LineString' else g['coordinates'] if g['type']=='MultiLineString' else []
            self.rivers.extend(lines)

    def map_background(self,cam):
        """Cinematic but stable colour grade for the physical atlas."""
        im=self.atlas.frame(cam).convert('RGB')
        im=ImageEnhance.Color(im).enhance(1.28)
        im=ImageEnhance.Contrast(im).enhance(1.09)
        return ImageEnhance.Brightness(im).enhance(.98).convert('RGBA')

    def geography_labels(self,s,cam,opacity):
        key=(s['id'],cam,round(opacity,4))
        if key==self.label_cache.get('key'):return self.label_cache['image'].copy()
        im=Image.new('RGBA',(W*SS,H*SS));d=ImageDraw.Draw(im)
        # Rivers stay registered to the same map projection as the terrain.
        for river in self.rivers:
            pts=[screen(p,cam) for p in river]
            if not any(-100<x<W+100 and -100<y<H+100 for x,y in pts):continue
            polyline(d,pts,(20,52,68,int(95*opacity)),4 if cam[2]<10 else 2)
            polyline(d,pts,(74,170,213,int(185*opacity)),2 if cam[2]<10 else 1)
        for river in s.get('local_rivers',[]):
            pts=[screen(p,cam) for p in river['points']]
            polyline(d,pts,(20,52,68,int(115*opacity)),6)
            polyline(d,pts,(75,181,226,int(225*opacity)),3)
        for region in s.get('region_labels',[]):
            xy=screen(region['pos'],cam)
            if 70<xy[0]<W-70 and 170<xy[1]<H-170:label(im,xy,region['text'],region.get('size',33),(*CREAM,220),alpha=opacity,kind='serif')
        for ident in s['visible_places']:
            place=self.data['places'][ident];x,y=screen(place['pos'],cam);dx,dy=s.get('label_offsets',{}).get(ident,place.get('offset',[0,25]))
            if not -40<x<W+40 or not -40<y<H+40:continue
            # Opacity fades at viewport edges; no abrupt culling/repositioning.
            edge=min(smooth((x-28)/45),smooth((W-28-x)/45),smooth((y-145)/45),smooth((H-175-y)/45))
            op=opacity*edge
            if op<=0:continue
            col=tuple(place.get('color',CREAM))
            # Map pin with a soft halo stays legible on bright relief and dark sea.
            d.ellipse((x*SS-11*SS,y*SS-11*SS,x*SS+11*SS,y*SS+11*SS),fill=(*INK,int(85*op)))
            d.ellipse((x*SS-7*SS,y*SS-7*SS,x*SS+7*SS,y*SS+7*SS),fill=(*col,int(245*op)),outline=(*CREAM,int(240*op)),width=2*SS)
            d.ellipse((x*SS-2*SS,y*SS-2*SS,x*SS+2*SS,y*SS+2*SS),fill=(*INK,int(245*op)))
            label(im,(x+dx,y+dy),place['name'],place.get('size',22),col,op)
        self.label_cache={'key':key,'image':im.copy()}
        return im

    def hud(self,s):
        if s['id'] in self.huds:return self.huds[s['id']]
        im=Image.new('RGBA',(W,H));d=ImageDraw.Draw(im)
        d.text((56,31),self.data['short_title'].upper()+'  /  ATLANTE STORICO',font=font(16),fill=GOLD)
        d.text((54,56),s['title'].upper(),font=font(58,'display'),fill=CREAM)
        d.text((W-58,39),s['date'],font=font(22),fill=CREAM,anchor='ra')
        d.line((W-111,107,W-111,156),fill=CREAM,width=2);d.polygon([(W-111,102),(W-117,117),(W-105,117)],fill=CREAM)
        d.text((W-111,86),'N',font=font(17),fill=CREAM,anchor='mm')
        # One compact narration card leaves nearly all geography visible.
        d.rounded_rectangle((50,865,880,1005),radius=9,fill=(*INK,218),outline=(152,169,157,65),width=1)
        d.rectangle((50,885,54,983),fill=GOLD)
        d.text((76,880),s['kicker'].upper(),font=font(16),fill=GOLD)
        lines=wrap(d,s['facts'][0],760,29,'serif')
        for j,line in enumerate(lines[:2]):d.text((76,909+j*34),line,font=font(29,'serif'),fill=CREAM)
        d.text((76,980),s.get('caption_note','Itinerario schematico · coordinate geografiche'),font=font(12),fill=MUTED)
        d.text((W-56,964),f'{int(s["id"]):02} / {len(self.data["scenes"]):02}',font=font(23),fill=GOLD,anchor='ra')
        d.text((W-56,1000),'Cartografia: Natural Earth · rilievo: Mapzen / Copernicus',font=font(12),fill=MUTED,anchor='ra')
        d.line((948,959,982,959),fill=GOLD,width=4)
        d.text((994,948),self.data.get('route_legend','Avanzata'),font=font(16),fill=CREAM)
        d.line((948,988,960,988),fill=GOLD,width=3);d.line((970,988,982,988),fill=GOLD,width=3)
        d.text((994,977),'Tratto incerto / schematico',font=font(14),fill=MUTED)
        for other in self.data['scenes']:
            x=56+1808*other['start']/self.total;end=56+1808*other['end']/self.total-2
            d.line((x,1042,end,1042),fill=(*GOLD,70),width=3)
        self.huds[s['id']]=im;return im

    def frame(self,s,t):
        cam=camera(s,t);im=self.map_background(cam)
        fade=1 if s.get('_still') else min(smooth(t/.9),smooth((s['duration']-t)/.9))
        overlay=Image.new('RGBA',(W*SS,H*SS));d=ImageDraw.Draw(overlay)
        for area in s.get('uncertainty_areas',[]):
            pts=[screen(p,cam) for p in area['points']]
            d.polygon([(x*SS,y*SS) for x,y in pts],fill=(*GOLD,42))
            polyline(d,pts+[pts[0]],(*GOLD,180),2,True)
        for route in s.get('routes',[]):
            p=progress(s,route,t) if s.get('_still') else 1 if route.get('complete') else progress(s,route,t)
            if p<=0:continue
            points=[screen(x,cam) for x in route['points']];points=partial(points,p)
            col=self.colors.get(route.get('side','carthage'),GOLD);alpha=route.get('alpha',235)
            polyline(d,points,(*INK,min(alpha,205)),12,False)
            polyline(d,points,(*col,alpha),7,route.get('uncertain',False))
            if not route.get('uncertain',False):polyline(d,points,(*CREAM,min(alpha,105)),2,False)
            if not route.get('complete') and route.get('marker',True):
                x,y=points[-1]
                if -30<x<W+30 and -30<y<H+30:
                    d.ellipse(((x-19)*SS,(y-19)*SS,(x+19)*SS,(y+19)*SS),fill=(*INK,110))
                    d.ellipse(((x-15)*SS,(y-15)*SS,(x+15)*SS,(y+15)*SS),fill=(*col,245),outline=(*CREAM,245),width=2*SS)
                    # Original compass/banner glyph, readable at every zoom.
                    d.line((x*SS,(y-9)*SS,x*SS,(y+9)*SS),fill=(*INK,245),width=3*SS)
                    d.polygon([(x*SS,(y-9)*SS),((x+10)*SS,(y-5)*SS),(x*SS,(y-1)*SS)],fill=CREAM)
        # BEGIN H3 BATTLE ATLAS TACTICS
        # Direction heads and unit counters use the same smooth cue progress as
        # routes. Their positions are deterministic, so no per-frame jitter is
        # introduced while labels and counters move with the geographic camera.
        for arrow in s.get('arrows',[]):
            p=progress(s,arrow,t)
            if p<=0:continue
            points=partial([screen(x,cam) for x in arrow['points']],p)
            if len(points)<2:continue
            x,y=points[-1];px,py=points[-2];angle=math.atan2(y-py,x-px);col=self.colors.get(arrow.get('side'),GOLD)
            size=18*SS
            tip=(x*SS,y*SS)
            left=(x*SS-size*math.cos(angle)+size*.48*math.sin(angle),y*SS-size*math.sin(angle)-size*.48*math.cos(angle))
            right=(x*SS-size*math.cos(angle)-size*.48*math.sin(angle),y*SS-size*math.sin(angle)+size*.48*math.cos(angle))
            d.polygon([tip,left,right],fill=(*col,int(245*fade)),outline=(*INK,int(220*fade)))
        for unit in s.get('units',[]):
            if t<cue_start(s,unit.get('cue',0)):continue
            if unit.get('until') is not None and t>cue_start(s,unit['until']):continue
            pos=partial(unit['path'],progress(s,unit,t))[-1] if unit.get('path') else unit['pos']
            x,y=screen(pos,cam)
            sx,sy=unit.get('screen_offset',[0,0]);x+=sx;y+=sy
            if not 40<x<W-40 or not 175<y<H-175:continue
            col=self.colors.get(unit.get('side'),GOLD);count=max(1,min(4,int(unit.get('count',1))))
            for n in range(count):
                ox=(n-(count-1)/2)*16*SS
                d.rounded_rectangle((x*SS-25*SS+ox,y*SS-11*SS,x*SS+25*SS+ox,y*SS+11*SS),radius=7*SS,fill=(*INK,int(110*fade)))
                d.rounded_rectangle((x*SS-23*SS+ox,y*SS-13*SS,x*SS+23*SS+ox,y*SS+9*SS),radius=7*SS,fill=(*col,int(245*fade)),outline=(*CREAM,int(240*fade)),width=2*SS)
            kind=unit.get('kind','infantry')
            if kind=='cavalry':d.line(((x-10)*SS,(y+5)*SS,(x+10)*SS,(y-5)*SS),fill=(*INK,int(245*fade)),width=2*SS)
            elif kind=='artillery':d.ellipse(((x-5)*SS,(y-5)*SS,(x+5)*SS,(y+5)*SS),fill=(*INK,int(245*fade)))
            else:
                d.line(((x-8)*SS,(y-5)*SS,(x+8)*SS,(y+5)*SS),fill=(*INK,int(235*fade)),width=SS)
                d.line(((x-8)*SS,(y+5)*SS,(x+8)*SS,(y-5)*SS),fill=(*INK,int(235*fade)),width=SS)
            if unit.get('show_label',True) and unit.get('label'):
                dx,dy=unit.get('label_offset',[0,-30])
                label(overlay,(x+dx,y+dy),unit['label'],16,CREAM,fade)
        # END H3 BATTLE ATLAS TACTICS
        labels=self.geography_labels(s,cam,fade);overlay.alpha_composite(labels)
        for item in s.get('callouts',[]):
            age=t-cue_start(s,item.get('cue',0))
            if age<0:continue
            x,y=screen(item['pos'],cam);dx,dy=item.get('offset',[0,-56]);op=1 if s.get('_still') else fade*smooth(age/.8)
            if 60<x<W-60 and 190<y<H-210:
                d=ImageDraw.Draw(overlay);d.line((x*SS,y*SS,(x+dx)*SS,(y+dy+18)*SS),fill=(*GOLD,int(180*op)),width=2*SS)
                label(overlay,(x+dx,y+dy),item['text'],item.get('size',23),GOLD,op)
        small=cv2.resize(np.asarray(overlay),(W,H),interpolation=cv2.INTER_AREA)
        im=Image.alpha_composite(im.convert('RGBA'),Image.fromarray(small))
        im.alpha_composite(self.shade)
        hud=self.hud(s)
        if fade<1:
            hud=hud.copy();hud.putalpha(hud.getchannel('A').point(lambda v:round(v*fade)))
        im.alpha_composite(hud)
        d=ImageDraw.Draw(im)
        elapsed=s['start']+t;d.line((56,1042,56+1808*elapsed/self.total,1042),fill=GOLD,width=3)
        d.text((W-56,929),f'{stamp(elapsed)[3:]} / {stamp(self.total)[3:]}',font=font(16),fill=CREAM,anchor='ra')
        # A locator provides continuous Europe/Mediterranean context during close-ups.
        if cam[2]<30:
            mini=self.locator(cam);im.alpha_composite(mini,(1580,703))
        if s.get('tactical_diagram'):
            self.diagram(im,s,t,fade)
        for item in s.get('commanders',[]):
            age=t-cue_start(s,item['cue'])
            # BEGIN H3 OPENING LAYOUT
            if s.get('mode')=='opening' and not s.get('_still'):age-=6
            # END H3 OPENING LAYOUT
            if age<0 or (age>13 and not s.get('_still')):continue
            c=self.data['commanders'][item['id']];card=Image.new('RGBA',(290,388),(*INK,234))
            photo=ImageOps.fit(Image.open(ROOT/c['portrait']).convert('RGB'),(266,267),method=Image.Resampling.LANCZOS,centering=(.5,0))
            card.paste(photo,(12,12));cd=ImageDraw.Draw(card)
            cd.text((15,286),c['name'],font=font(31,'serif'),fill=CREAM)
            notes=c.get('portrait_note',['Ritratto storico','Provenienza e licenza nei crediti'])
            cd.text((15,330),notes[0],font=font(13),fill=MUTED)
            cd.text((15,351),notes[1],font=font(12),fill=MUTED)
            op=1 if s.get('_still') else fade*min(smooth(age/.8),smooth((13-age)/1.2));card.putalpha(card.getchannel('A').point(lambda v:round(v*op)))
            im.alpha_composite(card,(56,197))
        if not s.get('_still') and s.get('mode')=='opening' and t<6:
            op=1-smooth((t-3)/3);hero=Image.new('RGBA',(W,H));hd=ImageDraw.Draw(hero)
            hd.rounded_rectangle((55,300,705,621),radius=10,fill=(*INK,210))
            hd.text((85,324),self.data['subtitle'].upper(),font=font(22),fill=GOLD)
            size=143
            while hd.textlength(self.data['short_title'],font=font(size,'display'))>590:size-=1
            hd.text((80,362),self.data['short_title'].upper(),font=font(size,'display'),fill=CREAM)
            hd.text((88,537),self.data['display_date']+'  /  Una storia attraverso le mappe',font=font(21),fill=CREAM)
            hero.putalpha(hero.getchannel('A').point(lambda v:round(v*op)));im.alpha_composite(hero)
        return im.convert('RGB')

    def diagram(self,im,s,t,fade):
        spec=s['tactical_diagram'];start=cue_start(s,spec.get('cue',1));age=t-start
        if age<0:return
        p=1 if s.get('_still') else smooth(age/max(4,s['duration']-start-1));x,y,w,h=spec.get('panel',[56,204,710,480])
        card=Image.new('RGBA',(w*SS,h*SS));d=ImageDraw.Draw(card)
        d.rounded_rectangle((0,0,w*SS-1,h*SS-1),radius=14*SS,fill=(*INK,242),outline=(*GOLD,110),width=SS)
        d.text((26*SS,20*SS),spec['title'],font=font(24*SS,'display'),fill=CREAM)
        d.text((26*SS,58*SS),'Schema illustrativo · non in scala geografica',font=font(13*SS),fill=MUTED)
        def px(q):return (q[0]*w*SS,(95+q[1]*(h-135))*SS)
        for line in spec.get('routes',[]):
            pts=partial([px(q) for q in line['points']],p)
            d.line(pts,fill=(*self.colors[line['side']],230),width=4*SS,joint='curve')
            if len(pts)>1:
                ex,ey=pts[-1];ax,ay=pts[-2];a=math.atan2(ey-ay,ex-ax)
                d.polygon([(ex,ey),(ex-16*SS*math.cos(a)+7*SS*math.sin(a),ey-16*SS*math.sin(a)-7*SS*math.cos(a)),(ex-16*SS*math.cos(a)-7*SS*math.sin(a),ey-16*SS*math.sin(a)+7*SS*math.cos(a))],fill=self.colors[line['side']])
        for unit in spec['units']:
            q=[a+(b-a)*p for a,b in zip(unit['pos'],unit.get('end',unit['pos']))];ux,uy=px(q);c=self.colors[unit['side']]
            d.rounded_rectangle((ux-18*SS,uy-8*SS,ux+18*SS,uy+8*SS),radius=2*SS,fill=c,outline=CREAM,width=SS)
        d.text((24*SS,(h-34)*SS),'ORO: CARTAGINESI     ROSSO: ROMANI',font=font(13*SS),fill=CREAM)
        card=Image.fromarray(cv2.resize(np.asarray(card),(w,h),interpolation=cv2.INTER_AREA))
        op=fade*smooth(age/.8);card.putalpha(card.getchannel('A').point(lambda v:round(v*op)));im.alpha_composite(card,(x,y))

    def locator(self,cam):
        if not hasattr(self,'mini'):
            info,levels,_=self.atlas.layers[0];view=self.data.get('atlas_locator',[7,40,43]);self.mini_cam=(view[0],merc(view[1]),view[2])
            self.mini=self.atlas.warp(info,levels,self.mini_cam)
            self.mini=Image.fromarray(self.mini).resize((280,158),Image.Resampling.LANCZOS).convert('RGBA')
        im=self.mini.copy();d=ImageDraw.Draw(im)
        x=W/2+(cam[0]-self.mini_cam[0])*W/self.mini_cam[2];y=H/2-(cam[1]-self.mini_cam[1])*W/self.mini_cam[2]
        rx=cam[2]*W/self.mini_cam[2]/2;ry=rx*H/W
        rect=((x-rx)*280/W,(y-ry)*158/H,(x+rx)*280/W,(y+ry)*158/H)
        d.rectangle(rect,outline=GOLD,width=2);d.rectangle((0,0,279,157),outline=(*GOLD,150),width=1)
        return im
