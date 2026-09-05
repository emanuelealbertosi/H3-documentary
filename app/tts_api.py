"""Saved external TTS profiles and provider adapters.

Secrets stay in the Studio data directory protected with Windows DPAPI. Project
workspaces receive only an immutable public snapshot of the selected profile.
"""
from __future__ import annotations
import base64,hashlib,json,os,re,secrets,subprocess,tempfile,time,wave
from contextlib import contextmanager,nullcontext
from pathlib import Path
from urllib.parse import quote
import requests
from . import store
from .models import TTSProfile

MAX_AUDIO_BYTES=25*1024*1024
PROFILE_FILE='tts-api.json'
PUBLIC_FIELDS=('id','name','provider','base_url','model','voice','language','response_format','timeout',
               'temperature','top_p','top_k','seed','max_new_tokens','style_protocol')

class TTSHTTPError(ValueError):
    def __init__(self,status_code,message):
        super().__init__(message);self.status_code=status_code

def _path():return store.DATA/PROFILE_FILE

def _raw():
    path=_path()
    if not path.exists():return {'profiles':{}}
    value=store.read_json(path)
    return value if isinstance(value,dict) and isinstance(value.get('profiles'),dict) else {'profiles':{}}

def _public(row):
    defaults={'timeout':180,'temperature':1.0,'top_p':.95,'top_k':50,'seed':-1,'max_new_tokens':2048,'style_protocol':'none'}
    value={key:row.get(key,defaults.get(key,'')) for key in PUBLIC_FIELDS}
    for key,default in defaults.items():
        if value.get(key) in ('',None):value[key]=default
    value['timeout']=int(value['timeout'] or 180)
    value['has_api_key']=bool(row.get('encrypted_key') or os.environ.get('DOCUMENTARIAI_TTS_API_KEY'))
    value['updated']=row.get('updated','')
    return value

def profiles():
    rows=[_public(row) for row in _raw()['profiles'].values() if isinstance(row,dict)]
    return sorted(rows,key=lambda row:row.get('updated',''),reverse=True)

def profile(profile_id):
    if not isinstance(profile_id,str) or not re.fullmatch(r'[a-f0-9]{24}',profile_id):raise KeyError(profile_id)
    row=_raw()['profiles'].get(profile_id)
    if not isinstance(row,dict):raise KeyError(profile_id)
    return _public(row)

def save(value:TTSProfile):
    with store.LOCK:
        data=value.model_dump();profile_id=data.pop('id') or secrets.token_hex(12)
        raw=_raw();previous=raw['profiles'].get(profile_id,{})
        supplied=data.pop('api_key',None);clear=data.pop('clear_api_key',False)
        encrypted='' if clear else (store.protect(supplied) if supplied else previous.get('encrypted_key',''))
        row={**data,'id':profile_id,'encrypted_key':encrypted,'updated':store.now()}
        raw['profiles'][profile_id]=row;store.write_json(_path(),raw)
    return _public(row)

def remove(profile_id):
    with store.LOCK:
        raw=_raw()
        if profile_id not in raw['profiles']:raise KeyError(profile_id)
        del raw['profiles'][profile_id];store.write_json(_path(),raw)

def secret_for(profile_id):
    row=_raw()['profiles'].get(profile_id)
    if not isinstance(row,dict):raise KeyError(profile_id)
    environment=os.environ.get('DOCUMENTARIAI_TTS_API_KEY','')
    return environment or (store.protect(row.get('encrypted_key',''),True) if row.get('encrypted_key') else '')

def snapshot(profile_id):
    return {key:value for key,value in profile(profile_id).items() if key not in ('has_api_key','updated')}

def connection(value:TTSProfile):
    data=value.model_dump();profile_id=data.get('id','')
    if not data.get('api_key') and profile_id:
        try:data['api_key']=secret_for(profile_id)
        except KeyError:pass
    return data

def _endpoint(base,suffix):
    base=base.rstrip('/')
    return base if base.endswith(suffix) else base+suffix

def _limited(content):
    if not content:raise ValueError('Il server TTS ha restituito un audio vuoto.')
    if len(content)>MAX_AUDIO_BYTES:raise ValueError('La risposta audio del server TTS supera 25 MB.')
    return content

def _error(response):
    try:detail=response.json().get('detail') or response.json().get('error')
    except Exception:detail=response.text[:300]
    if isinstance(detail,dict):detail=detail.get('message') or json.dumps(detail,ensure_ascii=False)
    raise TTSHTTPError(response.status_code,f'Server TTS: HTTP {response.status_code}. {str(detail or "Risposta non valida")[:500]}')

def _post(url,*,headers=None,json_body=None,data=None,files=None,timeout=180):
    last=None
    for attempt in range(3):
        try:
            for item in (files or {}).values():
                if isinstance(item,tuple) and len(item)>1 and hasattr(item[1],'seek'):item[1].seek(0)
            response=requests.post(url,headers=headers,json=json_body,data=data,files=files,timeout=(10,timeout))
        except requests.RequestException as exc:
            last=exc
            if attempt<2:time.sleep(.7*(attempt+1));continue
            raise ValueError('Server TTS non raggiungibile: '+str(exc)) from exc
        if response.status_code in (408,429,500,502,503,504) and attempt<2:
            time.sleep(.7*(attempt+1));continue
        if not response.ok:_error(response)
        return response
    raise ValueError('Server TTS non raggiungibile: '+str(last))

def _get(url,*,headers=None,timeout=30):
    try:response=requests.get(url,headers=headers,timeout=(10,timeout))
    except requests.RequestException as exc:raise ValueError('Server TTS non raggiungibile: '+str(exc)) from exc
    if not response.ok:_error(response)
    return response

def _headers(api_key='',accept='application/json'):
    value={'Accept':accept}
    if api_key:value['Authorization']='Bearer '+api_key
    return value

def _object(response,label):
    try:value=response.json()
    except Exception as exc:raise ValueError(f'Il server Higgs ha restituito una risposta {label} non valida.') from exc
    if not isinstance(value,dict):raise ValueError(f'Il server Higgs ha restituito una risposta {label} non valida.')
    return value

def higgs_status(config,api_key=''):
    if config.get('provider')!='higgs':raise ValueError('Il controllo del modello è disponibile soltanto per Higgs TTS.')
    response=_get(_endpoint(config['base_url'],'/status'),headers=_headers(api_key),timeout=min(int(config.get('timeout',900)),60))
    return _object(response,'di stato')

def higgs_model(config,action,api_key=''):
    if action not in ('load','unload'):raise ValueError('Operazione Higgs non valida.')
    if config.get('provider')!='higgs':raise ValueError('Il controllo del modello è disponibile soltanto per Higgs TTS.')
    response=_post(_endpoint(config['base_url'],'/model/'+action),headers=_headers(api_key),timeout=int(config.get('timeout',900)))
    value=_object(response,'del modello');expected='ready' if action=='load' else 'unloaded'
    if value.get('ok') is not True or value.get('model_state')!=expected:
        raise ValueError(f'Il server Higgs non ha confermato lo stato {expected}.')
    status=higgs_status(config,api_key)
    if status.get('model_state')!=expected:
        raise ValueError(f'Il comando Higgs è terminato, ma lo stato successivo è {status.get("model_state","sconosciuto")} invece di {expected}.')
    return {**value,**status,'confirmed_by_status':True}

def higgs_upload_voice(config,reference_path,reference_text,voice_id,overwrite=False,api_key=''):
    if config.get('provider')!='higgs':raise ValueError('Le voci persistenti sono disponibili soltanto per Higgs TTS.')
    fields={'voice_id':voice_id,'reference_text':reference_text or '','overwrite':str(bool(overwrite)).lower()}
    with open(reference_path,'rb') as source:
        response=_post(_endpoint(config['base_url'],'/voices/upload'),headers=_headers(api_key),data=fields,
                       files={'reference_audio':(Path(reference_path).name,source,'audio/wav')},timeout=int(config.get('timeout',900)))
    value=_object(response,'di registrazione della voce')
    if not value.get('voice'):raise ValueError('Il server Higgs non ha restituito il nome della voce registrata.')
    return value

@contextmanager
def higgs_activity(config,api_key='',log=None):
    """Keep the API process alive while H3 owns one complete synthesis activity."""
    if config.get('provider')!='higgs':
        yield
        return
    result=higgs_model(config,'load',api_key)
    if log:log('Higgs remoto: modello caricato e pronto.' if not result.get('already_loaded') else 'Higgs remoto: modello già pronto.')
    failed=False
    try:yield
    except BaseException:
        failed=True
        raise
    finally:
        try:
            result=higgs_model(config,'unload',api_key)
            if log:log('Higgs remoto: il server conferma lo stato unloaded; il processo HTTP resta raggiungibile.' if not result.get('already_unloaded') else 'Higgs remoto: il server conferma che il modello era già nello stato unloaded.')
        except Exception as exc:
            if log:log('Higgs remoto: sintesi conclusa, ma lo scaricamento del modello non è riuscito: '+str(exc))
            if not failed:raise

def _google_token(secret):
    if secret and not secret.lstrip().startswith('{'):return secret
    try:
        import google.auth
        from google.auth.transport.requests import Request
        if secret:
            from google.oauth2 import service_account
            credentials=service_account.Credentials.from_service_account_info(json.loads(secret),scopes=['https://www.googleapis.com/auth/cloud-platform'])
        else:
            credentials,_=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        credentials.refresh(Request());return credentials.token
    except Exception as exc:
        raise ValueError('Google TTS richiede un token OAuth, un JSON service account oppure Application Default Credentials configurate.') from exc

def _higgs_fields(config,text,reference_text=''):
    def option(name,default):
        value=config.get(name,default);return default if value in ('',None) else value
    fields={'input':text,'response_format':config.get('response_format') or 'wav',
            'temperature':str(option('temperature',1.0)),'top_p':str(option('top_p',.95)),
            'top_k':str(option('top_k',50)),'seed':str(option('seed',-1)),
            'max_new_tokens':str(option('max_new_tokens',2048))}
    if reference_text:fields['reference_text']=reference_text
    return fields

def synthesize_bytes(config,text,reference_path=None,api_key='',reference_text='',delivery=None,log=None,delivery_report=None):
    """Use supported tags, with one unstyled retry only for format rejection."""
    from .voice_delivery import synthesis_text,delivery_dict
    if not text.strip():raise ValueError('Il testo da sintetizzare è vuoto.')
    selected=delivery_dict(delivery);outbound=synthesis_text(config,text,selected);tagged=outbound!=text
    report={'requested_style':selected['style'],'effective_style':selected['style'] if tagged else 'original',
            'style_verified':False,'fallback':False}
    try:
        result=_synthesize_bytes(config,outbound,reference_path,api_key,reference_text)
    except TTSHTTPError as exc:
        if not tagged or exc.status_code not in (400,422):raise
        # Keep authentication/network/server failures distinct; a second format
        # rejection also propagates. Never change the saved server configuration.
        if log:log('La richiesta con tag espressivi è stata rifiutata: riprovo questa frase con la voce originale, senza stile.')
        result=_synthesize_bytes(config,text,reference_path,api_key,reference_text)
        report.update(effective_style='original',fallback=True)
    if delivery_report is not None:delivery_report.update(report)
    return result

def _synthesize_bytes(config,text,reference_path=None,api_key='',reference_text=''):
    """Return provider audio bytes and their expected container."""
    provider=config['provider'];base=config['base_url'];timeout=int(config.get('timeout',180));model=config.get('model','');voice=config.get('voice','')
    if not text.strip():raise ValueError('Il testo da sintetizzare è vuoto.')
    if provider in ('openai','higgs'):
        headers=_headers(api_key,'audio/*')
        if provider=='higgs' and reference_path:
            url=_endpoint(base,'/audio/voice-clone');fields=_higgs_fields(config,text,reference_text)
            with open(reference_path,'rb') as source:
                response=_post(url,headers=headers,data=fields,files={'reference_audio':(Path(reference_path).name,source,'audio/wav')},timeout=timeout)
        else:
            url=_endpoint(base,'/audio/speech')
            if provider=='higgs':
                body={key:(float(value) if key in ('temperature','top_p') else int(value) if key in ('top_k','seed','max_new_tokens') else value)
                      for key,value in _higgs_fields(config,text).items()}
            else:body={'model':model or 'tts-1','input':text,'response_format':config.get('response_format','mp3')}
            if voice:body['voice']=voice
            response=_post(url,headers=headers,json_body=body,timeout=timeout)
        return _limited(response.content),config.get('response_format','mp3')
    if provider=='elevenlabs':
        if not voice:raise ValueError('ElevenLabs richiede il voice ID nel profilo TTS.')
        headers={'Accept':'audio/mpeg','Content-Type':'application/json'}
        if api_key:headers['xi-api-key']=api_key
        url=_endpoint(base,'/text-to-speech/')+quote(voice,safe='')+'?output_format=mp3_44100_128'
        body={'text':text,'model_id':model or 'eleven_multilingual_v2'}
        response=_post(url,headers=headers,json_body=body,timeout=timeout)
        return _limited(response.content),'mp3'
    if provider=='google':
        token=_google_token(api_key);headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
        voice_body={'languageCode':config.get('language') or 'it-IT'}
        if voice:voice_body['name']=voice
        body={'input':{'text':text},'voice':voice_body,'audioConfig':{'audioEncoding':'LINEAR16','sampleRateHertz':24000}}
        response=_post(_endpoint(base,'/text:synthesize'),headers=headers,json_body=body,timeout=timeout)
        try:content=base64.b64decode(response.json()['audioContent'],validate=True)
        except Exception as exc:raise ValueError('Google TTS non ha restituito audioContent valido.') from exc
        return _limited(content),'wav'
    raise ValueError('Provider TTS non supportato.')

def _valid_wav(path):
    try:
        with wave.open(str(path),'rb') as audio:
            channels=audio.getnchannels();sample_width=audio.getsampwidth();frames=audio.getnframes()
            # Some streaming TTS servers terminate a WAV correctly but leave the
            # RIFF/data length at 0x7fffffff.  wave/scipy can read the payload, yet
            # every later read emits a premature-EOF warning.  Treat that header
            # as non-canonical so normalize_audio rewrites it through FFmpeg.
            declared_payload=frames*channels*sample_width
            complete=declared_payload<=max(0,Path(path).stat().st_size-44)+4096
            return channels==1 and sample_width==2 and audio.getframerate()==24000 and frames>6000 and complete
    except (wave.Error,EOFError,OSError):return False

def normalize_audio(content,container,target):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='h3-tts-') as temporary:
        extension=container if container in ('wav','mp3','flac','ogg') else 'bin'
        source=Path(temporary)/('response.'+extension);source.write_bytes(content)
        if container=='wav' and _valid_wav(source):
            source.replace(target);return target
        import imageio_ffmpeg
        command=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i',str(source),'-ar','24000','-ac','1','-c:a','pcm_s16le',str(target)]
        try:subprocess.run(command,check=True,capture_output=True,timeout=180)
        except (subprocess.SubprocessError,OSError) as exc:raise ValueError('Il server TTS non ha restituito un formato audio decodificabile.') from exc
    if not _valid_wav(target):
        target.unlink(missing_ok=True);raise ValueError('Il server TTS ha restituito un WAV vuoto o non valido.')
    return target

def test_voice(value:TTSProfile,text='Questa è una prova della voce italiana per il documentario.',reference_path=None,reference_text='',delivery=None,delivery_report=None):
    from .voice_delivery import delivery_dict,is_default,preview_lines,combine_preview
    data=connection(value);api_key=data.get('api_key') or ''
    selected=delivery_dict(delivery);lines=preview_lines(text)
    # Preserve the old request and exact normalized bytes for default controls.
    if is_default(selected):lines=[text]
    with tempfile.TemporaryDirectory(prefix='h3-tts-test-') as temporary:
        paths=[]
        with higgs_activity(data,api_key):
            for index,line in enumerate(lines):
                kwargs={} if is_default(selected) else {'delivery':selected}
                report={}
                if data.get('provider')=='higgs' and data.get('style_protocol')=='higgs_tags' and selected['style']!='original':
                    kwargs['delivery_report']=report
                content,container=synthesize_bytes(data,line,reference_path,api_key,reference_text,**kwargs)
                target=Path(temporary)/f'{index}.wav';normalize_audio(content,container,target);paths.append(target)
                if delivery_report is not None and report:delivery_report.append(report)
        return combine_preview(paths,selected)

def _fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def synthesis_key(pack,scene_id,index,spoken,work):
    values=[spoken,pack['voice'],pack.get('voice_engine','piper'),pack.get('voice_speaker'),1.0,.45,.65]
    if pack.get('voice_reference_text'):values.append(pack['voice_reference_text'])
    marker=f'{scene_id}:{index}'
    if marker in pack.get('voice_custom_chunks',{}):values.extend(['custom-chunks-v2',pack['voice_custom_chunks'][marker]])
    elif marker in pack.get('voice_clause_chunks',[]):values.append('clause-chunks-v1')
    elif marker in pack.get('voice_sentence_chunks',[]):values.append('sentence-chunks-v1')
    overrides=pack.get('voice_phoneme_overrides',{}).get(marker)
    if overrides:values.append(overrides)
    fragments=pack.get('voice_chunk_assets',{}).get(marker,{})
    if fragments:
        values.append({key:{**asset,'sha256':hashlib.sha256((Path(work)/asset['path']).read_bytes()).hexdigest()} for key,asset in fragments.items()})
    return _fingerprint(values)[:18]

def synthesize_pack(pack,project,work,cancel,log):
    config=project.get('tts_config') or pack.get('voice_api')
    if not isinstance(config,dict):raise ValueError('Il progetto non contiene la configurazione del server TTS.')
    profile_id=project.get('tts_profile_id') or config.get('id')
    api_key=secret_for(profile_id)
    reference=Path(work)/pack['voice_reference'] if pack.get('voice_reference') else None
    lines=[(scene,i,line) for scene in pack['scenes'] for i,line in enumerate(scene['lines'])]
    out=Path(work)/'build'/pack['slug']/'voice';out.mkdir(parents=True,exist_ok=True)
    pending=[]
    cache_items={}
    previous_items={};manifest=out/'external-voice-cache.json'
    try:
        previous=json.loads(manifest.read_text(encoding='utf-8')) if manifest.is_file() else {}
        if isinstance(previous,dict) and isinstance(previous.get('items'),dict):previous_items=previous['items']
    except (OSError,ValueError):pass
    for scene,index,line in lines:
        spoken=line
        for original,replacement in sorted(pack.get('pronunciation',{}).items(),key=lambda item:-len(item[0])):spoken=spoken.replace(original,replacement)
        target=out/(synthesis_key(pack,scene['id'],index,spoken,work)+'.wav')
        pending.append((scene,index,spoken,target))
        cache_items[f'{scene["id"]}:{index}']={'file':target.name,'spoken_sha256':hashlib.sha256(spoken.encode('utf-8')).hexdigest()}
        previous=previous_items.get(f'{scene["id"]}:{index}',{})
        if isinstance(previous,dict) and previous.get('file')==target.name and isinstance(previous.get('delivery'),dict):
            cache_items[f'{scene["id"]}:{index}']['delivery']=previous['delivery']
    # Repair reusable files produced by streaming servers before deciding that
    # the cache is complete.  This is local and does not call the TTS server.
    for _,_,_,target in pending:
        if target.exists() and not _valid_wav(target):
            temporary=target.with_suffix('.normalized.wav')
            normalize_audio(target.read_bytes(),'wav',temporary);temporary.replace(target)
    manager=higgs_activity(config,api_key,log) if any(not target.exists() for _,_,_,target in pending) else nullcontext()
    with manager:
        for done,(scene,index,spoken,target) in enumerate(pending,1):
            cancel()
            if not target.exists():
                kwargs={'delivery':pack['voice_delivery']} if pack.get('voice_delivery') else {}
                report={}
                if config.get('provider')=='higgs' and config.get('style_protocol')=='higgs_tags' and pack.get('voice_delivery',{}).get('style','original')!='original':
                    kwargs.update(delivery_report=report,log=log)
                content,container=synthesize_bytes(config,spoken,reference,api_key,pack.get('voice_reference_text',''),**kwargs)
                temporary=target.with_suffix('.part.wav')
                normalize_audio(content,container,temporary)
                if report:
                    cache_items[f'{scene["id"]}:{index}']['delivery']=report
                    # Persist provenance before publishing the cached WAV, so a
                    # later interrupted cue does not lose the fallback record.
                    store.write_json(manifest,{'version':1,'backend':'tts_api','items':cache_items})
                temporary.replace(target)
            log(f'TTS API: segmento {done}/{len(lines)} pronto.')
    (out/'external-voice-cache.json').write_text(json.dumps({'version':1,'backend':'tts_api','items':cache_items},ensure_ascii=False,indent=2),encoding='utf-8')
    return len(lines)
