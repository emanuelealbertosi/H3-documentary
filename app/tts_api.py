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
               'temperature','top_p','top_k','seed','max_new_tokens')

def _path():return store.DATA/PROFILE_FILE

def _raw():
    path=_path()
    if not path.exists():return {'profiles':{}}
    value=store.read_json(path)
    return value if isinstance(value,dict) and isinstance(value.get('profiles'),dict) else {'profiles':{}}

def _public(row):
    defaults={'timeout':180,'temperature':1.0,'top_p':.95,'top_k':50,'seed':-1,'max_new_tokens':2048}
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
    raise ValueError(f'Server TTS: HTTP {response.status_code}. {str(detail or "Risposta non valida")[:500]}')

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
    return value

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
            if log:log('Higgs remoto: modello scaricato; il server resta raggiungibile.' if not result.get('already_unloaded') else 'Higgs remoto: modello già scaricato.')
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

def synthesize_bytes(config,text,reference_path=None,api_key='',reference_text=''):
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
            return audio.getnchannels()==1 and audio.getsampwidth()==2 and audio.getframerate()==24000 and audio.getnframes()>6000
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

def test_voice(value:TTSProfile,text='Questa è una prova della voce italiana per il documentario.',reference_path=None,reference_text=''):
    data=connection(value);api_key=data.get('api_key') or ''
    handle,name=tempfile.mkstemp(prefix='h3-tts-test-',suffix='.wav');os.close(handle);temporary=Path(name)
    try:
        with higgs_activity(data,api_key):content,container=synthesize_bytes(data,text,reference_path,api_key,reference_text)
        return normalize_audio(content,container,temporary).read_bytes()
    finally:temporary.unlink(missing_ok=True)

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
    for scene,index,line in lines:
        spoken=line
        for original,replacement in sorted(pack.get('pronunciation',{}).items(),key=lambda item:-len(item[0])):spoken=spoken.replace(original,replacement)
        pending.append((scene,index,spoken,out/(synthesis_key(pack,scene['id'],index,spoken,work)+'.wav')))
    manager=higgs_activity(config,api_key,log) if any(not target.exists() for _,_,_,target in pending) else nullcontext()
    with manager:
        for done,(scene,index,spoken,target) in enumerate(pending,1):
            cancel()
            if not target.exists():
                content,container=synthesize_bytes(config,spoken,reference,api_key,pack.get('voice_reference_text',''))
                temporary=target.with_suffix('.part.wav')
                normalize_audio(content,container,temporary);temporary.replace(target)
            log(f'TTS API: segmento {done}/{len(lines)} pronto.')
    return len(lines)
