"""Historical visual grammar atop the unchanged, stable geographic atlas."""
import math
from functools import lru_cache
import numpy as np,cv2
from PIL import Image,ImageDraw,ImageOps,ImageEnhance,ImageChops
from .common import ROOT
from .atlas import AtlasVisuals,camera,screen,partial,smooth,progress,label,polyline,W,H,SS,INK,CREAM,GOLD,MUTED
from .visuals import font,wrap
from .history_schema import interpolate_year,year_label,historical_value
from .history_territories import modern_areas,selected_layers,area_style,state_blend

PALETTE={'migration':(72,211,180),'population_transfer':(72,211,180),'trade':(247,186,75),'sea_trade':(68,184,231),'cultural_diffusion':(190,132,241),'religious_diffusion':(102,199,123),'technology_diffusion':(64,205,218),'journey':(244,164,96),'exploration':(74,205,193),'connection':(166,202,211),'influence':(204,139,231),'attack':(239,86,91),'invasion':(239,86,91),'retreat':(239,137,80),'campaign':(239,86,91),'expansion':(247,186,75)}
SEMANTICS={'migration':'Migrazione','population_transfer':'Trasferimento di popolazione','trade':'Scambi terrestri','sea_trade':'Scambi marittimi','cultural_diffusion':'Circolazione delle idee','religious_diffusion':'Diffusione religiosa','technology_diffusion':'Circolazione tecnica','journey':'Spostamento personale','exploration':'Esplorazione','connection':'Collegamento','influence':'Influenza','attack':'Attacco','invasion':'Invasione','retreat':'Ritirata','campaign':'Campagna','expansion':'Espansione'}
NONMAP={'timeline','person_intro','event_focus','comparison','data_visualization','quote','artwork','document','transition','summary'}

def textblock(d,xy,text,width,size=30,color=CREAM,kind='sans',maxlines=10):
    lines=wrap(d,str(text),width,size,kind)
    while len(lines)>maxlines and size>17:
        size-=1;lines=wrap(d,str(text),width,size,kind)
    for i,line in enumerate(lines):d.text((xy[0],xy[1]+i*int(size*1.3)),line,font=font(size,kind),fill=color)
    return len(lines)*int(size*1.3)

def territory_state(layer,year):
    states=sorted(layer.get('states',[]),key=lambda s:historical_value(s['year']))
    old=None;new=None
    for state in states:
        if historical_value(state['year'])<=historical_value(year):old=state
        else:new=state;break
    return old,new

class HistoryVisuals(AtlasVisuals):
    def __init__(self,data):
        super().__init__(data)
        self.events={e['id']:e for e in data.get('events',[])}
        self.people={p['id']:p for p in data.get('persons',[])}
        self.assets={p['id']:p for p in data.get('visual_assets',[])}
        self.disabled_assets=set(data.get('disabled_visual_asset_ids',[]))
        self.layers={p['id']:p for p in data.get('visual_layers',[])}
        self.static_cards={}
        yy,xx=np.mgrid[:H,:W]
        a=(np.clip(1-np.sqrt(((xx-700)/2000)**2+((yy-450)/1500)**2),0,1)*8).astype(np.uint8)
        bg=np.zeros((H,W,3),np.uint8)
        for c,b in enumerate(INK):bg[:,:,c]=b+a
        self.background=Image.fromarray(bg)

    def map_background(self,cam):
        """Give physical relief a richer documentary grade without changing geography."""
        im=self.atlas.frame(cam).convert('RGB')
        im=ImageEnhance.Color(im).enhance(1.32)
        im=ImageEnhance.Contrast(im).enhance(1.10)
        im=ImageEnhance.Brightness(im).enhance(.98)
        return im.convert('RGBA')

    def uses_map(self,s):
        """Keep geographic continuity for map-led stories without inventing a location."""
        direction=self.data.get('visual_direction') or self.data.get('metadata',{}).get('visual_direction',{})
        return s['scene_type'] not in NONMAP or (direction.get('map_led') and s['scene_type'] in {'event_focus','summary'})

    def frame(self,s,t):
        q=max(0,min(1,t/s['duration']));a,b=s['historical_range'];year=interpolate_year(a,b,q)
        kind=s['scene_type'];cam=camera(s,t)
        if not self.uses_map(s):
            im=self.card(s,t,year)
        else:
            im=self.map_background(cam)
            overlay=Image.new('RGBA',(W*SS,H*SS));d=ImageDraw.Draw(overlay)
            if modern_areas(self.data):
                value=historical_value(a)+(historical_value(b)-historical_value(a))*q
                self.territories(overlay,d,s,cam,value-1 if value<=0 else value)
            else:self.territories(overlay,d,s,cam,year)
            for m in s.get('movements',[]):self.movement(overlay,d,m,s,t,cam)
            self.network(overlay,d,s,t,cam)
            self.battle_symbols(overlay,d,s,t,cam)
            overlay.alpha_composite(self.geography_labels(s,cam,1))
            im.alpha_composite(Image.fromarray(cv2.resize(np.asarray(overlay),(W,H),interpolation=cv2.INTER_AREA)))
            im.alpha_composite(self.shade)
            self.map_key(im,s)
            if modern_areas(self.data):self.territory_legend(im,s,year)
        self.directed_overlays(im,s,t)
        self.header(im,s,year)
        self.chronology(im,s,t,year)
        return im.convert('RGB')

    def directed_overlays(self,im,s,t):
        """Opt-in map storytelling. Existing packs render byte-for-byte as before."""
        direction=self.data.get('visual_direction') or self.data.get('metadata',{}).get('visual_direction',{})
        if direction.get('version')!=1:return
        journey=s.get('schematic_journey')
        excluded={'person_intro','timeline','comparison','data_visualization','quote','artwork','document'}
        people=s.get('person_ids',[]) if direction.get('auto_persons') and s.get('scene_type') not in excluded and not s.get('image_insets') else []
        d=ImageDraw.Draw(im,'RGBA')
        if journey:
            # A compact lower-third preserves the map and never competes with the portrait.
            stops=journey['stops'];left=840;right=1475 if people else 1840;top=758;bottom=916
            d.rounded_rectangle((left,top,right,bottom),radius=14,fill=(*INK,232),outline=(*GOLD,155),width=2)
            d.text((left+22,top+14),'SEQUENZA NARRATIVA · TAPPE NON LOCALIZZATE',font=font(14),fill=GOLD)
            y=top+67;xs=[left+40+i*(right-left-80)/max(1,len(stops)-1) for i in range(len(stops))]
            d.line((xs[0],y,xs[-1],y),fill=(*MUTED,150),width=5)
            q=smooth(t/max(1,s['duration']));active=min(len(stops)-1,int(q*len(stops)))
            if active:d.line((xs[0],y,xs[active],y),fill=GOLD,width=7)
            for i,(x,label_text) in enumerate(zip(xs,stops)):
                r=12 if i<=active else 8;d.ellipse((x-r,y-r,x+r,y+r),fill=GOLD if i<=active else MUTED,outline=CREAM,width=2)
                textblock(d,(x-65,y+22),label_text,130,15,CREAM,maxlines=1)
            textblock(d,(left+22,bottom-23),journey['note'],right-left-44,11,MUTED,maxlines=1)
        if people:
            # Linked figures remain readable without replacing the geographic scene.
            slot=min(len(people)-1,int(max(0,min(.999,t/max(1,s['duration'])))*len(people)))
            person=self.people[people[slot]];x,y,w,h=1515,205,320,500
            # Put the portrait on the opposite side when a focal place would sit below it.
            if not journey:
                cam=camera(s,t)
                focus=[self.data['places'][ident]['pos'] for ident in s.get('location_ids',[]) if ident in self.data['places']]
                if any(screen(pos,cam)[0]>1440 for pos in focus):x=85
            d.rounded_rectangle((x,y,x+w,y+h),radius=15,fill=(*INK,238),outline=(*GOLD,150),width=2)
            path=person.get('portrait')
            if path and (ROOT/path).exists():
                with Image.open(ROOT/path) as original:
                    photo=ImageOps.fit(original.convert('RGB'),(288,330),Image.Resampling.LANCZOS,centering=(.5,.25))
                im.paste(photo,(x+16,y+16))
            else:
                d.ellipse((x+75,y+65,x+245,y+235),outline=(*GOLD,100),width=2)
                d.text((x+160,y+150),''.join(v[0] for v in person['name'].split()[:2]),font=font(64,'serif'),fill=GOLD,anchor='mm')
            textblock(d,(x+18,y+365),person['name'],w-36,30,CREAM,'serif',2)
            textblock(d,(x+18,y+438),person.get('role',''),w-36,17,MUTED,maxlines=2)

    def battle_symbols(self,im,d,s,t,cam):
        for unit in s.get('units',[]):
            p=progress(s,unit,t)
            if t<s['cues'][unit.get('cue',0)]['start']:continue
            pos=partial(unit.get('path',[unit['pos'],unit['pos']]),p)[-1]
            x,y=screen(pos,cam);col=self.colors.get(unit.get('side'),GOLD)
            # Compact illustrated badge: shadow, coloured body and a unit glyph.
            d.rounded_rectangle(((x-22)*SS,(y-15)*SS,(x+24)*SS,(y+17)*SS),radius=8*SS,fill=(*INK,125))
            d.rounded_rectangle(((x-24)*SS,(y-17)*SS,(x+22)*SS,(y+15)*SS),radius=8*SS,fill=(*col,245),outline=(*CREAM,235),width=2*SS)
            kind=unit.get('kind','infantry')
            if kind=='cavalry':
                d.arc(((x-12)*SS,(y-11)*SS,(x+6)*SS,(y+7)*SS),190,355,fill=(*INK,245),width=3*SS)
                d.line(((x-7)*SS,(y+5)*SS,(x+12)*SS,(y-8)*SS),fill=(*INK,245),width=3*SS)
            elif kind=='artillery':
                d.ellipse(((x-10)*SS,(y-7)*SS,(x+4)*SS,(y+7)*SS),outline=(*INK,245),width=3*SS)
                d.line(((x+2)*SS,(y-1)*SS,(x+13)*SS,(y-1)*SS),fill=(*INK,245),width=4*SS)
            else:
                d.line(((x-11)*SS,(y-8)*SS,(x+11)*SS,(y+8)*SS),fill=(*INK,245),width=3*SS)
                d.line(((x-11)*SS,(y+8)*SS,(x+11)*SS,(y-8)*SS),fill=(*INK,245),width=3*SS)
            if unit.get('label'):label(im,(x,y+28),unit['label'],18,CREAM)
        for arrow in s.get('arrows',[]):
            m={**arrow,'semantic':arrow.get('semantic','attack'),'color':self.colors.get(arrow.get('side'),PALETTE['attack'])}
            self.movement(im,d,m,s,t,cam)

    def territories(self,im,d,s,cam,year):
        if modern_areas(self.data):
            for layer in selected_layers(self.data,s):
                blended=state_blend(layer,year)
                for state,opacity in blended:self.paint_area(im,state,layer,cam,opacity)
                if blended and blended[-1][0].get('polygons') and layer.get('label_pos'):
                    x,y=screen(layer['label_pos'],cam)
                    if 65<x<W-65 and 170<y<735:label(im,(x,y),blended[-1][0].get('label',layer['label']),24,CREAM)
            return
        # State comes from absolute historical time, not previously rendered frames.
        # This makes seeking, parallel rendering and out-of-order previews identical.
        selected=s.get('territory_ids',list(self.layers))
        for ident in selected:
            layer=self.layers[ident]
            if layer.get('kind') not in ('territory','influence','cultural','linguistic','religious','alliance','contested'):continue
            state,nextstate=territory_state(layer,year)
            if not state:continue
            fade=1
            years=layer.get('transition_years',0)
            previous=[x for x in layer['states'] if historical_value(x['year'])<historical_value(state['year'])]
            if years and previous:
                previous=max(previous,key=lambda x:historical_value(x['year']))
                fade=smooth((historical_value(year)-historical_value(state['year']))/years)
                self.paint_state(d,previous,layer,cam,1-fade)
            self.paint_state(d,state,layer,cam,fade)
            if layer.get('label_pos'):
                x,y=screen(layer['label_pos'],cam)
                if 60<x<W-60 and 170<y<800:label(im,(x,y),state.get('label',layer['label']),24,CREAM)

    def paint_state(self,d,state,layer,cam,opacity):
        if opacity<=0:return
        col=tuple(state.get('color',layer.get('color',GOLD)))
        for poly in state.get('polygons',[]):
            pts=[screen(p,cam) for p in poly]
            scaled=[(x*SS,y*SS) for x,y in pts]
            d.polygon(scaled,fill=(*col,int(96*opacity)))
            # A soft outer edge separates a changing territory from detailed relief.
            polyline(d,pts+[pts[0]],(*INK,int(115*opacity)),7,False)
            polyline(d,pts+[pts[0]],(*col,int(245*opacity)),3,layer.get('schematic',True) or state.get('contested',False))

    def paint_area(self,im,state,layer,cam,opacity):
        if opacity<=0 or not state.get('polygons'):return
        style=area_style(layer,state);col=tuple(state.get('color',layer.get('color',GOLD)))
        area=Image.new('RGBA',im.size);draw=ImageDraw.Draw(area)
        mask=Image.new('L',im.size) if style['hatch'] else None
        for poly in state['polygons']:
            pts=[screen(p,cam) for p in poly];scaled=[(x*SS,y*SS) for x,y in pts]
            draw.polygon(scaled,fill=(*col,int(style['fill']*opacity)))
            if mask:ImageDraw.Draw(mask).polygon(scaled,fill=255)
            polyline(draw,pts+[pts[0]],(*INK,int(95*opacity)),7,style['dashed'])
            polyline(draw,pts+[pts[0]],(*col,int(230*opacity)),style['width'],style['dashed'])
        if mask:
            # Clip diagonal hatching to contested areas; deterministic at any frame order.
            hatch=Image.new('RGBA',im.size);hd=ImageDraw.Draw(hatch)
            for x in range(-im.height,im.width,24*SS):hd.line((x,0,x+im.height,im.height),fill=(*col,int(105*opacity)),width=2*SS)
            hatch.putalpha(ImageChops.multiply(hatch.getchannel('A'),mask));area.alpha_composite(hatch)
        im.alpha_composite(area)

    def territory_legend(self,im,s,year):
        rows=[]
        for layer in selected_layers(self.data,s):
            state,_=territory_state(layer,year)
            if state and state.get('polygons'):rows.append((layer,state,area_style(layer,state)))
        if not rows:return
        d=ImageDraw.Draw(im,'RGBA');x=60;y=170;width=435
        shown=rows[:4];height=24+len(shown)*52+(20 if len(rows)>4 else 0)
        d.rounded_rectangle((x,y,x+width,y+height),radius=12,fill=(*INK,226),outline=(*CREAM,60),width=1)
        for i,(layer,state,style) in enumerate(shown):
            top=y+12+i*52;col=tuple(state.get('color',layer.get('color',GOLD)))
            d.rounded_rectangle((x+15,top+5,x+37,top+27),radius=3,fill=(*col,155),outline=col,width=2)
            if style['hatch']:d.line((x+16,top+25,x+35,top+6),fill=CREAM,width=2)
            textblock(d,(x+50,top),state.get('label',layer['label']),width-65,20,CREAM,maxlines=1)
            d.text((x+50,top+27),style['label']+' · '+style['boundary'],font=font(12),fill=MUTED)
        if len(rows)>4:d.text((x+15,y+height-23),f'+ {len(rows)-4} altre aree sulla mappa',font=font(12),fill=MUTED)

    def semantic_marker(self,d,xy,angle,semantic,col,scale=1):
        """Draw a distinct endpoint glyph so a route does not always mean attack."""
        x,y=xy;u=SS*scale;dark=(*INK,235);light=(*CREAM,245)
        def pt(dx,dy):return ((x+dx*scale)*SS,(y+dy*scale)*SS)
        def box(r):return (*pt(-r,-r),*pt(r,r))
        d.ellipse(box(18),fill=(*INK,105))
        if semantic in ('attack','invasion','campaign','retreat','expansion'):
            length=27;half=12;tip=pt(0,0)
            back=pt(-length*math.cos(angle),-length*math.sin(angle))
            left=pt(-length*math.cos(angle)+half*math.sin(angle),-length*math.sin(angle)-half*math.cos(angle))
            right=pt(-length*math.cos(angle)-half*math.sin(angle),-length*math.sin(angle)+half*math.cos(angle))
            d.polygon([tip,left,back,right],fill=(*col,255),outline=dark)
            d.line((tip,back),fill=light,width=max(1,round(u)))
        elif semantic=='sea_trade':
            d.ellipse(box(17),fill=(*col,245),outline=light,width=max(1,round(2*u)))
            d.polygon([pt(-10,5),pt(11,5),pt(6,11),pt(-6,11)],fill=dark)
            d.polygon([pt(-1,-11),pt(-1,3),pt(9,3)],fill=light)
        elif semantic in ('migration','population_transfer'):
            d.ellipse(box(17),fill=(*col,245),outline=light,width=max(1,round(2*u)))
            for off in (-7,0,7):
                ox=off*math.sin(angle);oy=-off*math.cos(angle)
                a=pt(-7*math.cos(angle)+ox,-7*math.sin(angle)+oy)
                b=pt(7*math.cos(angle)+ox,7*math.sin(angle)+oy)
                d.line((a,b),fill=dark,width=max(1,round(2*u)))
        elif semantic in ('cultural_diffusion','religious_diffusion','technology_diffusion','influence'):
            d.ellipse(box(16),fill=(*col,238),outline=light,width=max(1,round(2*u)))
            d.ellipse(box(5),fill=light)
            for a in range(0,360,45):
                ca=math.cos(math.radians(a));sa=math.sin(math.radians(a))
                d.line((pt(8*ca,8*sa),pt(13*ca,13*sa)),fill=dark,width=max(1,round(2*u)))
        else:
            # Journey, exploration, trade and neutral connections use a compass pin.
            d.ellipse(box(17),fill=(*col,245),outline=light,width=max(1,round(2*u)))
            tip=pt(10*math.cos(angle),10*math.sin(angle))
            left=pt(-5*math.cos(angle)+5*math.sin(angle),-5*math.sin(angle)-5*math.cos(angle))
            right=pt(-5*math.cos(angle)-5*math.sin(angle),-5*math.sin(angle)+5*math.cos(angle))
            d.polygon([tip,left,right],fill=dark)

    def movement(self,im,d,m,s,t,cam):
        p=1 if m.get('complete') else progress(s,m,t)
        if p<=0:return
        semantic=m['semantic'];col=tuple(m.get('color',PALETTE[semantic]));points=[screen(x,cam) for x in m['points']]
        pts=partial(points,p);w=min(14,max(5,m.get('width',7)))
        uncertain=m.get('uncertain',False)
        # A stable three-layer ribbon reads cleanly over sea and relief alike.
        polyline(d,pts,(*INK,205),w+8,False)
        polyline(d,pts,(*col,250),w,uncertain)
        if not uncertain:polyline(d,pts,(*CREAM,105),max(1,w//3),False)
        if len(pts)>1:
            x,y=pts[-1];ax,ay=pts[-2];theta=math.atan2(y-ay,x-ax)
            self.semantic_marker(d,(x,y),theta,semantic,col)

    def network(self,im,d,s,t,cam):
        net=s.get('network',{})
        for edge in net.get('edges',[]):
            p1=self.data['places'][edge['from']]['pos'];p2=self.data['places'][edge['to']]['pos']
            m={**edge,'points':edge.get('points',[p1,p2]),'semantic':edge.get('semantic','connection'),'cue':edge.get('cue',0)}
            self.movement(im,d,m,s,t,cam)
        for node in net.get('nodes',[]):
            p=self.data['places'][node['location_id']];x,y=screen(p['pos'],cam);r=12
            col=tuple(node.get('color',GOLD));r=13
            d.ellipse(((x-r-5)*SS,(y-r-5)*SS,(x+r+5)*SS,(y+r+5)*SS),fill=(*INK,105))
            d.ellipse(((x-r)*SS,(y-r)*SS,(x+r)*SS,(y+r)*SS),fill=(*col,235),outline=(*CREAM,245),width=2*SS)
            d.ellipse(((x-4)*SS,(y-4)*SS,(x+4)*SS,(y+4)*SS),fill=(*INK,235))

    def header(self,im,s,year):
        d=ImageDraw.Draw(im)
        d.rectangle((0,0,W,148),fill=(*INK,242))
        d.text((60,28),self.data['short_title'].upper()+'  /  STORIE VISUALI',font=font(16),fill=GOLD)
        textblock(d,(57,58),s['title'].upper(),1410,53,CREAM,'display',1)
        direction=self.data.get('visual_direction') or self.data.get('metadata',{}).get('visual_direction',{})
        shown_date='SEQUENZA NARRATIVA' if direction.get('timeline_mode')=='sequence' else s.get('date',year_label(year))
        d.text((1860,36),shown_date,font=font(22),fill=CREAM,anchor='ra')
        if self.uses_map(s):
            d.text((1840,93),'N ↑',font=font(20),fill=MUTED,anchor='ra')
        d.line((60,143,1860,143),fill=(*GOLD,110),width=1)

    def map_key(self,im,s):
        d=ImageDraw.Draw(im)
        d.rounded_rectangle((55,765,815,915),radius=12,fill=(*INK,238))
        d.text((79,785),s['kicker'].upper(),font=font(16),fill=GOLD)
        textblock(d,(79,816),s['facts'][0],706,29,CREAM,'serif',2)
        semantic=[]
        for m in s.get('movements',[])+s.get('network',{}).get('edges',[]):
            sem=m.get('semantic','connection')
            if sem not in semantic:semantic.append(sem)
        for i,sem in enumerate(semantic[:3]):
            y=785+i*36
            d.rounded_rectangle((1030,y-3,1550,y+32),radius=5,fill=(*INK,230))
            col=PALETTE[sem]
            d.line((1050,y+12,1094,y+12),fill=(*INK,230),width=10)
            d.line((1050,y+12,1094,y+12),fill=col,width=6)
            self.semantic_marker(d,(1097,y+12),0,sem,col,.48)
            d.text((1115,y),SEMANTICS[sem],font=font(19),fill=CREAM)
        default_note='Aree e confini: significato e precisione nella legenda' if modern_areas(self.data) and selected_layers(self.data,s) else 'Collegamenti schematici · nessuna quantità implicita'
        notice=s.get('map_note',default_note)
        d.text((1858,904),notice[:100],font=font(13),fill=MUTED,anchor='ra')

    def chronology(self,im,s,t,year):
        d=ImageDraw.Draw(im);d.rectangle((0,938,W,H),fill=(*INK,250))
        direction=self.data.get('visual_direction') or self.data.get('metadata',{}).get('visual_direction',{})
        if direction.get('timeline_mode')=='sequence':
            index=next((i for i,row in enumerate(self.data['scenes']) if row['id']==s['id']),0);q=max(0,min(1,t/s['duration']))
            d.text((60,956),f'TAPPA {index+1} / {len(self.data["scenes"])}',font=font(26,'serif'),fill=GOLD)
            d.line((310,988,1640,988),fill=(67,89,95),width=3);d.line((310,988,310+1330*(index+q)/len(self.data['scenes']),988),fill=GOLD,width=3)
            d.text((1840,957),'Ordine del racconto',font=font(18),fill=MUTED,anchor='ra')
            d.text((1858,1036),f'{index+1:02} / {len(self.data["scenes"]):02}',font=font(22),fill=GOLD,anchor='ra')
            d.line((60,1053,1860,1053),fill=(*GOLD,90),width=2);return
        period=self.data.get('historical_period',{});lo=period.get('start',s['historical_range'][0]);hi=period.get('end',s['historical_range'][1])
        def x(y):return 250+1390*max(0,min(1,(historical_value(y)-historical_value(lo))/max(1,historical_value(hi)-historical_value(lo))))
        d.text((60,956),year_label(year),font=font(29,'serif'),fill=GOLD)
        d.line((250,988,1640,988),fill=(67,89,95),width=3)
        d.line((250,988,max(251,x(year)),988),fill=GOLD,width=3)
        # Fixed positions and a bounded number of labels prevent flicker/collisions.
        events=[e for e in self.events.values() if e.get('timeline',True)]
        if len(events)>8:events=[events[round(i*(len(events)-1)/7)] for i in range(8)]
        last=-1000
        for e in sorted(events,key=lambda e:e['year']):
            ex=x(e['year']);past=historical_value(e['year'])<=historical_value(year)
            d.ellipse((ex-4,984,ex+4,992),fill=GOLD if past else MUTED)
            if ex-last>150:
                d.text((ex,1005),year_label(e['year']),font=font(13),fill=MUTED,anchor='ma');last=ex
        ex=x(year);d.ellipse((ex-7,981,ex+7,995),fill=CREAM)
        d.text((1860,961),f'{int(s["id"]):02} / {len(self.data["scenes"]):02}',font=font(24),fill=GOLD,anchor='ra')
        d.text((1860,1030),'Geografia fisica: Natural Earth · rilievo Mapzen',font=font(11),fill=MUTED,anchor='ra')
        d.line((60,1053,1860,1053),fill=(45,65,73),width=3)
        d.line((60,1053,60+1800*(s['start']+t)/self.total,1053),fill=GOLD,width=3)

    def card(self,s,t,year):
        # Static text/images are cached. Only charts/timeline/camera advance with time.
        key=s['id']
        if key not in self.static_cards:
            im=self.background.copy().convert('RGBA');d=ImageDraw.Draw(im)
            kind=s['scene_type']
            asset_ids=[ident for ident in s.get('asset_ids',[]) if ident not in self.disabled_assets]
            if kind in ('artwork','document') and asset_ids:
                a=self.assets[asset_ids[0]];path=ROOT/a['path']
                picture=ImageOps.contain(Image.open(path).convert('RGB'),(1080,710),Image.Resampling.LANCZOS)
                im.paste(picture,(60+(1080-picture.width)//2,177+(710-picture.height)//2))
                d.text((1200,207),'OPERA' if kind=='artwork' else 'DOCUMENTO',font=font(18),fill=GOLD)
                y=251+textblock(d,(1200,251),a.get('title',s['title']),630,47,CREAM,'serif',4)
                y+=24+textblock(d,(1200,y+24),a.get('creator','')+' · '+a.get('date',''),620,23,MUTED,maxlines=3)
                textblock(d,(1200,y+50),s['facts'][0],630,30,CREAM,'serif',6)
                textblock(d,(1200,827),a.get('credit',a.get('license','')),630,14,MUTED,maxlines=3)
            elif kind=='person_intro' and s.get('person_ids'):
                p=self.people[s['person_ids'][0]]
                if p.get('portrait') and (ROOT/p['portrait']).exists():
                    photo=ImageOps.contain(Image.open(ROOT/p['portrait']).convert('RGB'),(670,710),Image.Resampling.LANCZOS);im.paste(photo,(60+(670-photo.width)//2,180+(710-photo.height)//2))
                else:
                    d.ellipse((195,245,565,615),outline=(*GOLD,100),width=2);d.text((380,430),''.join(w[0] for w in p['name'].split()[:2]),font=font(138,'serif'),fill=GOLD,anchor='mm')
                    d.text((380,670),'Ritratto non disponibile',font=font(17),fill=MUTED,anchor='mm')
                d.text((850,209),p.get('role','PERSONAGGIO STORICO').upper(),font=font(21),fill=GOLD)
                textblock(d,(845,260),p['name'],955,78,CREAM,'serif',2)
                d.text((850,462),p.get('period',''),font=font(25),fill=MUTED)
                textblock(d,(850,540),p.get('intro',s['facts'][0]),930,36,CREAM,'serif',6)
            elif kind=='comparison':
                cols=s.get('comparison',[])
                for i,c in enumerate(cols[:3]):
                    width=1710/max(1,len(cols[:3]));x=70+i*(width+25)
                    d.rounded_rectangle((x,220,x+width,860),radius=15,fill=(24,47,59),outline=(64,87,91),width=1)
                    d.rectangle((x+28,255,x+width-28,259),fill=GOLD)
                    textblock(d,(x+30,294),c['title'],width-60,39,CREAM,'serif',3)
                    textblock(d,(x+30,475),c['text'],width-60,29,MUTED,maxlines=9)
            elif kind=='quote' and s.get('quote'):
                quote=s['quote'];d.text((125,180),'“',font=font(180,'serif'),fill=GOLD)
                textblock(d,(250,300),quote['text'],1460,55,CREAM,'serif',6)
                textblock(d,(250,780),quote.get('author','')+' · '+quote['source'],1460,22,MUTED,maxlines=3)
            elif kind not in ('timeline','data_visualization'):
                d.text((120,219),s['kicker'].upper(),font=font(23),fill=GOLD)
                direction=self.data.get('visual_direction') or self.data.get('metadata',{}).get('visual_direction',{})
                width=1290 if direction.get('version')==1 and direction.get('auto_persons') and s.get('person_ids') else 1550
                textblock(d,(112,285),s['facts'][0],width,67,CREAM,'serif',4)
                cards=s.get('highlights',[])
                for i,c in enumerate(cards[:3]):
                    x=120+i*575;d.line((x,679,x+480,679),fill=GOLD,width=2);textblock(d,(x,716),c,490,27,MUTED,maxlines=5)
            self.static_cards[key]=im
        im=self.static_cards[key].copy()
        if s['scene_type'] in ('artwork','document') and any(ident not in self.disabled_assets for ident in s.get('asset_ids',[])):
            # A gentle camera push on the artwork alone; typography stays registered.
            region=self.static_cards[key].crop((60,177,1140,887))
            zoom=1+.025*smooth(t/s['duration']);w,h=region.size
            mx=(w-w/zoom)/2;my=(h-h/zoom)/2
            region=region.transform((w,h),Image.Transform.EXTENT,(mx,my,w-mx,h-my),Image.Resampling.BICUBIC)
            im.paste(region,(60,177))
        if s['scene_type']=='timeline':self.event_cards(im,s,t,year)
        if s['scene_type']=='data_visualization':self.chart(im,s,t)
        return im

    def event_cards(self,im,s,t,year):
        d=ImageDraw.Draw(im);events=[self.events[x] for x in s.get('event_ids',[])][:5]
        for i,e in enumerate(events):
            y=205+i*138;past=historical_value(e['year'])<=historical_value(year)
            d.line((321,y+23,321,min(885,y+155)),fill=GOLD if past else (67,89,95),width=3)
            d.ellipse((313,y+17,329,y+33),fill=GOLD if past else MUTED)
            d.text((279,y+7),year_label(e['year']),font=font(30,'serif'),fill=GOLD,anchor='ra')
            textblock(d,(375,y),e.get('title',e['description']),1400,34,CREAM,'serif',1)
            textblock(d,(375,y+51),e['description'],1400,23,MUTED,maxlines=2)

    def chart(self,im,s,t):
        d=ImageDraw.Draw(im);spec=s.get('chart')
        if not spec:
            textblock(d,(140,320),'Non sono disponibili dati quantitativi confrontabili.',1600,55,CREAM,'serif');return
        rows=spec['values'];values=[r['value'] for r in rows];lo=min(0,min(values));hi=max(values)
        span=max(1,hi-lo);p=smooth(t/min(5,s['duration']*.25));left=530;right=1730;top=285;bottom=800
        textblock(d,(120,190),spec.get('title',s['title']),1600,37,CREAM,'serif',1)
        if spec['kind']=='line':
            xs=[r.get('x',i) for i,r in enumerate(rows)];xmin=min(xs);xmax=max(xs);pts=[]
            for i,r in enumerate(rows):
                x=240+1450*(xs[i]-xmin)/max(1,xmax-xmin);y=bottom-(r['value']-lo)/span*460;pts.append((x,y))
                d.text((x,830),r['label'],font=font(19),fill=MUTED,anchor='ma')
                d.text((x,y-34),str(r['value']),font=font(23),fill=CREAM,anchor='ma')
            d.line(partial(pts,p),fill=GOLD,width=5)
            for x,y in pts:d.ellipse((x-6,y-6,x+6,y+6),fill=GOLD)
        else:
            step=min(130,500/max(1,len(rows)))
            zero=left+(0-lo)/span*(right-left)
            for i,r in enumerate(rows):
                y=top+i*step;end=zero+r['value']/span*(right-left)*p
                d.text((left-28,y+12),r['label'],font=font(26),fill=CREAM,anchor='ra')
                d.rounded_rectangle((min(zero,end),y,max(zero+.1,end),y+48),radius=5,fill=tuple(r.get('color',GOLD)))
                d.text((max(zero,end)+16,y+10),str(r['value'])+' '+spec.get('unit',''),font=font(23),fill=CREAM)
        textblock(d,(120,882),spec.get('note','')+' · Fonti: '+', '.join(spec['sources']),1680,16,MUTED,maxlines=2)
