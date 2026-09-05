"""Offline delivery contracts: no model, network or active project access."""
import copy,hashlib,io,json,math,struct,wave
from pathlib import Path
import pytest
from contextlib import nullcontext
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app import store,tts,tts_api,tts_routes,voice_delivery as vd
from app.models import Settings,ProjectRequest,VoiceChoice,VoiceDelivery,TTSProfile,TTSTestRequest,TTSPreviewRequest

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    (tmp_path/'jobs').mkdir()
    monkeypatch.setattr(store,'DATA',tmp_path);monkeypatch.setattr(store,'JOBS',tmp_path/'jobs')
    monkeypatch.delenv('DOCUMENTARIAI_TTS_API_KEY',raising=False)
    # Isolation is in place before migrations; never open the running app's DB.
    store.init()
    from app import runner
    monkeypatch.setattr(runner,'active',lambda *args:False)
    monkeypatch.setattr(tts_api.requests,'post',lambda *a,**k:pytest.fail('Unexpected TTS network call'))
    monkeypatch.setattr(tts_api.requests,'get',lambda *a,**k:pytest.fail('Unexpected TTS network call'))

def wav_bytes(seconds=.5):
    samples=b''.join(struct.pack('<h',round(math.sin(i*2*math.pi*220/24000)*2000)) for i in range(round(seconds*24000)))
    out=io.BytesIO()
    with wave.open(out,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000);audio.writeframes(samples)
    return out.getvalue()

def duration(raw):
    with wave.open(io.BytesIO(raw),'rb') as audio:return audio.getnframes()/audio.getframerate()

def client():
    app=FastAPI();app.include_router(tts_routes.router);app.include_router(tts_routes.preview_router)
    return TestClient(app)

def test_defaults_and_bounds():
    expected={'style':'original','speed':1.0,'pause_seconds':.18}
    assert Settings().tts_delivery.model_dump()==expected
    assert ProjectRequest(topic='Storia di Roma').tts_delivery is None
    assert VoiceChoice(tts_engine='kokoro').tts_delivery.model_dump()==expected
    for value in ({'speed':.84},{'speed':1.16},{'pause_seconds':-.01},{'pause_seconds':.81},{'speed':float('nan')},{'pause_seconds':float('inf')},{'style':'whispering'}):
        with pytest.raises(ValidationError):VoiceDelivery(**value)
    assert VoiceDelivery(speed=.85,pause_seconds=.8).speed==.85

def test_profiles_opt_in_only_higgs():
    profile=TTSProfile(name='Higgs locale',provider='higgs',base_url='http://voice/v1',style_protocol='higgs_tags')
    saved=tts_api.save(profile)
    assert saved['style_protocol']=='higgs_tags' and tts_api.snapshot(saved['id'])['style_protocol']=='higgs_tags'
    for provider in ('openai','elevenlabs','google'):
        with pytest.raises(ValidationError):TTSProfile(**{**profile.model_dump(),'provider':provider})
    assert tts_api._public({'id':'a'*24})['style_protocol']=='none'

def test_settings_freeze_create_clone_restart_and_explicit_override():
    selected={'style':'calm','speed':.92,'pause_seconds':.4}
    store.save_settings(Settings(tts_delivery=selected))
    project=store.create(ProjectRequest(topic='Storia di Roma',start=False))
    assert project['tts_delivery']==selected
    store.save_settings(Settings(tts_delivery={'style':'engaging'}))
    assert store.project(project['id'])['tts_delivery']==selected
    store.update(project['id'],status='failed')
    assert store.restart_project(project['id'])['tts_delivery']==selected
    store.update(project['id'],status='completed')
    twin=store.clone_completed(project['id'])
    assert twin['tts_delivery']==selected
    override=store.clone_completed(project['id'],ProjectRequest(topic='Storia di Roma',start=False,tts_delivery={}))
    assert override['tts_delivery']==vd.DEFAULT_DELIVERY

def test_old_project_json_reads_legacy_default():
    project=store.create(ProjectRequest(topic='Storia di Roma',start=False))
    with store.connect() as connection:connection.execute('UPDATE projects SET tts_delivery=? WHERE id=?',('{}',project['id']))
    assert store.project(project['id'])['tts_delivery']==vd.DEFAULT_DELIVERY

def test_change_voice_preserves_selected_controls_and_invalidates_audio():
    project=store.create(ProjectRequest(topic='Storia di Roma',start=False))
    checkpoint=store.JOBS/project['id']/'checkpoints';checkpoint.mkdir();(checkpoint/'voice.done.json').write_text('{}')
    choice=VoiceChoice(tts_engine='kokoro',tts_delivery={'speed':.9,'pause_seconds':.3})
    result=tts.change_project_voice(project['id'],choice)
    assert result['tts_delivery']==choice.tts_delivery.model_dump()
    assert not (checkpoint/'voice.done.json').exists()

def test_kokoro_default_preserves_pack_and_custom_delivery_can_reset(tmp_path):
    old={'slug':'roma','schema_version':2,'scenes':[]}
    pack=copy.deepcopy(old)
    tts.configure_pack(pack,{'tts_engine':'kokoro'},tmp_path,tmp_path)
    assert pack==old
    tts.configure_pack(pack,{'tts_engine':'kokoro','tts_delivery':{'speed':.95}},tmp_path,tmp_path)
    assert pack['voice_delivery']['speed']==.95
    tts.configure_pack(pack,{'tts_engine':'kokoro','tts_delivery':vd.DEFAULT_DELIVERY},tmp_path,tmp_path)
    assert pack==old

def test_chatterbox_styles_map_to_parameters_and_cache_identity(monkeypatch,tmp_path):
    monkeypatch.setattr(tts,'chatterbox_installed',lambda path:True)
    original={};tts.configure_pack(original,{'tts_engine':'chatterbox'},tmp_path,tmp_path)
    assert original['voice']=='chatterbox-multilingual-v3@5bb1f6e;e=.35;c=.5;t=.7;r=1.2'
    assert 'voice_delivery' not in original
    variants=[]
    for style in vd.STYLES[1:]:
        pack={};tts.configure_pack(pack,{'tts_engine':'chatterbox','tts_delivery':{'style':style}},tmp_path,tmp_path)
        assert tuple(pack[name] for name in ('chatterbox_exaggeration','chatterbox_cfg_weight','chatterbox_temperature','chatterbox_repetition_penalty'))==vd.CHATTERBOX_STYLES[style]
        variants.append(pack['voice'])
    assert len(set(variants+[original['voice']]))==5

def api_project(provider='higgs',protocol='none',delivery=None):
    config=TTSProfile(name='Server vocale',provider=provider,base_url='http://voice/v1',response_format='wav',style_protocol=protocol).model_dump()
    return {'tts_engine':'api','tts_config':config,'tts_delivery':delivery or {}}

def test_api_default_fingerprint_unchanged_and_only_effective_style_changes_cache(tmp_path):
    project=api_project();config=project['tts_config']
    stable={key:config.get(key) for key in ('id','provider','base_url','model','voice','language','response_format','temperature','top_p','top_k','seed','max_new_tokens')}
    expected='tts-api:'+hashlib.sha256(json.dumps(stable,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
    pack={};tts.configure_pack(pack,project,tmp_path,tmp_path)
    assert pack['voice']==expected and 'voice_delivery' not in pack and 'style_protocol' not in pack['voice_api']
    ignored={};tts.configure_pack(ignored,api_project(delivery={'style':'calm'}),tmp_path,tmp_path)
    assert ignored['voice']==expected
    calm={};tts.configure_pack(calm,api_project(protocol='higgs_tags',delivery={'style':'calm'}),tmp_path,tmp_path)
    solemn={};tts.configure_pack(solemn,api_project(protocol='higgs_tags',delivery={'style':'solemn'}),tmp_path,tmp_path)
    assert calm['voice']!=solemn['voice']!=expected
    assert calm['voice_api']['style_protocol']=='higgs_tags'

def test_higgs_tags_only_decorate_outbound_body_and_never_reference_text(monkeypatch,tmp_path):
    seen=[]
    class Reply:
        content=wav_bytes()
    monkeypatch.setattr(tts_api,'_post',lambda url,**kwargs:(seen.append(kwargs) or Reply()))
    config=api_project(protocol='higgs_tags')['tts_config'];source='Roma cambia nel corso dei secoli.';copy_config=copy.deepcopy(config)
    reference=tmp_path/'reference.wav';reference.write_bytes(wav_bytes())
    for style,tags in vd.HIGGS_STYLE_TAGS.items():
        tts_api.synthesize_bytes(config,source,reference,reference_text='Campione originale.',delivery={'style':style})
        assert seen[-1]['data']['input']==tags+source
        assert seen[-1]['data']['reference_text']=='Campione originale.'
    assert config==copy_config and source=='Roma cambia nel corso dei secoli.'
    for provider,protocol in [('higgs','none'),('openai','none'),('elevenlabs','none'),('google','none')]:
        assert vd.synthesis_text({'provider':provider,'style_protocol':protocol},source,{'style':'solemn'})==source

def test_status_declares_effective_capabilities(tmp_path):
    plain=tts_api.save(TTSProfile(name='Higgs senza tag',provider='higgs',base_url='http://voice/v1'))
    tagged=tts_api.save(TTSProfile(name='Higgs con tag',provider='higgs',base_url='http://voice/v1',style_protocol='higgs_tags'))
    status=tts.status({'pipeline_path':str(tmp_path),'tts_delivery':{'speed':.9}})
    assert status['default_delivery']['speed']==.9
    caps={row['id']:row['delivery_capabilities'] for row in status['engines']}
    assert caps['kokoro']['styles']==['original']
    assert caps['chatterbox']['style_control']=='parameters'
    assert caps['api:'+plain['id']]['styles']==['original']
    assert caps['api:'+tagged['id']]['styles']==list(vd.STYLES)
    assert all(value['speed'] and value['pause_seconds'] and value['note'] for value in caps.values())

def test_default_api_preview_preserves_exact_audio_and_one_request(monkeypatch):
    calls=[];audio=wav_bytes()
    def fake(config,text,reference_path=None,api_key='',reference_text=''):
        calls.append(text);return audio,'wav'
    monkeypatch.setattr(tts_api,'synthesize_bytes',fake)
    value=TTSProfile(name='Server vocale',base_url='http://voice/v1')
    text='Prima frase. Seconda frase.'
    assert tts_api.test_voice(value,text=text,delivery=vd.DEFAULT_DELIVERY)==audio
    assert calls==[text]

def test_api_preview_custom_style_speed_and_pause_are_applied(monkeypatch):
    calls=[]
    def fake(config,text,reference_path=None,api_key='',reference_text='',delivery=None):
        calls.append((text,delivery));return wav_bytes(1),'wav'
    monkeypatch.setattr(tts_api,'synthesize_bytes',fake)
    value=TTSProfile(name='Server vocale',base_url='http://voice/v1')
    delivery={'style':'calm','speed':.9,'pause_seconds':.6}
    audio=tts_api.test_voice(value,text='Prima frase. Seconda frase.',delivery=delivery)
    assert [call[0] for call in calls]==['Prima frase.','Seconda frase.']
    assert all(call[1]==delivery for call in calls)
    assert duration(audio)==pytest.approx(2/.9+.6,abs=.07)

def test_split_keeps_all_text_and_caps_requests():
    text=' '.join(f'Frase numero {i}.' for i in range(12))
    lines=vd.preview_lines(text)
    assert len(lines)==8 and ' '.join(lines)==text
    for bad in ('   ','x'*801):
        with pytest.raises(ValueError):vd.preview_lines(bad)

def test_profile_test_and_saved_api_preview_use_requested_text_delivery(monkeypatch):
    saved=tts_api.save(TTSProfile(name='Server vocale',base_url='http://voice/v1'))
    seen=[];audio=wav_bytes()
    monkeypatch.setattr(tts_api,'test_voice',lambda value,**kwargs:(seen.append((value,kwargs)) or audio))
    request={'text':'Il Mediterraneo unisce queste città.','tts_delivery':{'style':'calm','speed':.92,'pause_seconds':.4}}
    response=client().post('/api/tts/profiles/test',json={**saved,**request})
    assert response.status_code==200 and response.content==audio
    assert seen[-1][1]['text']==request['text'] and seen[-1][1]['delivery'].speed==.92
    response=client().post('/api/tts/preview',json={**request,'tts_engine':'api','tts_profile_id':saved['id']})
    assert response.status_code==200 and response.headers['content-type']=='audio/wav'
    assert seen[-1][0].id==saved['id'] and seen[-1][1]['delivery'].pause_seconds==.4

def test_local_preview_route_and_worker_contract(monkeypatch,tmp_path):
    root=tmp_path/'pipeline';(root/'.venv/Scripts').mkdir(parents=True);(root/'.venv/Scripts/python.exe').touch()
    (root/'tools').mkdir();(root/'tools/preview_voice.py').touch()
    store.save_settings(Settings(pipeline_path=str(root)))
    captured={};audio=wav_bytes()
    def fake_run(command,**kwargs):
        payload=json.loads(Path(command[command.index('--request')+1]).read_text(encoding='utf-8'))
        captured.update(payload);captured['temporary']=Path(command[command.index('--output')+1]).parent
        assert kwargs['timeout']==900 and kwargs['cwd']==str(root.resolve())
        Path(command[command.index('--output')+1]).write_bytes(audio)
        return type('Result',(),{'returncode':0})()
    monkeypatch.setattr(vd.subprocess,'run',fake_run)
    response=client().post('/api/tts/preview',json={'tts_engine':'kokoro','text':'Le città diventano centri di cultura.','tts_delivery':{'speed':.9}})
    assert response.status_code==200 and response.content==audio
    assert captured['pack']['voice_delivery']['speed']==.9 and captured['delivery']['speed']==.9
    assert not captured['temporary'].exists()

@pytest.mark.parametrize('endpoint,payload',[
    ('/api/tts/preview',{'tts_engine':'kokoro','text':'Una prova breve.'}),
    ('/api/tts/profiles/test',{'name':'Server vocale','base_url':'http://voice/v1'}),
    ('/api/tts/profiles/'+'a'*24+'/model/unload',{}),
    ('/api/tts/profiles/'+'a'*24+'/voices/upload',{'reference_id':'b'*24,'voice_id':'prova'}),
])
def test_preview_and_lifecycle_refuse_active_production(monkeypatch,endpoint,payload):
    from app import runner
    monkeypatch.setattr(runner,'active',lambda *args:True)
    response=client().post(endpoint,json=payload)
    assert response.status_code==409

def test_preview_guard_serializes_and_releases_after_failure():
    assert not vd.preview_active()
    with pytest.raises(RuntimeError):
        with vd.preview_activity():
            assert vd.preview_active()
            with pytest.raises(HTTPException) as error:
                with vd.preview_activity():pytest.fail('Concurrent preview accepted')
            assert error.value.status_code==409
            raise RuntimeError('Simulated synthesis failure')
    assert not vd.preview_active()

def test_preview_text_size_validation():
    assert client().post('/api/tts/preview',json={'tts_engine':'kokoro','text':'x'*801}).status_code==422
    assert client().post('/api/tts/profiles/test',json={'name':'Voce','base_url':'http://voice/v1','text':'x'*801}).status_code==422

@pytest.mark.parametrize('rejection',[400,422])
def test_higgs_rejected_style_falls_back_once_with_trace(monkeypatch,rejection):
    config=api_project(protocol='higgs_tags')['tts_config'];calls=[];log=[];report={}
    class Reply:content=wav_bytes()
    def post(url,**kwargs):
        text=kwargs['json_body']['input'];calls.append(text)
        if text.startswith('<|'):raise tts_api.TTSHTTPError(rejection,'Formato rifiutato')
        return Reply()
    monkeypatch.setattr(tts_api,'_post',post)
    before=copy.deepcopy(config)
    audio,_=tts_api.synthesize_bytes(config,'Roma cambia.',delivery={'style':'calm'},log=log.append,delivery_report=report)
    assert len(calls)==2 and calls[-1]=='Roma cambia.' and audio.startswith(b'RIFF')
    assert report=={'requested_style':'calm','effective_style':'original','style_verified':False,'fallback':True}
    assert log and 'senza stile' in log[0] and config==before

@pytest.mark.parametrize('rejection',[401,403,408,429,500,503])
def test_higgs_style_never_masks_other_failures(monkeypatch,rejection):
    calls=[]
    def post(*args,**kwargs):
        calls.append(kwargs);raise tts_api.TTSHTTPError(rejection,'Richiesta rifiutata')
    monkeypatch.setattr(tts_api,'_post',post)
    with pytest.raises(tts_api.TTSHTTPError):
        tts_api.synthesize_bytes(api_project(protocol='higgs_tags')['tts_config'],'Roma cambia.',delivery={'style':'calm'})
    assert len(calls)==1

def test_second_higgs_format_rejection_propagates(monkeypatch):
    calls=[]
    def post(*args,**kwargs):
        calls.append(kwargs);raise tts_api.TTSHTTPError(400,'Formato rifiutato')
    monkeypatch.setattr(tts_api,'_post',post)
    with pytest.raises(tts_api.TTSHTTPError):
        tts_api.synthesize_bytes(api_project(protocol='higgs_tags')['tts_config'],'Roma cambia.',delivery={'style':'calm'})
    assert len(calls)==2

def test_style_success_reports_unverified_and_fallback_manifest_survives_resume(monkeypatch,tmp_path):
    saved=tts_api.save(TTSProfile(name='Higgs locale',provider='higgs',base_url='http://voice/v1',style_protocol='higgs_tags',response_format='wav'))
    project={'tts_engine':'api','tts_profile_id':saved['id'],'tts_config':tts_api.snapshot(saved['id']),'tts_delivery':{'style':'calm'}}
    pack={'slug':'roma','scenes':[{'id':'s1','lines':['Roma cambia nel corso dei secoli.']}]};tts.configure_pack(pack,project,tmp_path,tmp_path)
    monkeypatch.setattr(tts_api,'higgs_activity',lambda *args,**kwargs:nullcontext())
    calls=[]
    class Reply:content=wav_bytes()
    def post(url,**kwargs):
        text=kwargs['json_body']['input'];calls.append(text)
        if text.startswith('<|'):raise tts_api.TTSHTTPError(422,'Tag non supportati')
        return Reply()
    monkeypatch.setattr(tts_api,'_post',post)
    before=copy.deepcopy(pack);events=[]
    tts_api.synthesize_pack(pack,project,tmp_path,lambda:None,events.append)
    path=tmp_path/'build/roma/voice/external-voice-cache.json'
    first=json.loads(path.read_text(encoding='utf-8'))['items']['s1:0']['delivery']
    assert first['fallback'] and first['effective_style']=='original'
    tts_api.synthesize_pack(pack,project,tmp_path,lambda:None,events.append)
    assert len(calls)==2 and json.loads(path.read_text(encoding='utf-8'))['items']['s1:0']['delivery']==first
    assert pack==before
    monkeypatch.setattr(tts_api,'_post',lambda *args,**kwargs:Reply())
    report={};tts_api.synthesize_bytes(project['tts_config'],'Roma cambia.',delivery={'style':'calm'},delivery_report=report)
    assert report['effective_style']=='calm' and not report['style_verified'] and not report['fallback']

def test_preview_reports_style_fallback_to_ui(monkeypatch):
    def fake(value,**kwargs):
        kwargs['delivery_report'].append({'fallback':True});return wav_bytes()
    monkeypatch.setattr(tts_api,'test_voice',fake)
    response=client().post('/api/tts/profiles/test',json={'name':'Higgs locale','provider':'higgs','base_url':'http://voice/v1','style_protocol':'higgs_tags','tts_delivery':{'style':'calm'}})
    assert response.status_code==200 and response.headers['X-Voice-Style-Fallback']=='true'
