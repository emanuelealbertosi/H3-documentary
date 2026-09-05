"""Higgs identity controls stay fixed across cues, retries and cached resumes."""
import copy,hashlib,io,json,wave
from contextlib import nullcontext
import pytest
from app import store,tts,tts_api
from app.models import ProjectRequest,Settings,TTSProfile


def wav_bytes(seconds=.5,amplitude=1000):
    output=io.BytesIO()
    with wave.open(output,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000)
        audio.writeframes(amplitude.to_bytes(2,'little',signed=True)*round(seconds*24000))
    return output.getvalue()


class Reply:
    def __init__(self,status=200):
        self.status_code=status;self.ok=status<400;self.content=wav_bytes();self.text='Temporary failure'
    def json(self):return {'detail':self.text}


@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    (tmp_path/'jobs').mkdir();monkeypatch.setattr(store,'DATA',tmp_path);monkeypatch.setattr(store,'JOBS',tmp_path/'jobs')
    monkeypatch.delenv('DOCUMENTARIAI_TTS_API_KEY',raising=False);store.init()
    monkeypatch.setattr(tts_api,'higgs_activity',lambda *args,**kwargs:nullcontext())
    monkeypatch.setattr(tts_api.time,'sleep',lambda *_:None)
    def forbidden(*args,**kwargs):raise AssertionError('No real HTTP requests in seed tests')
    monkeypatch.setattr(tts_api.requests,'get',forbidden);monkeypatch.setattr(tts_api.requests,'post',forbidden)


def profile(seed=42,voice=''):
    return tts_api.save(TTSProfile(name='Higgs di prova',provider='higgs',base_url='http://higgs.invalid/v1',
                                   response_format='wav',seed=seed,voice=voice))


def capture_post(monkeypatch,calls,failures=()):
    attempts=iter(failures)
    def post(url,**kwargs):
        fields=copy.deepcopy(kwargs['json'] or kwargs['data'])
        reference=kwargs['files']['reference_audio'][1].read() if kwargs.get('files') else None
        calls.append({'url':url,'fields':fields,'reference':reference})
        failure=next(attempts,None)
        if isinstance(failure,Exception):raise failure
        return Reply(failure or 200)
    monkeypatch.setattr(tts_api.requests,'post',post)


@pytest.mark.parametrize('seed',[0,42])
@pytest.mark.parametrize('cloning',[False,True])
def test_seed_and_reference_unchanged_across_transport_retry_and_style_fallback(seed,cloning,tmp_path,monkeypatch):
    config=tts_api.snapshot(profile(seed,voice='narratore.wav')['id']);config['style_protocol']='higgs_tags'
    reference=tmp_path/'clone.wav' if cloning else None
    if reference:reference.write_bytes(wav_bytes(5))
    calls=[]
    # Exercise a fully consumed upload on each attempt: _post must rewind it.
    capture_post(monkeypatch,calls,[tts_api.requests.ConnectionError('test'),503,422])
    before=copy.deepcopy(config)
    tts_api.synthesize_bytes(config,'Prima frase.',reference,reference_text='Trascrizione.',delivery={'style':'calm'})
    tts_api.synthesize_bytes(config,'Seconda frase.',reference,reference_text='Trascrizione.',delivery={'style':'calm'})
    assert len(calls)==5 and all(int(call['fields']['seed'])==seed for call in calls)
    assert calls[0]['fields']['input'].startswith('<|emotion:') and calls[3]['fields']['input']=='Prima frase.'
    assert calls[4]['fields']['input'].endswith('Seconda frase.') and config==before
    if cloning:
        assert all(call['url'].endswith('/audio/voice-clone') for call in calls)
        assert all(call['reference']==reference.read_bytes() and call['fields']['reference_text']=='Trascrizione.' for call in calls)
    else:
        assert all(call['url'].endswith('/audio/speech') and call['fields']['voice']=='narratore.wav' for call in calls)


@pytest.mark.parametrize('seed',[0,42])
@pytest.mark.parametrize('cloning',[False,True])
def test_project_seed_survives_profile_change_and_cached_resume_but_explicit_change_resynthesizes(seed,cloning,tmp_path,monkeypatch):
    saved=profile(seed,voice='narratore.wav')
    reference=tts.upload_reference(wav_bytes(5),'voce.wav','Trascrizione.') if cloning else None
    store.save_settings(Settings(tts_engine='api',tts_profile_id=saved['id'],tts_reference_id=reference['id'] if reference else ''))
    project=store.create(ProjectRequest(topic='Storia per la prova',start=False))
    work=tmp_path/'work';work.mkdir()
    pack={'slug':'prova','scenes':[{'id':'s1','lines':['Primo passaggio.','Secondo passaggio.']},{'id':'s2','lines':['Ultimo passaggio.']} ]}
    tts.configure_pack(pack,project,work,tmp_path)
    calls=[];capture_post(monkeypatch,calls)
    attempts=iter([False,True])
    def cancel():
        if next(attempts,False):raise InterruptedError('Interruzione di prova')
    with pytest.raises(InterruptedError):tts_api.synthesize_pack(pack,project,work,cancel,lambda _:None)
    assert len(calls)==1
    # Admin changes must not silently alter the voice of an existing project.
    tts_api.save(TTSProfile(**{**tts_api.profile(saved['id']),'seed':17}))
    project=store.project(project['id']);tts.configure_pack(pack,project,work,tmp_path)
    assert project['tts_config']['seed']==seed
    logs=[];tts_api.synthesize_pack(pack,project,work,lambda:None,logs.append)
    tts_api.synthesize_pack(pack,project,work,lambda:None,logs.append)
    assert len(calls)==3 and all(int(call['fields']['seed'])==seed for call in calls)
    output=work/'build/prova/voice';manifest=json.loads((output/'external-voice-cache.json').read_text(encoding='utf-8'))
    assert manifest['synthesis']['seed']==seed and manifest['synthesis']['seed_mode']=='fixed'
    if reference:assert manifest['synthesis']['reference_sha256']==reference['sha256']
    else:assert manifest['synthesis']['voice']=='narratore.wav'
    assert 'base_url' not in manifest['synthesis'] and 'id' not in manifest['synthesis']
    first_voice=pack['voice'];first_files={item['file'] for item in manifest['items'].values()}
    project['tts_config']=tts_api.snapshot(saved['id']);tts.configure_pack(pack,project,work,tmp_path)
    tts_api.synthesize_pack(pack,project,work,lambda:None,logs.append)
    changed=json.loads((output/'external-voice-cache.json').read_text(encoding='utf-8'))
    assert pack['voice']!=first_voice and len(calls)==6
    assert all(int(call['fields']['seed'])==17 for call in calls[3:])
    assert first_files.isdisjoint(item['file'] for item in changed['items'].values())
    assert all((output/name).is_file() for name in first_files)


def test_cloning_cache_identity_includes_recording_even_with_identical_transcript(tmp_path,monkeypatch):
    saved=profile();project={'tts_engine':'api','tts_profile_id':saved['id'],'tts_config':tts_api.snapshot(saved['id'])}
    first=tts.upload_reference(wav_bytes(5,1000),'prima.wav','Stessa trascrizione.')
    second=tts.upload_reference(wav_bytes(5,2000),'seconda.wav','Stessa trascrizione.')
    assert first['sha256']!=second['sha256']
    pack={'slug':'cloni','scenes':[{'id':'s1','lines':['La stessa frase viene narrata.']} ]}
    calls=[];capture_post(monkeypatch,calls)
    identities=[]
    for recording in (first,first,second,second):
        project['tts_reference_id']=recording['id'];tts.configure_pack(pack,project,tmp_path,tmp_path)
        tts_api.synthesize_pack(pack,project,tmp_path,lambda:None,lambda _:None)
        identities.append((pack['voice'],tts_api.synthesis_key(pack,'s1',0,pack['scenes'][0]['lines'][0],tmp_path)))
        assert pack['voice_api']['reference_sha256']==recording['sha256']
    assert identities[0]==identities[1] and identities[2]==identities[3] and identities[0]!=identities[2]
    assert len(calls)==2 and calls[0]['reference']!=calls[1]['reference']


@pytest.mark.parametrize('seed',[-1,0,42])
@pytest.mark.parametrize('identity',['absent','saved','reference'])
def test_higgs_log_explains_seed_and_identity_without_guaranteeing_speaker(seed,identity,tmp_path):
    messages=[];config={'provider':'higgs','seed':seed,'voice':'narratore.wav' if identity=='saved' else ''}
    reference=tmp_path/'reference.wav' if identity=='reference' else None
    if reference:reference.write_bytes(wav_bytes(5))
    details=tts_api._higgs_synthesis_details(config,reference,messages.append)
    assert len(messages)==2
    assert ('casuale (-1)' if seed<0 else f'fisso {seed}') in messages[0]
    assert details['seed']==seed and details['seed_mode']==('random' if seed<0 else 'fixed')
    if identity=='absent':assert 'non garantisce lo stesso narratore' in messages[1]
    elif identity=='saved':assert 'voce registrata' in messages[1] and details['voice']=='narratore.wav'
    else:
        assert 'stesso campione vocale' in messages[1]
        assert details['reference_sha256']==hashlib.sha256(reference.read_bytes()).hexdigest()
