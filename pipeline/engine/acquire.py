"""Generic licensed-asset acquisition for new battle packs. Rendering stays offline."""
from pathlib import Path
import json,hashlib,time
import requests
from .common import ROOT,read_json,write_json

def _placeholder_portrait(path,title,manifests):
    """Create an explicitly generic card when an optional historical image cannot be licensed."""
    from PIL import Image,ImageDraw,ImageFont
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);seed=int(hashlib.sha256(title.encode('utf-8')).hexdigest()[:8],16)
    image=Image.new('RGB',(960,1200),(25+(seed%18),31+(seed//19%18),42+(seed//211%20)));draw=ImageDraw.Draw(image)
    for y in range(1200):
        shade=round(22*y/1200);draw.line((0,y,960,y),fill=(34+shade,39+shade,51+shade))
    gold=(211,166,89);ink=(14,18,25);draw.rectangle((44,44,916,1156),outline=gold,width=5)
    draw.ellipse((300,190,660,550),fill=ink);draw.polygon([(215,1000),(270,660),(390,535),(570,535),(690,660),(745,1000)],fill=ink)
    try:
        font=ImageFont.truetype(str(ROOT/'assets/fonts/Manrope[wght].ttf'),42);small=ImageFont.truetype(str(ROOT/'assets/fonts/Manrope[wght].ttf'),24)
    except OSError:font=small=ImageFont.load_default()
    draw.text((480,84),'FIGURA STORICA',font=small,fill=gold,anchor='ma')
    label=title[:34];draw.rectangle((70,1015,890,1128),fill=(19,23,31));draw.text((480,1072),label,font=font,fill=(238,232,216),anchor='mm')
    image.save(path,quality=92,subsampling=0)
    source='https://github.com/emanuelealbertosi/H3-documentary'
    info={'descriptionurl':source,'extmetadata':{'LicenseShortName':{'value':'CC0-1.0'},'Artist':{'value':'H3-documentary, grafica procedurale'},'ObjectName':{'value':f'Riquadro generico per {title}; non è un ritratto storico attribuito'},'LicenseUrl':{'value':'https://creativecommons.org/publicdomain/zero/1.0/'}}}
    write_json(path.with_suffix('.metadata.json'),info)
    relative=path.relative_to(ROOT).as_posix();manifests.append({'path':relative,'url':source,'source':source,'license':'CC0-1.0 · grafica procedurale, non effigie storica','sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    print('Optional portrait unavailable; generated neutral card:',title,flush=True)

def acquire(pack):
    session=requests.Session();session.headers['User-Agent']='DocumentariAI/1.0 (local educational production)'
    manifests=read_json(ROOT/'assets/manifest.json') if (ROOT/'assets/manifest.json').exists() else []
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
    for asset in pack.get('assets',[]):save(asset['url'],asset['path'],asset['license'],asset.get('source'))
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
        path=ROOT/c['portrait'];metadata=path.with_suffix('.metadata.json')
        if path.exists() and metadata.exists():continue
        if metadata.exists():info=read_json(metadata)
        else:
            filename=c.get('commons_file')
            if not filename:
                title=c.get('wikipedia_page')
                if not title:raise ValueError(f'Commander {cid}: specify wikipedia_page, commons_file or local portrait + rights metadata.')
                for language in ('en','it'):
                    q=request(f'https://{language}.wikipedia.org/w/api.php',dict(action='query',titles=title,prop='pageimages',redirects=1,format='json')).json()
                    filename=next(iter(q['query']['pages'].values())).get('pageimage')
                    if filename:break
                if not filename:
                    if c.get('portrait_optional'):_placeholder_portrait(path,c.get('name',title),manifests);continue
                    raise ValueError('No lead portrait: '+title)
            result=request('https://commons.wikimedia.org/w/api.php',dict(action='query',titles='File:'+filename,prop='imageinfo',iiprop='url|extmetadata',iiurlwidth=960,format='json')).json()
            page=next(iter(result['query']['pages'].values()));images=page.get('imageinfo',[])
            if not images:
                if c.get('portrait_optional'):_placeholder_portrait(path,c.get('name',title),manifests);continue
                raise ValueError('Commons metadata unavailable: '+str(filename))
            info=images[0]
            write_json(metadata,info)
        lic=info['extmetadata'].get('LicenseShortName',{}).get('value','')
        if not any(x in lic.lower() for x in ('public domain','cc0','cc by')):
            if c.get('portrait_optional'):
                metadata.unlink(missing_ok=True);_placeholder_portrait(path,c.get('name',cid),manifests);continue
            raise ValueError('Unreviewed portrait licence: '+lic)
        save(info.get('thumburl',info['url']),c['portrait'],lic,info['descriptionurl'])
    write_json(ROOT/'assets/manifest.json',manifests)
