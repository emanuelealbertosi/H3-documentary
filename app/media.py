"""Local image library. Originals are immutable; productions take their own snapshot."""
import hashlib, io, re, secrets, shutil, unicodedata, warnings
from pathlib import Path
from typing import Literal
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, ConfigDict
from . import store

MAX_BYTES = 20 * 1024 * 1024
KINDS = ('person', 'place', 'topic', 'event', 'entity', 'scene')

class Binding(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    kind: Literal['person','place','topic','event','entity','scene'] = 'topic'
    label: str = Field(min_length=2, max_length=120)
    aliases: list[str] = Field(default_factory=list, max_length=12)

class Layout(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    x: float = Field(.71, ge=.02, le=.80)
    y: float = Field(.21, ge=.19, le=.65)
    width: float = Field(.25, ge=.16, le=.36)
    fit: Literal['contain','cover'] = 'contain'

class MediaEdit(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=120)
    credit: str = Field('', max_length=300)
    source: str = Field('', max_length=500)
    rights: str = Field('', max_length=300)
    enabled: bool = True
    bindings: list[Binding] = Field(default_factory=list, max_length=32)
    layout: Layout = Field(default_factory=Layout)

def folder(mid):
    if not re.fullmatch(r'[a-f0-9]{24}', mid): raise KeyError(mid)
    return store.DATA / 'media' / mid

def get(mid):
    path = folder(mid) / 'record.json'
    if not path.is_file(): raise KeyError(mid)
    return store.read_json(path)

def catalog():
    with store.LOCK:
        return sorted([store.read_json(p) for p in (store.DATA/'media').glob('*/record.json')], key=lambda r:r['created'], reverse=True)

def save(mid, value):
    with store.LOCK:
        record = get(mid)
        record.update(value.model_dump())
        record['updated'] = store.now()
        store.write_json(folder(mid)/'record.json', record)
        return record

def upload(raw, filename):
    if not raw or len(raw)>MAX_BYTES: raise ValueError('Usa un’immagine fino a 20 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as im:
                if im.format not in ('JPEG','PNG','WEBP'): raise ValueError('Formati supportati: JPG, PNG e WebP.')
                if im.width*im.height > 32_000_000: raise ValueError('L’immagine supera 32 megapixel.')
                if getattr(im,'n_frames',1)>1: raise ValueError('Scegli un’immagine fissa, senza animazione.')
                fmt=im.format
                im.load()
                rendered=ImageOps.exif_transpose(im).convert('RGBA')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
        raise ValueError('Immagine non valida o troppo grande.') from e
    mid=secrets.token_hex(12); dest=folder(mid); dest.mkdir(parents=True)
    name=filename.replace('\\','/').rsplit('/',1)[-1][:160]
    name=''.join(c for c in name if ord(c)>=32) or 'Immagine'
    original='original.'+{'JPEG':'jpg','PNG':'png','WEBP':'webp'}[fmt]
    (dest/original).write_bytes(raw)
    rendered.thumbnail((2560,2560),Image.Resampling.LANCZOS)
    rendered.save(dest/'image.png')
    thumb=Image.new('RGB',rendered.size,'#183a40');thumb.paste(rendered,mask=rendered.getchannel('A'))
    thumb.thumbnail((440,320),Image.Resampling.LANCZOS);thumb.save(dest/'thumb.jpg',quality=88)
    record=MediaEdit(title=Path(name).stem[:120] or 'Immagine').model_dump()
    record.update(id=mid,filename=name,original=original,created=store.now(),updated=store.now(),
                  width=rendered.width,height=rendered.height,sha256=hashlib.sha256(raw).hexdigest(),
                  image_sha256=hashlib.sha256((dest/'image.png').read_bytes()).hexdigest())
    with store.LOCK: store.write_json(dest/'record.json',record)
    return record

def normalized(text):
    text=''.join(c for c in unicodedata.normalize('NFKD',str(text).lower()) if not unicodedata.combining(c))
    return ' '.join(re.findall(r'\w+',text))

def mention(text, term):
    term=normalized(term)
    return bool(term and (' '+term+' ') in (' '+normalized(text)+' '))

def scene_matches(scene, item):
    """Literal names/aliases, no invented semantic inference. Cue indices follow TTS."""
    lines=scene.get('lines',[])
    if not lines: lines=[c.get('text','') for c in scene.get('cues',[])]
    matches=[]
    for i,line in enumerate(lines):
        if any(mention(line,t) for b in item['bindings'] for t in [b['label'],*b.get('aliases',[])]): matches.append(i)
    # Explicit scene association applies even if its title is not spoken.
    if not matches and any(b['kind']=='scene' and any(mention(scene.get('title',''),t) or scene.get('id')==t for t in [b['label'],*b.get('aliases',[])]) for b in item['bindings']):
        matches=[0] if lines else []
    return matches

def attach(pack, records, work):
    """Only matched assets enter the project. Existing checkpoints never change."""
    used={}; count=0
    for scene in pack['scenes']:
        cues={}
        for item in records:
            if not item['enabled']: continue
            for cue in scene_matches(scene,item): cues.setdefault(cue,[]).append(item)
        overlays=[]
        for cue, items in sorted(cues.items()):
            for slot,item in enumerate(items):
                used[item['id']]=item
                overlays.append(dict(asset_id=item['id'],cue=cue,slot=slot,slots=len(items),
                    title=item['title'],layout=item['layout'],sha256=item['image_sha256']))
        if overlays: scene['image_insets']=overlays;count+=len(overlays)
    if not used: return 0
    manifest=[]
    for mid,item in used.items():
        src=folder(mid); rel=Path('assets/user')/mid; dest=work/rel;dest.mkdir(parents=True,exist_ok=True)
        for name in (item['original'],'image.png'):
            expected=item['sha256'] if name==item['original'] else item['image_sha256']
            if hashlib.sha256((src/name).read_bytes()).hexdigest()!=expected: raise ValueError('Un’immagine è stata modificata sul disco: caricala nuovamente.')
            shutil.copy2(src/name,dest/name)
        entry=dict(item,path=(rel/'image.png').as_posix(),original_path=(rel/item['original']).as_posix())
        store.write_json(dest/'record.json',entry);manifest.append(entry)
    pack['user_media']=manifest
    # Uploaded material never inherits a blanket public-domain video license.
    if pack.get('video_license'):
        pack['base_video_license']=pack.pop('video_license')
    store.write_json(work/'assets/user/manifest.json',manifest)
    return count

def freeze(pid, enabled):
    path=store.JOBS/pid/'checkpoints/media-selection.json'
    with store.LOCK:
        if not path.exists():store.write_json(path,catalog() if enabled else [])
        return store.read_json(path)

def targets(pid):
    p=store.project(pid);out=[{'kind':'topic','label':p['topic']}]
    path=store.JOBS/pid/'checkpoints/outline.json'
    if path.exists():
        o=store.read_json(path)
        for key,kind in [('places','place'),('locations','place'),('commanders','person'),('persons','person'),('entities','entity'),('factions','entity'),('events','event'),('scenes','scene')]:
            rows=o.get(key,[])
            if isinstance(rows,dict):rows=rows.values()
            for r in rows:
                name=r.get('name') or r.get('title')
                if name:out.append({'kind':kind,'label':name})
    return out
