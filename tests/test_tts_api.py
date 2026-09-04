import array,base64,io,json,math,wave
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app import store,tts,tts_api,server
from app.models import ProjectRequest,Settings,TTSProfile

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    (tmp_path/'jobs').mkdir();monkeypatch.setattr(store,'DATA',tmp_path);monkeypatch.setattr(store,'JOBS',tmp_path/'jobs')
    monkeypatch.delenv('DOCUMENTARIAI_TTS_API_KEY',raising=False);store.init()

def wav_bytes(seconds=.5,sample_rate=24000):
    pcm=array.array('h',(round(math.sin(i*2*math.pi*220/sample_rate)*2500) for i in range(round(seconds*sample_rate))))
    out=io.BytesIO()
    with wave.open(out,'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(sample_rate);f.writeframes(pcm.tobytes())
    return out.getvalue()

class Reply:
    def __init__(self,content=b'',status=200,body=None):self.content=content;self.status_code=status;self.ok=status<400;self._body=body
    @property
    def text(self):return self.content.decode(errors='replace')
    def json(self):return self._body if self._body is not None else json.loads(self.content)

def saved(provider='higgs',**changes):
    value=TTSProfile(name='Voce documentari',provider=provider,base_url='http://tts.local:8000/v1',model='higgs-tts-3',voice='narratore',api_key='private-tts-key',**changes)
    return tts_api.save(value)

def test_profiles_encrypt_keys_and_projects_freeze_public_config():
    item=saved();disk=(store.DATA/tts_api.PROFILE_FILE).read_text()
    assert 'private-tts-key' not in disk and item['has_api_key'] and 'api_key' not in item
    assert tts_api.secret_for(item['id'])=='private-tts-key'
    store.save_settings(Settings(tts_engine='api',tts_profile_id=item['id']))
    project=store.create(ProjectRequest(topic='Storia di prova',start=False))
    assert project['tts_engine']=='api' and project['tts_profile_id']==item['id']
    assert project['tts_config']['name']=='Voce documentari' and 'api_key' not in project['tts_config']
    tts_api.save(TTSProfile(**{**tts_api.profile(item['id']),'name':'Nome modificato','api_key':None}))
    assert store.project(project['id'])['tts_config']['name']=='Voce documentari'

def test_openai_and_higgs_contracts(monkeypatch,tmp_path):
    calls=[]
    def post(url,**kwargs):calls.append((url,kwargs));return Reply(wav_bytes())
    monkeypatch.setattr(tts_api.requests,'post',post)
    openai=dict(provider='openai',base_url='http://host/v1',model='m',voice='v',response_format='wav',timeout=20)
    audio,kind=tts_api.synthesize_bytes(openai,'Ciao',api_key='key')
    assert kind=='wav' and audio.startswith(b'RIFF') and calls[-1][0].endswith('/v1/audio/speech')
    assert calls[-1][1]['json']['input']=='Ciao' and calls[-1][1]['headers']['Authorization']=='Bearer key'
    reference=tmp_path/'reference.wav';reference.write_bytes(wav_bytes())
    higgs={**openai,'provider':'higgs'};tts_api.synthesize_bytes(higgs,'Testo',reference,'key','Trascrizione esatta')
    assert calls[-1][0].endswith('/v1/audio/voice-clone')
    assert calls[-1][1]['data']['input']=='Testo' and calls[-1][1]['data']['reference_text']=='Trascrizione esatta'
    assert calls[-1][1]['files']['reference_audio'][0]=='reference.wav'

def test_elevenlabs_and_google_contracts(monkeypatch):
    calls=[]
    google_audio=wav_bytes()
    def post(url,**kwargs):
        calls.append((url,kwargs))
        return Reply(body={'audioContent':base64.b64encode(google_audio).decode()}) if 'text:synthesize' in url else Reply(wav_bytes())
    monkeypatch.setattr(tts_api.requests,'post',post)
    config=dict(provider='elevenlabs',base_url='https://api.elevenlabs.io/v1',model='eleven_multilingual_v2',voice='voice id',language='it-IT',timeout=20)
    tts_api.synthesize_bytes(config,'Ciao',api_key='eleven-key')
    assert '/text-to-speech/voice%20id?output_format=' in calls[-1][0]
    assert calls[-1][1]['headers']['xi-api-key']=='eleven-key' and calls[-1][1]['json']['model_id']=='eleven_multilingual_v2'
    config.update(provider='google',base_url='https://texttospeech.googleapis.com/v1',voice='it-IT-Standard-A')
    audio,kind=tts_api.synthesize_bytes(config,'Buongiorno',api_key='oauth-token')
    assert kind=='wav' and audio==google_audio
    assert calls[-1][1]['headers']['Authorization']=='Bearer oauth-token'
    assert calls[-1][1]['json']['voice']=={'languageCode':'it-IT','name':'it-IT-Standard-A'}

def test_api_pack_populates_the_existing_narration_cache(monkeypatch,tmp_path):
    item=saved(provider='openai',response_format='wav');work=tmp_path/'work';work.mkdir()
    project={'tts_engine':'api','tts_profile_id':item['id'],'tts_config':tts_api.snapshot(item['id']),'tts_reference_id':''}
    pack={'slug':'prova','voice':'old','scenes':[{'id':'s1','lines':['Una frase abbastanza lunga per la prova.']}],'pronunciation':{'prova':'pròva'}}
    tts.configure_pack(pack,project,work,tmp_path)
    count={'n':0}
    def fake(config,text,reference_path=None,api_key='',reference_text=''):
        count['n']+=1;assert api_key=='private-tts-key';return wav_bytes(),'wav'
    monkeypatch.setattr(tts_api,'synthesize_bytes',fake)
    messages=[];tts_api.synthesize_pack(pack,project,work,lambda:None,messages.append)
    tts_api.synthesize_pack(pack,project,work,lambda:None,messages.append)
    assert count['n']==1 and len(list((work/'build/prova/voice').glob('*.wav')))==1
    manifest=json.loads((work/'build/prova/voice/external-voice-cache.json').read_text(encoding='utf-8'))
    assert manifest['backend']=='tts_api' and manifest['items']['s1:0']['file'].endswith('.wav')
    assert 'segmento 1/1' in messages[-1]

def test_profile_routes_and_reference_rules(monkeypatch,tmp_path):
    client=TestClient(server.app,headers={'X-DocumentariAI':'studio'})
    payload=TTSProfile(name='Server locale',provider='openai',base_url='http://localhost:9000/v1').model_dump()
    response=client.post('/api/tts/profiles',json=payload);assert response.status_code==201
    profile_id=response.json()['id'];status=client.get('/api/tts').json()
    assert any(x['id']=='api:'+profile_id and not x['supports_reference'] for x in status['engines'])
    with pytest.raises(ValueError,match='soltanto'):tts.ensure_available('api','a'*24,tmp_path,profile_id,tts_api.snapshot(profile_id))
    assert 'encrypted_key' not in client.get('/api/tts/profiles').text
    monkeypatch.setattr(tts_api,'test_voice',lambda value,**kwargs:wav_bytes())
    preview=client.post('/api/tts/profiles/test',json={**payload,'id':profile_id})
    assert preview.status_code==200 and preview.headers['content-type']=='audio/wav' and preview.content.startswith(b'RIFF')
    store.save_settings(Settings(tts_engine='api',tts_profile_id=profile_id))
    assert client.delete('/api/tts/profiles/'+profile_id).status_code==409
    store.save_settings(Settings())
    assert client.delete('/api/tts/profiles/'+profile_id).status_code==204

def test_errors_do_not_leak_credentials(monkeypatch):
    monkeypatch.setattr(tts_api.requests,'post',lambda *a,**k:Reply(b'{"error":{"message":"rifiutato"}}',401,{'error':{'message':'rifiutato'}}))
    with pytest.raises(ValueError,match='HTTP 401') as caught:
        tts_api.synthesize_bytes(dict(provider='openai',base_url='http://host/v1',model='m',voice='',response_format='mp3',timeout=10),'Ciao',api_key='top-secret')
    assert 'top-secret' not in str(caught.value)

def test_higgs_activity_loads_once_and_always_unloads(monkeypatch,tmp_path):
    calls=[]
    def post(url,**kwargs):
        calls.append((url,kwargs))
        if url.endswith('/model/load'):return Reply(body={'ok':True,'model_state':'ready','already_loaded':False})
        if url.endswith('/model/unload'):return Reply(body={'ok':True,'model_state':'unloaded','already_unloaded':False})
        return Reply(wav_bytes())
    monkeypatch.setattr(tts_api.requests,'post',post)
    config=dict(provider='higgs',base_url='http://gpu-pc:8095/v1',model='',voice='',response_format='wav',timeout=900,
                temperature=1.0,top_p=.95,top_k=50,seed=-1,max_new_tokens=2048)
    reference=tmp_path/'reference.wav';reference.write_bytes(wav_bytes())
    with pytest.raises(RuntimeError):
        with tts_api.higgs_activity(config):
            tts_api.synthesize_bytes(config,'Testo',reference,reference_text='Testo originale')
            raise RuntimeError('interruzione simulata')
    assert [url.rsplit('/v1/',1)[-1] for url,_ in calls]==['model/load','audio/voice-clone','model/unload']
    assert calls[1][1]['timeout']==(10,900)

def test_higgs_status_and_persistent_voice_contract(monkeypatch,tmp_path):
    item=saved(timeout=900,response_format='wav');record=tts.upload_reference(wav_bytes(5),'mia.wav','Testo pronunciato')
    calls=[]
    monkeypatch.setattr(tts_api.requests,'get',lambda url,**kwargs:Reply(body={'server':'up','model_state':'unloaded'}))
    def post(url,**kwargs):
        calls.append((url,kwargs))
        if url.endswith('/model/load'):return Reply(body={'ok':True,'model_state':'ready','already_loaded':False})
        if url.endswith('/model/unload'):return Reply(body={'ok':True,'model_state':'unloaded','already_unloaded':False})
        return Reply(body={'ok':True,'voice_id':'emanuele_it','voice':'emanuele_it.wav'})
    monkeypatch.setattr(tts_api.requests,'post',post)
    client=TestClient(server.app,headers={'X-DocumentariAI':'studio'})
    status=client.get('/api/tts/profiles/'+item['id']+'/status');assert status.status_code==200 and status.json()['model_state']=='unloaded'
    assert client.post('/api/tts/profiles/'+item['id']+'/model/load').json()['model_state']=='ready'
    assert client.post('/api/tts/profiles/'+item['id']+'/model/unload').json()['model_state']=='unloaded'
    result=client.post('/api/tts/profiles/'+item['id']+'/voices/upload',json={'reference_id':record['id'],'voice_id':'emanuele_it'})
    assert result.status_code==200 and result.json()['voice']=='emanuele_it.wav'
    assert calls[-1][0].endswith('/v1/voices/upload') and calls[-1][1]['data']['reference_text']=='Testo pronunciato'
    assert calls[-1][1]['files']['reference_audio'][0]=='reference.wav'

def test_higgs_reference_longer_than_thirty_seconds_reaches_test_and_voice_routes(monkeypatch,tmp_path):
    item=saved(timeout=900,response_format='wav');record=tts.upload_reference(wav_bytes(31),'campione-lungo.wav','Trascrizione completa')
    tts.ensure_available('api',record['id'],tmp_path,item['id'],tts_api.snapshot(item['id']))
    monkeypatch.setattr(tts_api,'test_voice',lambda value,**kwargs:wav_bytes())
    monkeypatch.setattr(tts_api,'higgs_upload_voice',lambda *args,**kwargs:{'ok':True,'voice':'campione_lungo.wav'})
    client=TestClient(server.app,headers={'X-DocumentariAI':'studio'})
    preview=client.post('/api/tts/profiles/test',json={**tts_api.profile(item['id']),'reference_id':record['id']})
    uploaded=client.post('/api/tts/profiles/'+item['id']+'/voices/upload',json={'reference_id':record['id'],'voice_id':'campione_lungo'})
    assert preview.status_code==200 and uploaded.status_code==200
