from fastapi import APIRouter,HTTPException
from fastapi.responses import Response
from .models import TTSProfile
from . import tts_api

router=APIRouter(prefix='/api/tts/profiles')

@router.get('')
def list_profiles():return tts_api.profiles()

@router.post('',status_code=201)
def save_profile(value:TTSProfile):return tts_api.save(value)

@router.delete('/{profile_id}',status_code=204)
def delete_profile(profile_id:str):
    from . import store
    cfg=store.settings()
    if cfg.get('tts_engine')=='api' and cfg.get('tts_profile_id')==profile_id:
        raise HTTPException(409,'Scegli prima un’altra voce predefinita e salva la configurazione.')
    if any(p.get('tts_profile_id')==profile_id and p.get('status')!='completed' for p in store.projects()):
        raise HTTPException(409,'Questo server TTS è ancora usato da un progetto non completato.')
    try:tts_api.remove(profile_id)
    except KeyError:raise HTTPException(404,'Server TTS non trovato.')
    return Response(status_code=204)

@router.post('/test')
def test_profile(value:TTSProfile):
    audio=tts_api.test_voice(value)
    return Response(audio,media_type='audio/wav',headers={'Content-Disposition':'inline; filename="prova-tts.wav"'})
