"""Generic licensed-asset acquisition for new battle packs. Rendering stays offline."""
from pathlib import Path
import json,hashlib,time
import requests
from .common import ROOT,read_json,write_json
from .image_rights import metadata_policy,usage_for

def _placeholder_portrait(path,title,manifests,kind='person'):
    """Create an explicitly generic card when an optional historical image cannot be licensed."""
    from PIL import Image,ImageDraw,ImageFont
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);seed=int(hashlib.sha256(title.encode('utf-8')).hexdigest()[:8],16)
    image=Image.new('RGB',(960,1200),(25+(seed%18),31+(seed//19%18),42+(seed//211%20)));draw=ImageDraw.Draw(image)
    for y in range(1200):
        shade=round(22*y/1200);draw.line((0,y,960,y),fill=(34+shade,39+shade,51+shade))
    gold=(211,166,89);ink=(14,18,25);draw.rectangle((44,44,916,1156),outline=gold,width=5)
    if kind=='place':
        draw.rectangle((170,570,790,950),fill=ink);draw.polygon([(135,570),(330,350),(490,570),(625,405),(825,570)],fill=ink)
        for x,h in [(230,150),(360,230),(505,175),(650,255)]:draw.rectangle((x,950-h,x+70,950),fill=(45,52,62))
    elif kind=='person':
        draw.ellipse((300,190,660,550),fill=ink);draw.polygon([(215,1000),(270,660),(390,535),(570,535),(690,660),(745,1000)],fill=ink)
    else:
        draw.rectangle((230,300,730,900),fill=ink,outline=gold,width=3)
        for y in range(440,800,90):draw.line((310,y,650,y),fill=(60,67,74),width=9)
    try:
        font=ImageFont.truetype(str(ROOT/'assets/fonts/Manrope[wght].ttf'),42);small=ImageFont.truetype(str(ROOT/'assets/fonts/Manrope[wght].ttf'),24)
    except OSError:font=small=ImageFont.load_default()
    draw.text((480,84),'LUOGO STORICO' if kind=='place' else 'FIGURA STORICA' if kind=='person' else 'IMMAGINE NON DISPONIBILE',font=small,fill=gold,anchor='ma')
    label=title[:34];draw.rectangle((70,1015,890,1128),fill=(19,23,31));draw.text((480,1072),label,font=font,fill=(238,232,216),anchor='mm')
    image.save(path,quality=92,subsampling=0)
    source='https://github.com/emanuelealbertosi/H3-documentary'
    description=f'Riquadro generico per {title}; non è una fotografia storica attribuita' if kind=='place' else f'Riquadro generico per {title}; non è un ritratto storico attribuito'
    info={'descriptionurl':source,'h3_placeholder':True,'h3_subject_kind':kind,'extmetadata':{'LicenseShortName':{'value':'CC0-1.0'},'Artist':{'value':'H3-documentary, grafica procedurale'},'ObjectName':{'value':description},'LicenseUrl':{'value':'https://creativecommons.org/publicdomain/zero/1.0/'}}}
    write_json(path.with_suffix('.metadata.json'),info)
    relative=path.relative_to(ROOT).as_posix();manifests.append({'path':relative,'url':source,'source':source,'license':'CC0-1.0 · grafica procedurale, non effigie storica','sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    print('Optional portrait unavailable; generated neutral card:',title,flush=True)

def acquire(pack):
    from .image_search import bounded_request
    session=requests.Session();session.headers['User-Agent']='DocumentariAI/1.0 (local educational production)'
    manifests=read_json(ROOT/'assets/manifest.json') if (ROOT/'assets/manifest.json').exists() else []
    usage=usage_for(pack)
    def request(url,params=None):
        for attempt in range(5):
            r=session.get(url,params=params,timeout=120)
            if r.status_code in (429,502,503,504):time.sleep(3*(attempt+1));continue
            r.raise_for_status();return r
        raise RuntimeError('Public source unavailable: '+url)
    def save(url,path,lic,source=None):
        dest=ROOT/path;dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            temp=dest.with_suffix(dest.suffix+'.part');temp.write_bytes(request(url).content);temp.replace(dest)
        if not any(x['path']==path for x in manifests):
            manifests.append(dict(path=path,url=url,source=source or url,license=lic,sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
            write_json(ROOT/'assets/manifest.json',manifests)
        print('Asset ready:',path,flush=True)
    for asset in pack.get('assets',[]):
        if asset.get('h3_image') or Path(asset['path']).suffix.lower() in {'.jpg','.jpeg','.png','.webp','.gif','.bmp','.tif','.tiff','.svg'}:
            # Direct editorial image URLs retain their stated rights, and pass
            # the same gate as discovered pictures before bytes are downloaded.
            info={'url':asset['url'],'descriptionurl':asset.get('source') or asset['url'],'h3_image_source':'editorial',
                  'extmetadata':{'LicenseShortName':{'value':asset.get('license','')},'LicenseUrl':{'value':asset.get('license_url','')},
                    'Artist':{'value':asset.get('credit') or asset.get('creator','')},'ObjectName':{'value':asset.get('title',Path(asset['path']).stem)}}}
            _acquire_image({'name':asset.get('title',Path(asset['path']).stem),'kind':'topic'},asset['path'],info,True,usage,manifests,bounded_request)
        else:save(asset['url'],asset['path'],asset['license'],asset.get('source'))
    for directory,name in [('bebasneue','BebasNeue-Regular.ttf'),('manrope','Manrope[wght].ttf'),('cormorantgaramond','CormorantGaramond[wght].ttf')]:
        base='https://raw.githubusercontent.com/google/fonts/main/ofl/'+directory+'/'
        save(base+name,'assets/fonts/'+name,'SIL Open Font License 1.1')
        save(base+'OFL.txt','assets/fonts/'+directory+'-OFL.txt','SIL Open Font License 1.1')
    # Chatterbox is installed and invoked by Studio in its own runtime. Its
    # model and optional reference recording are therefore not assets that
    # this generic downloader should try to resolve as a Kokoro ONNX file.
    if pack.get('voice_engine','kokoro') not in ('chatterbox','tts_api') and not (ROOT/pack['voice']).exists():
        spec=pack.get('voice_download')
        if not spec:raise ValueError('Missing local voice and voice_download descriptor.')
        for suffix in ['', '.json']:save(spec['url']+suffix,pack['voice']+suffix,spec['license'])
        save(spec['model_card'],str(Path(pack['voice']).parent/'MODEL_CARD').replace('\\','/'),spec['license'])
    for cid,c in pack['commanders'].items():
        subject={**c,'name':c.get('name',cid),'kind':c.get('kind','person')}
        _acquire_image(subject,c['portrait'],None,bool(c.get('portrait_optional')),usage,manifests,bounded_request)
    # Optional people and places that are spoken in the narration use the same
    # Commons licence gate. They are composed later as semantic inset cards.
    for item in pack.get('auto_visual_assets',[]):
        _acquire_image(item,item['path'],None,True,usage,manifests,bounded_request)
    write_json(ROOT/'assets/manifest.json',manifests)

def _acquire_image(subject,relative,info,optional,usage,manifests,request):
    """Keep licensed cached originals; Commons first, then a verified catalog fallback."""
    from .image_search import find_image,bounded_request
    from PIL import Image,UnidentifiedImageError
    import io,warnings
    path=ROOT/relative;metadata=path.with_suffix('.metadata.json');title=subject.get('name',Path(relative).stem)
    try:cached=read_json(metadata) if metadata.is_file() else None
    except (ValueError,OSError):cached=None
    if not isinstance(cached,dict):cached=None
    if path.is_file() and cached and metadata_policy(cached,usage)['allowed']:
        # Placeholders are an explicit saved outcome; a regeneration uses a fresh workspace.
        _record_image(manifests,relative,path,cached,usage);return
    if cached and not cached.get('h3_placeholder') and metadata_policy(cached,usage)['allowed']:info=cached
    elif cached and not metadata_policy(cached,usage)['allowed']:
        print('Immagine in cache esclusa dalla destinazione d’uso:',title,flush=True)
    errors=(requests.RequestException,RuntimeError,KeyError,TypeError,ValueError,OSError)
    if info is None:
        try:
            filename=subject.get('commons_file');page_title=subject.get('wikipedia_page') or title
            if not filename:
                for language in (('it','en') if subject.get('kind')=='place' else ('en','it')):
                    q=request(f'https://{language}.wikipedia.org/w/api.php',dict(action='query',titles=page_title,prop='pageimages',redirects=1,format='json')).json()
                    filename=next(iter(q['query']['pages'].values())).get('pageimage')
                    if filename:break
            if not filename:raise ValueError('Nessuna immagine principale: '+page_title)
            result=request('https://commons.wikimedia.org/w/api.php',dict(action='query',titles='File:'+filename.removeprefix('File:'),prop='imageinfo',iiprop='url|extmetadata',iiurlwidth=960,format='json')).json()
            images=next(iter(result['query']['pages'].values())).get('imageinfo',[])
            if not images:raise ValueError('Metadati Commons mancanti')
            info={**images[0],'h3_image_source':'wikimedia_commons'}
        except errors:info=None
    def download(candidate):
        if not candidate or not metadata_policy(candidate,usage)['allowed']:return False
        raw=bounded_request(candidate.get('thumburl') or candidate['url'],max_bytes=20*1024*1024).content
        # Validate content before replacing a cached file. Originals are never
        # overwritten through a shared hard link; project copies use atomic replace.
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            try:
                with Image.open(io.BytesIO(raw)) as im:
                    if im.format not in {'JPEG','PNG','WEBP'} or im.width*im.height>32_000_000 or getattr(im,'n_frames',1)>1:raise ValueError('Immagine non supportata')
                    im.verify()
            except (UnidentifiedImageError,Image.DecompressionBombError,Image.DecompressionBombWarning) as e:raise ValueError('Immagine non valida') from e
        path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.part')
        try:temp.write_bytes(raw);temp.replace(path)
        finally:temp.unlink(missing_ok=True)
        candidate.update(h3_placeholder=False,h3_subject_kind=subject.get('kind','person'),h3_asset_usage=usage)
        write_json(metadata,candidate);_record_image(manifests,relative,path,candidate,usage)
        print('Immagine trovata:',title,'·',candidate.get('h3_image_source','fonte editoriale'),flush=True)
        return True
    try:
        if download(info):return
    except errors:pass
    try:
        print('Ricerca alternativa di un’immagine con licenza compatibile:',title,flush=True)
        if download(find_image(bounded_request,subject,usage)):return
    except errors:pass
    if not optional:raise ValueError('Nessuna immagine con licenza compatibile per '+title)
    path.unlink(missing_ok=True);metadata.unlink(missing_ok=True)
    manifests[:]=[row for row in manifests if row.get('path')!=relative]
    _placeholder_portrait(path,title,manifests,subject.get('kind','person'))

def _record_image(manifests,relative,path,info,usage):
    policy=metadata_policy(info,usage);fields=info.get('extmetadata',{})
    entry=dict(path=relative,url=info.get('url',info.get('descriptionurl','')),source=info.get('descriptionurl',''),
      license=fields.get('LicenseShortName',{}).get('value',''),license_url=policy['license_url'],
      credit=fields.get('Attribution',{}).get('value','') or fields.get('Artist',{}).get('value',''),asset_usage=usage,
      noncommercial=policy['noncommercial'],sharealike=policy['sharealike'],image_source=info.get('h3_image_source','cache'),
      sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    if info.get('h3_license_evidence'):entry['license_evidence']=info['h3_license_evidence']
    manifests[:]=[row for row in manifests if row.get('path')!=relative];manifests.append(entry)
