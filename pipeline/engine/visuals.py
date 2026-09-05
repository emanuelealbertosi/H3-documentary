"""Cinematic map animation, commander portraits, troop movement and time-based overlays."""
from functools import lru_cache
import math
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageOps,ImageFilter
from .common import ROOT,stamp
from .cartography import Cartography

W,H=1920,1080
INK=(15,25,29); CREAM=(241,231,207); GOLD=(208,179,115); MUTED=(175,186,177)
COLORS={'fr':(102,164,227),'allied':(237,132,113),'pr':(229,197,109)}

@lru_cache(maxsize=128)
def font(size,kind='sans'):
    files={'sans':'Manrope[wght].ttf','display':'BebasNeue-Regular.ttf','serif':'CormorantGaramond[wght].ttf'}
    result=ImageFont.truetype(str(ROOT/'assets/fonts'/files[kind]),size)
    if kind=='sans':result.set_variation_by_axes([550])
    elif kind=='serif':result.set_variation_by_axes([500])
    return result

def txt(draw,xy,text,size=24,fill=CREAM,kind='sans',**kwargs):
    draw.text(xy,str(text),font=font(size,kind),fill=fill,**kwargs)

def wrap(draw,text,max_width,size,kind='sans'):
    words=text.split(); lines=[]; line=''
    for w in words:
        candidate=(line+' '+w).strip()
        if draw.textlength(candidate,font=font(size,kind))>max_width and line:
            lines.append(line); line=w
        else: line=candidate
    if line:lines.append(line)
    return lines

def ease(t):
    t=max(0,min(1,t)); return t*t*(3-2*t)

def cue_time(s,index): return s['cues'][min(index,len(s['cues'])-1)]['start']

def cue_progress(s,item,t):
    if s.get('_still'):return item.get('_still_progress',1)
    start=cue_time(s,item.get('cue',0)); end=cue_time(s,item['end_cue']) if item.get('end_cue') is not None else min(s['duration']-.8,start+max(5,s['cues'][item.get('cue',0)]['end']-start))
    return ease((t-start)/max(1,end-start))

def along(points,p):
    if len(points)<2:return points[0]
    lengths=[math.dist(a,b) for a,b in zip(points,points[1:])]; total=sum(lengths)
    target=p*total
    for a,b,l in zip(points,points[1:],lengths):
        if target<=l: return tuple(a[i]+(b[i]-a[i])*target/max(l,1e-8) for i in range(2))
        target-=l
    return points[-1]

@lru_cache(maxsize=32)
def portrait(path,framing=None):
    im=Image.open(ROOT/path).convert('RGB')
    # Crop the painted figure, keeping the head and shoulders in full-length portraits.
    # Source files remain untouched. These are framing choices within the video compositor.
    if framing:
        l,t,r,b=framing; im=im.crop((int(l*im.width),int(t*im.height),int(r*im.width),int(b*im.height)))
    return ImageOps.fit(im,(326,373),method=Image.Resampling.LANCZOS,centering=(.5,.25))

class Visuals:
    def __new__(cls,timeline):
        if timeline.get('presentation_mode')=='slides':
            from .slide_visuals import SlideVisuals
            return SlideVisuals(timeline)
        # BEGIN H3 IMAGE INSETS
        if timeline.get('user_media'):
            from .image_insets import InsetVisuals
            return InsetVisuals(timeline)
        # END H3 IMAGE INSETS
        if timeline.get('visual_style')=='history':
            from .history_visuals import HistoryVisuals
            return HistoryVisuals(timeline)
        if timeline.get('visual_style')=='atlas':
            from .atlas import AtlasVisuals
            return AtlasVisuals(timeline)
        return super().__new__(cls)

    def __init__(self,timeline):
        self.data=timeline
        if timeline.get('_still'):
            from .still_render import static_cartography
            self.maps={k:static_cartography(v,timeline['slug'],k,timeline['_still_cache']) for k,v in timeline['maps'].items()}
        else:self.maps={k:Cartography(v,timeline['slug'],k) for k,v in timeline['maps'].items()}
        for faction in timeline.get('factions',[]):COLORS[faction['id']]=tuple(faction['color'])
        self.total=timeline['duration']; self.static={}; self.cards={}; self.overlay=self.make_overlay()
        self.grids=[]

    def make_overlay(self):
        arr=np.zeros((H,W,4),dtype=np.uint8); arr[:,:,:3]=INK
        yy,xx=np.mgrid[:H,:W]
        alpha=np.maximum(np.clip((450-xx)/110,0,1)*.91,
          np.maximum(np.clip((195-yy)/90,0,1)*.94,np.clip((yy-884)/82,0,1)*.98))
        # Modest corner vignette preserves terrain detail.
        alpha=np.maximum(alpha,np.clip((((xx-1100)/1450)**2+((yy-520)/950)**2)*.15,0,.24))
        arr[:,:,3]=(alpha*255).astype(np.uint8)
        return Image.fromarray(arr)

    def static_hud(self,s):
        if s['id'] in self.static:return self.static[s['id']]
        im=Image.new('RGBA',(W,H)); d=ImageDraw.Draw(im)
        txt(d,(64,34),'ATLANTE DELLE BATTAGLIE',20,GOLD)
        d.line((64,74,1856,74),fill=(*GOLD,95),width=1)
        title_size=80
        while d.textlength(s['title'],font=font(title_size,'display'))>1390:title_size-=2
        txt(d,(62,85),s['title'],title_size,CREAM,'display')
        txt(d,(65,181),s['kicker'],20,MUTED)
        txt(d,(1850,29),f'{int(s["id"]):02} / {len(self.data["scenes"]):02}',24,GOLD,anchor='ra')
        # Fixed date window and map orientation.
        d.rounded_rectangle((1440,111,1856,170),radius=4,fill=(*INK,220),outline=(*GOLD,90),width=1)
        txt(d,(1648,128),s['date'],19,CREAM,anchor='ma')
        txt(d,(64,228),'LA SITUAZIONE',17,GOLD)
        d.line((64,261,393,261),fill=(*GOLD,90),width=1)
        txt(d,(1778,231),'N',24,CREAM,anchor='mm')
        d.line((1778,250,1778,306),fill=(*CREAM,200),width=2)
        d.polygon([(1778,246),(1770,267),(1786,267)],fill=(*CREAM,230))
        txt(d,(1778,329),self.data['maps'][s['map']].get('north_label',''),16,MUTED,anchor='mm')
        # Three sides stay identified throughout the film.
        x=66
        for faction in self.data['factions']:
            name,side=faction['label'],faction['id']
            d.rounded_rectangle((x,941,x+25,959),radius=2,fill=COLORS[side])
            txt(d,(x+37,938),name,17,CREAM)
            x+=37+d.textlength(name,font=font(17))+80
        txt(d,(1855,940),'Unità aggregate · effectifs indicativi'.replace('effectifs','effettivi'),16,MUTED,anchor='ra')
        txt(d,(65,987),s['note'],15,MUTED)
        # Chapters, with the current one highlighted.
        left,right=64,1856; span=right-left
        for other in self.data['scenes']:
            x1=left+span*other['start']/self.total; x2=left+span*other['end']/self.total-3
            d.rectangle((x1,1042,x2,1045),fill=(*GOLD,80))
        self.static[s['id']]=im
        return im

    def commander_card(self,id):
        if id in self.cards:return self.cards[id]
        commander=self.data['commanders'][id]; col=COLORS[commander['side']]
        im=Image.new('RGBA',(390,513)); d=ImageDraw.Draw(im)
        framing=self.data.get('framing',{}).get(id)
        im.paste(portrait(commander['portrait'],tuple(framing) if framing else None),(0,0))
        # Feather portrait into its caption, with a discreet coloured keyline.
        grad=Image.new('RGBA',(326,150)); ar=np.zeros((150,326,4),dtype=np.uint8); ar[:,:,:3]=INK; ar[:,:,3]=np.linspace(0,255,150).astype(np.uint8)[:,None]
        im.alpha_composite(Image.fromarray(ar),(0,223))
        d=ImageDraw.Draw(im); d.rectangle((0,0,3,372),fill=col)
        size=41
        while d.textlength(commander['name'],font=font(size,'serif'))>302:size-=1
        txt(d,(19,334),commander['name'],size,CREAM,'serif')
        for i,line in enumerate(wrap(d,commander['subtitle'],310,17)):txt(d,(0,390+i*26),line,17,MUTED)
        if commander.get('image_credit'):
            txt(d,(0,475),commander['image_credit'],13,MUTED)
        self.cards[id]=im
        return im

    def arrow(self,d,points,color,p,t,kind='attack'):
        if p<=0:return
        # Curved paths via Catmull-Rom interpolation would overshoot tactical waypoints;
        # use the author-provided path with round joints to retain geographic intent.
        distances=[math.dist(a,b) for a,b in zip(points,points[1:])]; total=sum(distances)
        if total<3:return
        pts=[along(points,float(k)) for k in np.linspace(0,p,max(3,int(total*p/5)))]
        if kind in ('retreat','plan','fire'):
            for i in range(len(pts)-1):
                if (i+int(t*4))%6<3:d.line((pts[i],pts[i+1]),fill=(*color,200),width=4 if kind!='fire' else 3)
        else:
            d.line(pts,fill=(7,14,17,130),width=15,joint='curve')
            d.line(pts,fill=(*color,210),width=9,joint='curve')
            d.line(pts,fill=(255,249,221,50),width=2,joint='curve')
            for k in range(3):
                phase=((t*.14+k/3)%1)*p
                fx,fy=along(points,phase)
                d.ellipse((fx-3,fy-3,fx+3,fy+3),fill=(255,244,208,185))
        x,y=pts[-1]; ax,ay=pts[max(0,len(pts)-4)]; angle=math.atan2(y-ay,x-ax)
        tip=20 if kind!='fire' else 12
        d.polygon([(x+math.cos(angle)*6,y+math.sin(angle)*6),
                   (x-tip*math.cos(angle)+tip*.57*math.sin(angle),y-tip*math.sin(angle)-tip*.57*math.cos(angle)),
                   (x-tip*math.cos(angle)-tip*.57*math.sin(angle),y-tip*math.sin(angle)+tip*.57*math.cos(angle))],fill=(*color,235))

    def tokens(self,d,u,xy,scale,t):
        x,y=xy; n=u['count']; col=COLORS[u['side']]; kind=u.get('kind','infantry')
        wid=28; sep=34; total=n*sep
        for k in range(n):
            bx=x+(k-(n-1)/2)*sep; by=y
            d.rounded_rectangle((bx-wid/2+3,by-10+6,bx+wid/2+3,by+10+6),radius=2,fill=(7,14,19,145))
            if kind=='square':
                d.rectangle((bx-15,by-15,bx+15,by+15),fill=(*col,250),outline=CREAM,width=1)
                d.rectangle((bx-8,by-8,bx+8,by+8),fill=INK)
            else:
                d.rounded_rectangle((bx-wid/2,by-10,bx+wid/2,by+10),radius=2,fill=col,outline=CREAM,width=1)
                if kind=='artillery':
                    d.ellipse((bx-4,by-4,bx+4,by+4),fill=INK)
                    d.line((bx,by+4,bx,by-7),fill=INK,width=3)
                elif kind=='armor':d.ellipse((bx-10,by-5,bx+10,by+5),outline=INK,width=2)
                elif kind=='air':
                    d.line((bx-10,by,bx+10,by),fill=INK,width=2)
                    d.line((bx,by-7,bx,by+7),fill=INK,width=2)
                    d.line((bx-4,by+5,bx+4,by+5),fill=INK,width=2)
                elif kind=='cavalry':d.line((bx-10,by+7,bx+10,by-7),fill=INK,width=2)
                else:
                    d.line((bx-10,by-7,bx+10,by+7),fill=INK,width=1)
                    d.line((bx-10,by+7,bx+10,by-7),fill=INK,width=1)
        return (x-total/2,y-15,x+total/2,y+15)

    def label(self,d,xy,text,size=19,fill=CREAM,anchor='mm'):
        x,y=xy; box=d.textbbox((x,y),text,font=font(size),anchor=anchor)
        d.rounded_rectangle((box[0]-7,box[1]-4,box[2]+7,box[3]+4),radius=3,fill=(*INK,217))
        txt(d,(x,y),text,size,fill,anchor=anchor)
        return (box[0]-7,box[1]-4,box[2]+7,box[3]+4)

    def frame(self,s,t):
        progress=ease(t/s['duration']); cam=[a+(b-a)*progress for a,b in zip(s['camera_start'],s['camera_end'])]
        m=self.maps[s['map']]; im=m.frame(cam)
        # Subtle illustrated influence zones, under the tactical symbols.
        tactical=Image.new('RGBA',(W,H)); d=ImageDraw.Draw(tactical)
        if s.get('mode') not in ('aftermath',):
            for zone in s.get('zones',m.spec.get('zones',[])):
                d.polygon([m.screen(x,cam) for x in zone['points']],fill=(*COLORS[zone['side']],15))
        for front in s.get('frontlines',[]):
            if t<cue_time(s,front.get('cue',0)):continue
            if front.get('until') is not None and t>=cue_time(s,front['until']):continue
            points=[m.screen(p,cam) for p in front['points']]
            d.line(points,fill=(*COLORS[front['side']],195),width=4,joint='curve')
        for focus in s['focus']:
            start=cue_time(s,focus['cue'])
            if t<start:continue
            place=next(x for x in m.spec['landmarks'] if x['id']==focus['place'])
            x,y=m.screen(place['pos'],cam); col=COLORS.get(focus.get('side'),GOLD)
            phase=(t-start)%3/3; radius=26+phase*39
            d.ellipse((x-radius,y-radius,x+radius,y+radius),outline=(*col,int(130*(1-phase))),width=3)
            d.ellipse((x-24,y-24,x+24,y+24),outline=(*col,170),width=2)
        for a in s['arrows']:
            start=cue_time(s,a['cue'])
            if t<start:continue
            end=cue_time(s,a['end_cue']) if a.get('end_cue') is not None else s['duration']
            if t>end+.7:continue
            col=COLORS[a['side']]
            self.arrow(d,[m.screen(p,cam) for p in a['points']],col,cue_progress(s,a,t),t,a.get('kind','attack'))
        # Short smoke/flash events, generated analytically and tied to narration cues.
        for i,fx in enumerate(s['sfx']):
            age=t-cue_time(s,fx['cue'])
            if fx['type'] in ('cannon','musket') and 0<=age<2.4:
                points=[a['points'][-1] for a in s['arrows']] or [[cam[0],cam[1]]]
                x,y=m.screen(points[i%len(points)],cam)
                for j in range(7):
                    r=8+age*17+j; px=x+math.sin(j*17)*28+age*9; py=y+math.cos(j*7)*10-age*16
                    d.ellipse((px-r,py-r,px+r,py+r),fill=(205,199,175,int(max(0,48-age*20))))
                if age<.16:d.ellipse((x-7,y-7,x+7,y+7),fill=(255,223,134,220))
        im.paste(tactical,(0,0),tactical)
        labels=Image.new('RGBA',(W,H)); d=ImageDraw.Draw(labels); occupied=[]
        for place in m.spec['landmarks']:
            if s.get('visible_places') is not None and place['id'] not in s['visible_places']:continue
            x,y=m.screen(place['pos'],cam)
            if not 477<x<1858 or not 225<y<880:continue
            if place['kind']=='forest':
                txt(d,(x,y),place['name'],18,(194,207,174),anchor='mm')
            else:
                d.ellipse((x-4,y-4,x+4,y+4),fill=CREAM)
                offset=-30 if place['kind']=='ridge' else 29
                dx,dy=place.get('label_offset',[0,offset])
                occupied.append(self.label(d,(x+dx,y+dy),place['name'],20 if s['map']=='battle' else 22))
        if m.spec.get('show_river_names',s['map']=='campaign'):
            txt(d,(520,875),m.spec.get('region_label',''),16,CREAM)
            for r in m.spec['rivers']:
                x,y=m.screen(r['points'][len(r['points'])//2],cam)
                dx,dy=r.get('label_offset',[55,-18])
                if 500<x<1850 and 220<y<850:occupied.append(self.label(d,(x+dx,y+dy),r['name'],18,(158,201,210)))
        unit_rects=[]
        for u in s['units']:
            if t<cue_time(s,u.get('cue',0)) and u.get('cue',0)>0:continue
            if u.get('until') is not None and t>cue_time(s,u['until']):continue
            pos=along(u['path'],cue_progress(s,u,t)) if u['path'] else u['pos']
            x,y=m.screen(pos,cam)
            if not 465<x<1870 or not 224<y<901:continue
            self.tokens(d,u,(x,y),cam[2],t)
            target=(x,y-33)
            for dx,dy in [(0,-33),(0,-59),(0,36),(0,58),(-95,-35),(95,-35)]:
                box=d.textbbox((x+dx,y+dy),u['label'],font=font(17),anchor='mm')
                rect=(box[0]-9,box[1]-6,box[2]+9,box[3]+6)
                if rect[0]<465 or rect[2]>1858 or rect[1]<223 or rect[3]>913:continue
                if not any(rect[0]<b[2] and rect[2]>b[0] and rect[1]<b[3] and rect[3]>b[1] for b in occupied):
                    target=(x+dx,y+dy);break
            occupied.append(self.label(d,target,u['label'],17,COLORS[u['side']]))
        # A true scale reference for the longitude axis of this illustrative oblique map.
        km=m.spec.get('scale_km',1 if s['map']=='battle' else 10)
        px=km/(111.32*math.cos(math.radians(cam[1])))*m.spec['scale'][0]*cam[2]
        right=1818
        d.line((right-px,881,right,881),fill=CREAM,width=2)
        d.line((right-px,876,right-px,887),fill=CREAM,width=2); d.line((right,876,right,887),fill=CREAM,width=2)
        txt(d,(right-px/2,902),f'{km} km',16,CREAM,anchor='mm')
        im.paste(labels,(0,0),labels)
        im.paste(self.overlay,(0,0),self.overlay)
        hud=self.static_hud(s); im.paste(hud,(0,0),hud)
        # Side panel: commander introductions or a large chapter motif.
        d=ImageDraw.Draw(im)
        selected=None
        for c in s['commanders']:
            if t>=cue_time(s,c['cue']):selected=c
        if selected:
            card=self.commander_card(selected['id'])
            age=t-cue_time(s,selected['cue']); opacity=1 if s.get('_still') else ease(age/.65)
            if opacity<1:
                card=card.copy(); card.putalpha(card.getchannel('A').point(lambda x:int(x*opacity)))
            im.paste(card,(64,285),card)
            fact_y=782
        else:
            # Decorative campaign diagram changes through the chapter and leaves the map dominant.
            txt(d,(62,277),f'{int(s["id"]):02}',142,(*GOLD,100),'display')
            d.line((66,451,390,451),fill=(*GOLD,110),width=1)
            txt(d,(66,482),'OBIETTIVO',17,GOLD)
            lines=wrap(d,s['kicker'].capitalize(),322,37,'serif')
            for j,line in enumerate(lines):txt(d,(64,519+j*43),line,37,CREAM,'serif')
            fact_y=675
        d=ImageDraw.Draw(im)
        for i,f in enumerate(s['facts']):
            size=22 if i==0 else 18; col=GOLD if i==0 else CREAM
            lines=wrap(d,f,335,size)
            for line in lines:
                txt(d,(65,fact_y),line,size,col); fact_y+=size+9
        # Synced sentence topic: compact short extract is not used as a substitute for captions.
        current=next((c for c in s['cues'] if c['start']<=t<c['end']),None)
        elapsed=s['start']+t
        txt(d,(1856,990),f'{stamp(elapsed)[3:]} / {stamp(self.total)[3:]}',17,CREAM,anchor='ra')
        d.rectangle((64,1042,64+1792*elapsed/self.total,1045),fill=GOLD)
        if not s.get('_still') and s.get('mode')=='opening' and t<5.7:
            opacity=1-ease((t-4.0)/1.7)
            hero=Image.new('RGBA',(W,H)); hd=ImageDraw.Draw(hero)
            hd.rectangle((0,0,W,H),fill=(*INK,210))
            txt(hd,(960,322),self.data['display_date'],27,GOLD,anchor='mm')
            hero_size=min(210,int(1460/max(1,len(self.data['short_title']))*1.8))
            txt(hd,(960,482),self.data['short_title'],hero_size,CREAM,'display',anchor='mm')
            hd.line((730,615,1190,615),fill=GOLD,width=2)
            txt(hd,(960,677),self.data['subtitle'].upper(),33,CREAM,anchor='mm')
            txt(hd,(960,902),'UN DOCUMENTARIO STORICO ATTRAVERSO LE MAPPE',18,MUTED,anchor='mm')
            hero.putalpha(hero.getchannel('A').point(lambda x:int(x*opacity)))
            im.paste(hero,(0,0),hero)
        if not s.get('_still') and s.get('mode')=='ending' and t>s['duration']-5:
            age=t-(s['duration']-5)
            end=Image.new('RGBA',(W,H)); ed=ImageDraw.Draw(end)
            ed.rectangle((0,0,W,H),fill=(*INK,int(220*ease(age/2))))
            if age>1:
                txt(ed,(960,392),self.data['short_title'],108,CREAM,'display',anchor='mm')
                txt(ed,(960,505),self.data['display_date'],27,GOLD,anchor='mm')
                txt(ed,(960,622),'Ricerca · mappe · narrazione italiana',25,CREAM,anchor='mm')
                txt(ed,(960,675),'Fonti, licenze e progetto riproducibile nei file allegati',21,MUTED,anchor='mm')
            im.paste(end,(0,0),end)
        # Fade through the same ink colour at each chapter cut, without touching narration.
        fade=1 if s.get('_still') else min(ease(t/.32),ease((s['duration']-t)/.40))
        if fade<1:im=Image.blend(Image.new('RGB',(W,H),INK),im,fade)
        return im.convert('RGB')
