"""Local and API TTS choices with immutable one-shot voice references."""
import hashlib,io,json,re,shutil,time,wave
from pathlib import Path
from . import store

MAX_REFERENCE_BYTES=20*1024*1024

def voices_root():
    path=store.DATA/'voices';path.mkdir(parents=True,exist_ok=True);return path

def voice_folder(voice_id):
    if not re.fullmatch(r'[a-f0-9]{24}',str(voice_id)):raise KeyError(voice_id)
    return voices_root()/voice_id

def voice(voice_id):
    path=voice_folder(voice_id)/'record.json'
    if not path.is_file():raise KeyError(voice_id)
    return store.read_json(path)

def voices():
    return sorted((store.read_json(p) for p in voices_root().glob('*/record.json')),key=lambda x:x['created'],reverse=True)

def upload_reference(raw,filename='Voce.wav',reference_text=''):
    if not raw or len(raw)>MAX_REFERENCE_BYTES:raise ValueError('Usa un WAV PCM fino a 20 MB.')
    try:
        with wave.open(io.BytesIO(raw),'rb') as wav:
            channels=wav.getnchannels();sample_rate=wav.getframerate();frames=wav.getnframes();width=wav.getsampwidth();compression=wav.getcomptype()
            payload=wav.readframes(frames)
    except (wave.Error,EOFError) as exc:raise ValueError('Il campione deve essere un file WAV PCM valido.') from exc
    duration=frames/max(1,sample_rate)
    if compression!='NONE' or width!=2 or channels not in (1,2) or not 8000<=sample_rate<=96000:
        raise ValueError('Usa un WAV PCM a 16 bit, mono o stereo.')
    if len(payload)!=frames*channels*width:raise ValueError('Il campione WAV è incompleto o danneggiato.')
    if not 4<=duration<=60:raise ValueError('Il campione vocale deve durare da 4 a 60 secondi; 10–20 secondi sono ideali.')
    digest=hashlib.sha256(raw).hexdigest();voice_id=digest[:24];folder=voice_folder(voice_id);folder.mkdir(parents=True,exist_ok=True)
    target=folder/'reference.wav'
    if not target.exists():target.write_bytes(raw)
    clean=Path(filename.replace('\\','/')).name[:120] or 'Voce.wav'
    reference_text=str(reference_text or '').strip()
    if len(reference_text)>5000:raise ValueError('La trascrizione del campione può contenere al massimo 5.000 caratteri.')
    record=dict(id=voice_id,name=Path(clean).stem[:80] or 'Voce',filename=clean,duration_seconds=round(duration,2),sample_rate=sample_rate,
                channels=channels,sha256=digest,reference_text=reference_text,created=store.now())
    store.write_json(folder/'record.json',record);return record

def chatterbox_paths(pipeline_path):
    root=Path(pipeline_path).resolve();python=root/'.venv-chatterbox/Scripts/python.exe';model=root/'assets/tts/chatterbox-v3';worker=root/'tools/chatterbox/synthesize_documentary.py'
    return root,python,model,worker

def chatterbox_installed(pipeline_path):
    _,python,model,worker=chatterbox_paths(pipeline_path)
    return python.is_file() and (model/'manifest.json').is_file() and worker.is_file()

def status(cfg):
    from .tts_api import profiles
    remote=profiles();selected=cfg.get('tts_profile_id','')
    default='api:'+selected if cfg.get('tts_engine')=='api' and selected else cfg.get('tts_engine','kokoro')
    engines=[{'id':'kokoro','name':'Kokoro · veloce, voce italiana if_sara','engine':'kokoro','supports_reference':False},
             {'id':'chatterbox','name':'Chatterbox Multilingual V3 · locale, cloning one-shot','engine':'chatterbox','supports_reference':True}]
    for item in remote:
        provider_name={'openai':'OpenAI compatibile','higgs':'Higgs','elevenlabs':'ElevenLabs','google':'Google Cloud'}.get(item['provider'],item['provider'])
        engines.append({'id':'api:'+item['id'],'name':item['name']+' · '+provider_name,'engine':'api','profile_id':item['id'],
                        'provider':item['provider'],'supports_reference':item['provider']=='higgs'})
    return {'default_engine':default,'default_selection':default,'default_reference_id':cfg.get('tts_reference_id',''),
            'chatterbox_installed':chatterbox_installed(cfg['pipeline_path']),'voices':voices(),
            'profiles':remote,'engines':engines}

def ensure_available(engine,reference_id,pipeline_path,profile_id='',config=None):
    if engine=='chatterbox' and not chatterbox_installed(pipeline_path):
        raise ValueError('Chatterbox non è ancora installato. Chiudi H3, esegui di nuovo INSTALLA.bat e poi riapri l’app.')
    if engine=='api':
        from .tts_api import profile
        current=config or profile(profile_id)
        if reference_id and current.get('provider')!='higgs':raise ValueError('Il campione one-shot è disponibile soltanto per Chatterbox e Higgs TTS.')
    if reference_id and engine in ('chatterbox','api'):
        voice(reference_id)

def _copy_reference(reference_id,work):
    if not reference_id:return '',None
    record=voice(reference_id);source=voice_folder(reference_id)/'reference.wav'
    destination=Path(work)/'assets/voice-reference'/f'{reference_id}.wav';destination.parent.mkdir(parents=True,exist_ok=True)
    if not destination.exists():shutil.copy2(source,destination)
    if hashlib.sha256(destination.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Il campione vocale salvato non supera il controllo di integrità.')
    return destination.relative_to(work).as_posix(),record

def configure_pack(pack,project,work,pipeline_path):
    engine=project.get('tts_engine') or 'kokoro';reference_id=project.get('tts_reference_id') or '';profile_id=project.get('tts_profile_id') or ''
    config=project.get('tts_config') or None
    ensure_available(engine,reference_id,pipeline_path,profile_id,config)
    if engine=='kokoro':
        # Schema-v2 packs may intentionally omit voice fields because their
        # backward-compatible adapter supplies these defaults at load time.
        if pack.get('voice_engine') not in (None,'kokoro') or 'voice' in pack:
            pack.update(voice_engine='kokoro',voice='assets/voice/kokoro/kokoro-v1.0.onnx',voice_styles='assets/voice/kokoro/voices-v1.0.bin',
                        voice_speaker='if_sara',voice_credit='Kokoro 82M, voce italiana if_sara. Sintesi locale; pesi Apache-2.0.')
            pack.pop('voice_reference',None);pack.pop('voice_language',None);pack.pop('voice_api',None)
        pack.pop('external_max_voice_tempo',None)
        return pack
    reference_path,record=_copy_reference(reference_id,work);speaker='clone-'+record['sha256'][:16] if record else 'included'
    if engine=='api':
        if not config:
            from .tts_api import snapshot
            config=snapshot(profile_id)
        stable={key:config.get(key) for key in ('id','provider','base_url','model','voice','language','response_format','temperature','top_p','top_k','seed','max_new_tokens')}
        fingerprint=hashlib.sha256(json.dumps(stable,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
        provider=config['provider'];label=config.get('name') or provider.title()
        credit=f'Sintesi vocale tramite {label} ({provider}); configurazione e provenienza registrate nel progetto. Audio ricevuto dal server e normalizzato localmente.'
        pack.update(voice_engine='tts_api',voice='tts-api:'+fingerprint,voice_speaker=config.get('voice') or 'default',voice_language=config.get('language','it-IT'),
                    voice_reference=reference_path,voice_reference_text=(record or {}).get('reference_text',''),
                    voice_api=stable|{'name':label,'timeout':config.get('timeout',180)},voice_credit=credit,external_max_voice_tempo=1.15)
        for key in ('voice_styles','chatterbox_exaggeration','chatterbox_cfg_weight','chatterbox_temperature','chatterbox_repetition_penalty'):pack.pop(key,None)
        return pack
    pack.update(voice_engine='chatterbox',voice='chatterbox-multilingual-v3@5bb1f6e;e=.35;c=.5;t=.7;r=1.2',voice_speaker=speaker,voice_language='it',
                voice_reference=reference_path,chatterbox_exaggeration=.35,chatterbox_cfg_weight=.5,chatterbox_temperature=.7,
                chatterbox_repetition_penalty=1.2,
                voice_credit='Chatterbox Multilingual V3, sintesi locale. Codice e pesi MIT; watermark audio del modello.',external_max_voice_tempo=1.15)
    pack.pop('voice_api',None)
    return pack

def change_project_voice(pid,choice):
    project=store.project(pid)
    if project['status'] in ('running','queued','cancelling','completed'):raise ValueError('Interrompi prima la produzione; un video completato resta immutabile.')
    cfg=store.settings();config={}
    if choice.tts_engine=='api':
        from .tts_api import snapshot
        if not choice.tts_profile_id:raise ValueError('Seleziona un server TTS salvato.')
        config=snapshot(choice.tts_profile_id)
    ensure_available(choice.tts_engine,choice.tts_reference_id,cfg['pipeline_path'],choice.tts_profile_id,config)
    folder=store.JOBS/pid;checkpoint=folder/'checkpoints';stamp=str(time.time_ns())
    for name in ('voice','preview','render','finalize','verify'):
        marker=checkpoint/(name+'.done.json')
        if marker.exists():marker.rename(checkpoint/(name+f'.before-voice-{stamp}.json'))
    work=folder/'workspace';build=work/'build'
    if build.exists():build.rename(work/f'build-before-voice-{stamp}')
    timeline=work/'timeline.json'
    if timeline.exists():timeline.rename(work/f'timeline.before-voice-{stamp}.json')
    store.update(pid,tts_engine=choice.tts_engine,tts_reference_id=choice.tts_reference_id,tts_profile_id=choice.tts_profile_id,tts_config=config,status='cancelled',stage='Voce da rigenerare',error='La nuova voce sarà applicata alla ripresa.')
    name=config.get('name') if config else ('Chatterbox Multilingual V3' if choice.tts_engine=='chatterbox' else 'Kokoro if_sara')
    store.event(pid,'Voce selezionata: '+name+'.')
    return store.project(pid)
