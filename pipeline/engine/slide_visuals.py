"""Deterministic black-canvas slides, without loading any geographic resource."""
from PIL import Image, ImageDraw, ImageOps
from .common import ROOT
from .visuals import font, wrap
from .image_insets import asset_path, signature, interval, rectangle


def placement(layout):
    spec=layout.get('slide') or {}
    mode=spec.get('mode','inset')
    if mode=='fullscreen':return (0,0,1920,1080)
    if mode=='inset':return rectangle(layout)
    w=round(max(.1,min(1,spec.get('width',.8)))*1920)
    h=round(max(.1,min(1,spec.get('height',.62)))*1080)
    x=round(max(0,min(1-w/1920,spec.get('x',.1)))*1920)
    y=round(max(0,min(1-h/1080,spec.get('y',.22)))*1080)
    return x,y,w,h


def motion(spec,progress,elapsed,duration):
    p=max(0,min(1,progress));p=p*p*(3-2*p)
    effect=spec.get('effect','fixed');zoom=1;dx=dy=0
    if effect=='zoom_in':zoom=1+.10*p
    elif effect=='zoom_out':zoom=1.10-.10*p
    elif effect.startswith('scroll_'):
        zoom=1.12;distance=.06*(2*p-1)
        if effect=='scroll_left':dx=-distance
        elif effect=='scroll_right':dx=distance
        elif effect=='scroll_up':dy=-distance
        elif effect=='scroll_down':dy=distance
    fade=min(.75,duration/4)
    opacity=max(0,min(1,elapsed/max(.001,fade),(duration-elapsed)/max(.001,fade))) if spec.get('fade') else 1
    return zoom,dx,dy,opacity


class SlideVisuals:
    def __init__(self,timeline):
        self.data=timeline;self.total=timeline['duration'];self.items={m['id']:m for m in timeline.get('user_media',[])}
        self.images={};self.fitted={};signature(timeline)

    def image(self,item):
        key=item['id']
        if key not in self.images:
            path=asset_path(item) if key in self.items else (ROOT/item['path']).resolve()
            if not path.is_relative_to((ROOT/'assets').resolve()):raise ValueError('Immagine fuori dagli asset del progetto.')
            with Image.open(path) as source:
                image=ImageOps.exif_transpose(source).convert('RGBA')
                image.thumbnail((2400,2400),Image.Resampling.LANCZOS);self.images[key]=image.copy()
        return self.images[key]

    def layer(self,canvas,item,layout,t,start,end,caption='',still=False):
        x,y,w,h=placement(layout);spec=layout.get('slide') or {};mode=spec.get('mode','inset')
        caption_height=72 if mode=='inset' and caption else 0
        ih=max(1,h-caption_height);fit=spec.get('fit',layout.get('fit','contain'))
        key=(item['id'],w,ih,fit)
        if key not in self.fitted:
            original=self.image(item)
            self.fitted[key]=ImageOps.fit(original,(w,ih),Image.Resampling.LANCZOS) if fit=='cover' else ImageOps.contain(original,(w,ih),Image.Resampling.LANCZOS)
        photo=self.fitted[key];duration=max(.001,end-start);elapsed=max(0,t-start)
        zoom,dx,dy,opacity=motion(spec,.5 if still else elapsed/duration,elapsed,duration)
        if still:opacity=1
        if zoom!=1:photo=photo.resize((max(1,round(photo.width*zoom)),max(1,round(photo.height*zoom))),Image.Resampling.BICUBIC)
        tile=Image.new('RGBA',(w,h),(0,0,0,0))
        # Clip within its assigned rectangle; scroll never paints over other boxes.
        image_area=Image.new('RGBA',(w,ih),(0,0,0,0))
        image_area.alpha_composite(photo,(round((w-photo.width)/2+dx*w),round((ih-photo.height)/2+dy*ih)))
        tile.alpha_composite(image_area)
        if mode=='inset':
            draw=ImageDraw.Draw(tile);draw.rectangle((0,0,w-1,h-1),outline=(205,176,114),width=2)
            if caption:
                draw.rectangle((1,ih,w-2,h-2),fill=(14,23,27,245))
                text=caption
                while draw.textlength(text,font=font(23))>w-28 and len(text)>1:text=text[:-2]+'…'
                draw.text((14,ih+18),text,font=font(23),fill=(242,232,210))
        if opacity<1:tile.putalpha(tile.getchannel('A').point(lambda a:round(a*opacity)))
        canvas.alpha_composite(tile,(x,y))

    def frame(self,scene,t):
        image=Image.new('RGBA',(1920,1080),(0,0,0,255));still=bool(scene.get('_still'))
        background=self.items.get(scene.get('background_asset_id'))
        if background and background.get('visual_state')!='blank' and not background.get('placeholder'):
            self.layer(image,background,background.get('layout',{}),t,0,scene['duration'],still=still)
        show_text=(background or {}).get('layout',{}).get('slide',{}).get('show_text',True)
        draw=ImageDraw.Draw(image)
        if show_text:
            # Stable text bands remain readable over any replacement photograph.
            draw.rectangle((0,0,1919,170),fill=(0,0,0,190))
            draw.text((64,32),str(scene.get('kicker') or self.data.get('short_title',''))[:110],font=font(20),fill=(205,176,114))
            title=str(scene.get('title',''));size=54
            while draw.textlength(title,font=font(size,'serif'))>1780 and size>24:size-=2
            draw.text((64,76),title,font=font(size,'serif'),fill=(247,239,222))
            facts=scene.get('facts') or []
            if facts:
                lines=wrap(draw,str(facts[0]),1780,27)[:2]
                draw.rectangle((0,945,1919,1079),fill=(0,0,0,190))
                for i,line in enumerate(lines):draw.text((64,972+i*35),line,font=font(27),fill=(235,229,215))
        visible_inset=False
        for inset in scene.get('image_insets',[]):
            start,end=interval(scene,inset)
            if not still and not start<=t<end:continue
            item=self.items.get(inset.get('asset_id'))
            if item:
                self.layer(image,item,inset.get('layout',item.get('layout',{})),t,start,end,inset.get('title',''),still)
                visible_inset=True
        # Authored artworks remain visible as thumbnails if no semantic inset uses them.
        for i,ident in enumerate(scene.get('asset_ids',[])):
            if visible_inset:break
            if ident in self.data.get('disabled_visual_asset_ids',[]):continue
            asset=next((a for a in self.data.get('visual_assets',[]) if a['id']==ident),None)
            if asset:
                self.layer(image,asset,asset.get('layout',{'x':.71,'y':.21,'width':.25,'fit':'contain'}),t,0,scene['duration'],asset.get('title',''),still)
                break
        # The black canvas itself is intentional. All temporal effects depend only on t.
        return image.convert('RGB')
