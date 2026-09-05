from fastapi import APIRouter,HTTPException
from fastapi.responses import Response
from .models import TTSProfile,TTSTestRequest,HiggsVoiceUpload,TTSPreviewRequest
from . import tts_api
from .voice_delivery import preview_activity

router=APIRouter(prefix='/api/tts/profiles')
preview_router=APIRouter(prefix='/api/tts')

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
def test_profile(value:TTSTestRequest):
    reports=[]
    with preview_activity():
        reference_path=None;reference_text=''
        if value.reference_id:
            from . import tts
            record=tts.voice(value.reference_id)
            if value.provider!='higgs':raise ValueError('Il campione one-shot nella prova è disponibile soltanto con Higgs TTS.')
            reference_path=tts.voice_folder(value.reference_id)/'reference.wav';reference_text=record.get('reference_text','')
        audio=tts_api.test_voice(value,text=value.text,reference_path=reference_path,reference_text=reference_text,delivery=value.tts_delivery,delivery_report=reports)
    return Response(audio,media_type='audio/wav',headers={'Content-Disposition':'inline; filename="prova-tts.wav"','X-Voice-Style-Fallback':str(any(row.get('fallback') for row in reports)).lower()})

@preview_router.post('/preview')
def preview_voice(value:TTSPreviewRequest):
    from . import store,tts
    from .voice_delivery import local_preview
    reports=[]
    with preview_activity():
        cfg=store.settings()
        if value.tts_engine=='api':
            config=tts_api.snapshot(value.tts_profile_id)
            tts.ensure_available('api',value.tts_reference_id,cfg['pipeline_path'],value.tts_profile_id,config)
            reference=None;reference_text=''
            if value.tts_reference_id:
                record=tts.voice(value.tts_reference_id)
                reference=tts.voice_folder(value.tts_reference_id)/'reference.wav';reference_text=record.get('reference_text','')
            audio=tts_api.test_voice(TTSProfile(**config),text=value.text,reference_path=reference,reference_text=reference_text,delivery=value.tts_delivery,delivery_report=reports)
        else:audio=local_preview(value,cfg['pipeline_path'])
    return Response(audio,media_type='audio/wav',headers={'Content-Disposition':'inline; filename="prova-voce.wav"','X-Voice-Style-Fallback':str(any(row.get('fallback') for row in reports)).lower()})

def _higgs(profile_id):
    config=tts_api.profile(profile_id)
    if config.get('provider')!='higgs':raise ValueError('Questa operazione richiede un profilo Higgs TTS.')
    return config,tts_api.secret_for(profile_id)

@router.get('/{profile_id}/status')
def remote_status(profile_id:str):
    config,key=_higgs(profile_id);return tts_api.higgs_status(config,key)

@router.post('/{profile_id}/model/{action}')
def remote_model(profile_id:str,action:str):
    with preview_activity():
        config,key=_higgs(profile_id);return tts_api.higgs_model(config,action,key)

@router.post('/{profile_id}/voices/upload')
def remote_voice(profile_id:str,value:HiggsVoiceUpload):
    from . import tts
    with preview_activity():
        config,key=_higgs(profile_id);record=tts.voice(value.reference_id)
        path=tts.voice_folder(value.reference_id)/'reference.wav'
        return tts_api.higgs_upload_voice(config,path,record.get('reference_text',''),value.voice_id,value.overwrite,key)
