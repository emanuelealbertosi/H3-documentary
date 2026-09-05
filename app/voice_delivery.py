"""Voice direction, capability declarations and isolated, bounded audio previews.

Style affects only supported synthesis adapters. Speed and cue gaps are shared
postprocessing controls; the default triple deliberately preserves legacy packs.
"""
from __future__ import annotations
import io,json,os,re,subprocess,tempfile,threading,wave
from contextlib import contextmanager
from pathlib import Path
from .models import VoiceDelivery

STYLES=('original','documentary','calm','engaging','solemn')
DEFAULT_DELIVERY=VoiceDelivery().model_dump()
_PREVIEW_LOCK=threading.Lock()

# Conservative presets over the existing Chatterbox controls, not free-form
# instructions. The original tuple is the application's pre-delivery default.
CHATTERBOX_STYLES={
    'original':(.35,.5,.7,1.2),
    'documentary':(.45,.5,.65,1.2),
    'calm':(.2,.55,.6,1.2),
    'engaging':(.65,.45,.75,1.2),
    'solemn':(.5,.55,.65,1.2),
}
# Official Higgs TTS 3 tokens: https://docs.boson.ai/models/higgs-tts/tags
# Enabled only by an explicit compatible-server protocol selection. Speed and
# pauses remain local so they are never applied twice through provider tags.
HIGGS_STYLE_TAGS={
    'original':'',
    'documentary':'<|emotion:contemplation|>',
    'calm':'<|emotion:contentment|><|prosody:expressive_low|>',
    'engaging':'<|emotion:enthusiasm|><|prosody:expressive_high|>',
    'solemn':'<|emotion:determination|><|prosody:expressive_low|>',
}

def delivery_dict(value=None):
    return VoiceDelivery.model_validate(value or {}).model_dump()

def is_default(value=None):
    return delivery_dict(value)==DEFAULT_DELIVERY

def capabilities(engine,config=None):
    config=config or {}
    control='none';styles=['original']
    note='Questo motore mantiene la propria espressività. Velocità e pause sono regolabili nell’app.'
    if engine=='chatterbox':
        control='parameters';styles=list(STYLES)
        note='Gli stili regolano i parametri espressivi di Chatterbox; il risultato dipende anche dal campione vocale.'
    elif engine=='api' and config.get('provider')=='higgs':
        if config.get('style_protocol')=='higgs_tags':
            control='tags';styles=list(STYLES)
            note='Stili inviati come tag ufficiali Higgs TTS 3. Prova la voce per verificare il supporto del tuo server.'
        else:
            note='Per gli stili Higgs abilita il protocollo dei tag su un server compatibile. Velocità e pause funzionano già nell’app.'
    return {'styles':styles,'style_control':control,'speed':True,'pause_seconds':True,'note':note}

def synthesis_text(config,text,delivery=None):
    """Decorate only the outbound request; scripts, cues and subtitles stay clean."""
    if config.get('provider')!='higgs' or config.get('style_protocol')!='higgs_tags':return text
    return HIGGS_STYLE_TAGS[delivery_dict(delivery)['style']]+text

def preview_active():
    return _PREVIEW_LOCK.locked()

@contextmanager
def preview_activity():
    """Serialize previews/lifecycle operations against the production queue."""
    from fastapi import HTTPException
    from . import runner
    with runner.LOCK:
        if runner.active():raise HTTPException(409,'Attendi o interrompi la produzione prima di provare la voce o gestire il modello TTS.')
        if not _PREVIEW_LOCK.acquire(blocking=False):
            raise HTTPException(409,'Una prova vocale o un’operazione TTS è già in corso. Attendi che termini.')
    try:yield
    finally:_PREVIEW_LOCK.release()

def preview_lines(text):
    text=str(text).strip()
    if not text:raise ValueError('Inserisci un testo per provare la voce.')
    if len(text)>800:raise ValueError('La prova vocale accetta al massimo 800 caratteri.')
    # Keep all user text even if there are more than eight sentence boundaries.
    return re.split(r'(?<=[.!?])\s+|\n+',text,maxsplit=7)

def combine_preview(paths,delivery=None):
    """Apply the same atempo and cue-gap controls to normalized API samples."""
    selected=delivery_dict(delivery);speed=selected['speed']
    paths=[Path(path) for path in paths]
    if len(paths)==1 and speed==1:return paths[0].read_bytes()
    frames=[]
    for index,path in enumerate(paths):
        adjusted=path
        if speed!=1:
            import imageio_ffmpeg
            adjusted=path.with_name(path.stem+'-tempo.wav')
            command=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i',str(path),
                     '-af',f'atempo={speed:.8g}','-ar','24000','-ac','1','-c:a','pcm_s16le',str(adjusted)]
            try:subprocess.run(command,check=True,capture_output=True,timeout=120)
            except (OSError,subprocess.SubprocessError) as exc:raise ValueError('Impossibile applicare la velocità alla prova vocale.') from exc
        with wave.open(str(adjusted),'rb') as source:
            if (source.getnchannels(),source.getsampwidth(),source.getframerate())!=(1,2,24000):
                raise ValueError('Formato della prova vocale non normalizzato.')
            frames.append(source.readframes(source.getnframes()))
        if index<len(paths)-1:frames.append(b'\0\0'*round(selected['pause_seconds']*24000))
    output=io.BytesIO()
    with wave.open(output,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000);audio.writeframes(b''.join(frames))
    return output.getvalue()

def local_preview(value,pipeline_path):
    """Run local TTS in the bundled runtime, never inside the app interpreter."""
    from . import tts
    root=Path(pipeline_path).resolve();python=root/'.venv'/'Scripts'/'python.exe'
    worker=root/'tools'/'preview_voice.py'
    if not python.is_file() or not worker.is_file():raise ValueError('La pipeline locale per la prova vocale non è installata. Completa l’installazione dell’app.')
    preview_lines(value.text)
    with tempfile.TemporaryDirectory(prefix='h3-voice-preview-') as temporary:
        work=Path(temporary);pack={'slug':'voice-preview'}
        tts.configure_pack(pack,value.model_dump(),work,root)
        if pack.get('voice_reference'):pack['voice_reference']=str((work/pack['voice_reference']).resolve())
        request=work/'request.json';output=work/'preview.wav'
        request.write_text(json.dumps({'pack':pack,'text':value.text,'delivery':delivery_dict(value.tts_delivery)},ensure_ascii=False),encoding='utf-8')
        try:
            result=subprocess.run([str(python),str(worker),'--request',str(request),'--output',str(output)],
                cwd=str(root),capture_output=True,timeout=900,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0)
        except subprocess.TimeoutExpired as exc:raise ValueError('La prova vocale ha superato 15 minuti. Prova un testo più breve o un motore più rapido.') from exc
        except OSError as exc:raise ValueError('Impossibile avviare il motore per la prova vocale.') from exc
        if result.returncode or not output.is_file():
            # Worker diagnostics never contain API credentials, but keep server
            # responses and local paths out of this user-facing error anyway.
            raise ValueError('Il motore locale non ha completato la prova vocale. Controlla che modelli e dipendenze siano installati.')
        from .tts_api import _valid_wav
        if not _valid_wav(output):raise ValueError('Il motore locale ha restituito una prova audio non valida.')
        return output.read_bytes()
