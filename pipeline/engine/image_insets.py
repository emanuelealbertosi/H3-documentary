"""Additive compositor for user images, shared by legacy, atlas and history frames."""
import hashlib
from PIL import Image, ImageDraw, ImageEnhance, ImageOps
from .common import ROOT

def asset_path(item):
    path=(ROOT/item['path']).resolve()
    if not path.is_relative_to((ROOT/'assets/user').resolve()):raise ValueError('Image inset outside project assets/user')
    return path

def signature(timeline):
    out=[]
    for item in timeline.get('user_media',[]):
        digest=hashlib.sha256(asset_path(item).read_bytes()).hexdigest()
        if digest!=item['image_sha256']:raise ValueError('Image inset checksum changed; update the asset manifest')
        out.append((item['id'],digest))
    return out

def interval(scene, item):
    cues=scene.get('cues',[]);index=item['cue']
    if index<0 or index>=len(cues):return (0,0)
    start=cues[index]['start'];end=cues[index]['end']
    span=(end-start)/max(1,item.get('slots',1))
    slot=item.get('slot',0)
    return start+slot*span,start+(slot+1)*span

def rectangle(layout):
    width=round(max(.16,min(.36,layout.get('width',.25)))*1920)
    height=round(width*.75)+72
    x=round(max(.02,min(1-.02-width/1920,layout.get('x',.71)))*1920)
    y=round(max(.19,min(.80-height/1080,layout.get('y',.21)))*1080)
    return x,y,width,height

class InsetVisuals:
    def __init__(self,timeline):
        from .visuals import Visuals
        base=dict(timeline);base.pop('user_media',None)
        self.base=Visuals(base);self.items={m['id']:m for m in timeline['user_media']};self.cards={}
        signature(timeline)

    def __getattr__(self,name):return getattr(self.base,name)

    def card(self,item):
        from .visuals import font
        layout=item['layout'];x,y,w,h=rectangle(layout)
        key=(item['asset_id'],w,layout.get('fit'),item['title'])
        if key not in self.cards:
            tile=Image.new('RGBA',(w,h),(17,38,43,248));d=ImageDraw.Draw(tile)
            with Image.open(asset_path(self.items[item['asset_id']])) as original:
                original=original.convert('RGBA');size=(w-16,h-80)
                im=ImageOps.fit(original,size,Image.Resampling.LANCZOS) if layout.get('fit')=='cover' else ImageOps.contain(original,size,Image.Resampling.LANCZOS)
                tile.alpha_composite(im,(8+(size[0]-im.width)//2,8+(size[1]-im.height)//2))
            d.rectangle((0,0,w-1,h-1),outline=(209,181,118,230),width=2)
            title=item['title'];f=font(23)
            while d.textlength(title,font=f)>w-32 and len(title)>1:title=title[:-2]+'…'
            d.text((16,h-51),title,font=f,fill=(241,231,207))
            self.cards[key]=tile
        return self.cards[key],x,y

    def make_room(self,image,scene):
        """Reserve a stable area on non-map cards; never cover their text or artwork.

        The body is fitted as a whole, preserving the existing card composition.
        Header and chronology retain their original size. The arrangement lasts
        the entire scene so its text does not jump when a cue starts or ends.
        """
        from .history_visuals import NONMAP
        if self.data.get('visual_style')!='history' or scene.get('scene_type') not in NONMAP or not scene.get('image_insets'):return image
        rects=[rectangle(item['layout']) for item in scene['image_insets']]
        left=min(r[0] for r in rects)-24;right=max(r[0]+r[2] for r in rects)+24
        top=min(r[1] for r in rects)-24;bottom=max(r[1]+r[3] for r in rects)+24
        candidates=[(50,170,left,935),(right,170,1870,935),(50,170,1870,top),(50,bottom,1870,935)]
        # Also consider a middle column when images occupy both corners.
        edges=sorted({50,1870,*[max(50,r[0]-24) for r in rects],*[min(1870,r[0]+r[2]+24) for r in rects]})
        for a,b in zip(edges,edges[1:]):
            if all(b<=r[0]-24 or a>=r[0]+r[2]+24 for r in rects):candidates.append((a,170,b,935))
        def score(box):return min((box[2]-box[0])/1820,(box[3]-box[1])/765)
        box=max(candidates,key=score);scale=score(box)
        if scale<.20:raise ValueError('Riquadri troppo dispersi nella scena senza mappa: usa lo stesso lato per le immagini associate.')
        body=image.crop((50,170,1870,935));body=body.resize((round(1820*scale),round(765*scale)),Image.Resampling.LANCZOS)
        image=image.copy();ImageDraw.Draw(image).rectangle((50,170,1869,934),fill=(13,31,42))
        x=round(box[0]+(box[2]-box[0]-body.width)/2);y=round(box[1]+(box[3]-box[1]-body.height)/2)
        image.paste(body,(x,y));return image

    def backdrop(self,image,scene):
        """Blend an optional user image into a non-map card without hiding text."""
        ident=scene.get('background_asset_id');item=self.items.get(ident)
        if not item:return image
        with Image.open(asset_path(item)) as original:
            photo=ImageOps.fit(original.convert('RGB'),(1820,765),Image.Resampling.LANCZOS)
        photo=ImageEnhance.Color(photo).enhance(.82)
        photo=ImageEnhance.Contrast(photo).enhance(.92)
        photo=ImageEnhance.Brightness(photo).enhance(.47)
        body=image.crop((50,170,1870,935)).convert('RGB')
        mixed=Image.blend(photo,body,.60)
        # Restore headings, dates, graph labels and other bright authored marks.
        mask=body.convert('L').point(lambda value:max(0,min(255,(value-55)*4)))
        mixed.paste(body,(0,0),mask)
        result=image.copy();result.paste(mixed,(50,170));return result

    def frame(self,scene,t):
        image=self.base.frame(scene,t)
        if self.data.get('visual_style')=='history':
            image=self.backdrop(image,scene)
            image=self.make_room(image,scene)
        for item in scene.get('image_insets',[]):
            start,end=interval(scene,item)
            if not start<=t<end:continue
            tile,x,y=self.card(item)
            fade=min(.35,(end-start)/4)
            opacity=min(1,(t-start)/max(.001,fade),(end-t)/max(.001,fade))
            if opacity<1:
                tile=tile.copy();tile.putalpha(tile.getchannel('A').point(lambda a:round(a*opacity)))
            image=image.convert('RGBA');image.alpha_composite(tile,(x,y))
            return image.convert('RGB')
        return image

def credits(timeline):
    lines=['## Immagini e sfondi','Le immagini automatiche conservano provenienza e licenza della fonte. Le sostituzioni e gli sfondi caricati conservano le indicazioni dichiarate dall’utente. I file usati dal montaggio sono in assets/user.']
    for item in timeline.get('user_media',[]):
        origin='Ricerca automatica con controllo licenza' if item.get('origin')=='automatic' else 'Immagine caricata e collegata dall’utente'
        composition='Ridimensionamento e composizione come sfondo di scena.' if str(item.get('id','')).startswith('visual-background-') else 'Ridimensionamento e composizione in riquadro.'
        lines += [f"### {item['title']}",f"{origin}. File: {item['filename']}. Autore / attribuzione: {item.get('credit') or 'non indicata'}. Provenienza: {item.get('source') or 'caricamento locale'}. Diritti: {item.get('rights') or 'da specificare; nessuna licenza presunta'}. {composition} SHA-256: {item['sha256']}."]
    return lines
