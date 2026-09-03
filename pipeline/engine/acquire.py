"""Generic licensed-asset acquisition for new battle packs. Rendering stays offline."""
from pathlib import Path
import json,hashlib,time
import requests
from .common import ROOT,read_json,write_json

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
    if not (ROOT/pack['voice']).exists():
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
                q=request('https://en.wikipedia.org/w/api.php',dict(action='query',titles=title,prop='pageimages',redirects=1,format='json')).json()
                filename=next(iter(q['query']['pages'].values())).get('pageimage')
                if not filename:raise ValueError('No lead portrait: '+title)
            result=request('https://commons.wikimedia.org/w/api.php',dict(action='query',titles='File:'+filename,prop='imageinfo',iiprop='url|extmetadata',iiurlwidth=960,format='json')).json()
            info=next(iter(result['query']['pages'].values()))['imageinfo'][0]
            write_json(metadata,info)
        lic=info['extmetadata'].get('LicenseShortName',{}).get('value','')
        if not any(x in lic.lower() for x in ('public domain','cc0','cc by')):raise ValueError('Unreviewed portrait licence: '+lic)
        save(info.get('thumburl',info['url']),c['portrait'],lic,info['descriptionurl'])
