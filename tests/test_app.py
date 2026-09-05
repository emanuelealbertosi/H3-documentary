import os,json,threading,copy,io,wave,array
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import pytest
os.environ.setdefault("DOCUMENTARIAI_DATA",str(Path(__file__).parent/"output/state"))
from app import store,server,pipeline,runner
from app.models import Settings,ProjectRequest,Outline,Review
from app.llm import LLM,extract_json,ModelError,provider_error
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    (tmp_path/"jobs").mkdir()
    for module in [store,server,pipeline,runner]:
        if hasattr(module,"DATA"):monkeypatch.setattr(module,"DATA",tmp_path)
        if hasattr(module,"JOBS"):monkeypatch.setattr(module,"JOBS",tmp_path/"jobs")
    store.init()
@pytest.fixture
def client():
    return TestClient(server.app,headers={"X-DocumentariAI":"studio"})

def test_provider_url_normalization():
    for url,expected in [("http://localhost:1234","http://localhost:1234/v1"),
         ("http://localhost:11434/v1/chat/completions","http://localhost:11434/v1"),
         ("https://host.example/api/v1/","https://host.example/api/v1")]:
        assert Settings(base_url=url).base_url==expected
    for url in ["file:///secrets","http://key:pass@host/v1","https://host/v1?key=secret"]:
        with pytest.raises(ValueError):Settings(base_url=url)

def test_boundary_usage_persists_and_project_exposes_only_frozen_materials(client):
    value=Settings(boundary_usage='education_nc',api_key='private-test-key')
    assert client.put('/api/settings',json=value.model_dump()).status_code==200
    assert client.get('/api/settings').json()['boundary_usage']=='education_nc'
    value.api_key=None;value.model='another-model'
    assert client.put('/api/settings',json=value.model_dump()).status_code==200
    assert store.settings(True)['api_key']=='private-test-key'
    pid=store.create(ProjectRequest(topic='Confini europei',start=False))['id']
    endpoint=f'/api/projects/{pid}'
    assert client.get(endpoint+'/boundaries').json() is None
    report={'usage':'education_nc','layers':[{'id':'fr','status':'sourced'}]}
    store.write_json(store.JOBS/pid/'checkpoints/boundary-report.json',report)
    store.write_json(store.JOBS/pid/'workspace/assets/boundaries/cshapes.geojson',{'type':'FeatureCollection','features':[]})
    store.write_json(store.JOBS/pid/'checkpoints/boundary-outline.json',{'private':'not an exposed checkpoint'})
    assert client.get(endpoint+'/boundaries').json()==report
    path='workspace/assets/boundaries/cshapes.geojson'
    assert path in {v['path'] for v in client.get(endpoint+'/files').json()}
    assert client.get(endpoint+'/file',params={'path':path}).status_code==200
    assert client.get(endpoint+'/file',params={'path':'checkpoints/boundary-outline.json'}).status_code==404
    assert client.get(endpoint+'/file',params={'path':'../../settings.json'}).status_code==404
def test_secrets_masking_rotation(client):
    a=Settings(model="model",api_key="test-only-secret")
    r=client.put("/api/settings",json=a.model_dump());assert r.status_code==200
    assert "test-only-secret" not in r.text
    assert client.get("/api/settings").json()["has_api_key"]
    assert store.settings(True)["api_key"]=="test-only-secret"
    assert "test-only-secret" not in (store.DATA/"settings.json").read_text()
    a.api_key=None;a.base_url="http://different.example/v1"
    client.put("/api/settings",json=a.model_dump())
    assert store.settings(True)["api_key"]==""
def test_unsaved_provider_does_not_receive_old_key():
    store.save_settings(Settings(api_key="secret"))
    assert server.connection(Settings(base_url="http://different.example/v1"))["api_key"]==""
    assert server.connection(Settings())["api_key"]=="secret"
def test_multiple_servers_remember_model_options_and_separate_encrypted_keys(client):
    first=Settings(provider='openai',base_url='https://one.example/v1',model='model-one',api_key='first-secret',max_tokens=12000,json_mode=True,reasoning_mode='off')
    second=Settings(provider='vllm',base_url='http://192.168.1.50:8000/v1',model='model-two',api_key='second-secret',max_tokens=6000)
    assert client.put('/api/settings',json=first.model_dump()).status_code==200
    assert client.put('/api/settings',json=second.model_dump()).status_code==200
    public=client.get('/api/settings').json()
    assert public['model']=='model-two' and len(public['saved_servers'])==2
    assert {p['model'] for p in public['saved_servers']}=={'model-one','model-two'}
    assert {p['model']:p['reasoning_mode'] for p in public['saved_servers']}=={'model-one':'off','model-two':'server'}
    assert all(p['has_api_key'] for p in public['saved_servers'])
    assert server.connection(first.model_copy(update={'api_key':None}))['api_key']=='first-secret'
    assert server.connection(second.model_copy(update={'api_key':None}))['api_key']=='second-secret'
    # Changing only the selected model keeps that server's encrypted key.
    changed=first.model_copy(update={'model':'model-one-new','api_key':None})
    client.put('/api/settings',json=changed.model_dump())
    assert store.settings()['model']=='model-one-new'
    assert server.connection(changed)['api_key']=='first-secret'
    disk=(store.DATA/'settings.json').read_text()
    assert 'first-secret' not in disk and 'second-secret' not in disk
    assert 'server_profiles' in disk
def test_previous_single_server_settings_are_migrated_without_losing_key():
    legacy=Settings(provider='openai',base_url='https://legacy.example/v1',model='legacy-model').model_dump()
    legacy.pop('api_key');legacy.pop('clear_api_key');legacy['encrypted_key']=store.protect('legacy-secret')
    store.write_json(store.DATA/'settings.json',legacy)
    public=store.settings()
    assert len(public['saved_servers'])==1 and public['saved_servers'][0]['model']=='legacy-model'
    assert store.settings(True)['api_key']=='legacy-secret'
    store.save_settings(Settings(provider='ollama',base_url='http://localhost:11434/v1',model='new-model'))
    request=Settings(provider='openai',base_url='https://legacy.example/v1',model='legacy-model')
    assert server.connection(request)['api_key']=='legacy-secret'
def test_cross_site_mutations_blocked(client):
    assert client.post("/api/projects",json={"topic":"Waterloo"},headers={"Origin":"https://evil.example"}).status_code==403
    c=TestClient(server.app)
    assert c.post("/api/projects",json={"topic":"Waterloo"}).status_code==403
    assert client.get("/api/health",headers={"Host":"evil.example"}).status_code==403
def test_admin_reasoning_control_is_visible_and_frontend_is_revalidated(client):
    version=(Path(__file__).resolve().parents[1]/'VERSION').read_text().strip()
    shell=client.get('/admin')
    assert shell.status_code==200 and shell.headers['cache-control']=='no-cache'
    assert client.get('/documents').headers['cache-control']=='no-cache'
    assert f'/static/app.js?v={version}' in shell.text
    frontend=client.get(f'/static/app.js?v={version}')
    assert frontend.headers['cache-control']=='no-cache'
    assert frontend.text.index("select('reasoning_mode','Reasoning del modello'") < frontend.text.index("'<details><summary>Parametri del modello")
    assert 'Voce e cloning one-shot' in frontend.text
    assert 'sidebar-toggle' in shell.text and 'h3-sidebar-collapsed' in frontend.text
    assert 'Tempo di elaborazione:' in frontend.text
    media_frontend=client.get(f'/static/media.js?v={version}').text
    media_styles=client.get('/static/media.css').text
    assert 'Immagini del film' in frontend.text and 'Aggiorna solo le scene interessate' in media_frontend
    assert 'media-column-resizer' in media_frontend and 'h3-media-target-width' in media_frontend
    assert '--media-target-width:380px' in media_styles and 'cursor:col-resize' in media_styles
    assert "const all=project?[...(project.targets||[]),...extra]" in media_frontend
    assert 'Scollega' in media_frontend and 'delete-image' in media_frontend and 'visual-replace' in media_frontend
    assert 'media-link-modal' in media_frontend and 'Scegli dal computer' in media_frontend
    assert "new URLSearchParams(location.search).get('slot')" in media_frontend and "media?slot=" in frontend.text
    assert 'Inserisci le mie immagini associate' not in frontend.text and 'use_media:true' in frontend.text
    assert 'project-use-media' not in media_frontend and 'enableProjectMedia' in media_frontend
    assert 'Impostazioni per la prossima versione' in frontend.text and 'reg-review-visuals' in frontend.text
    assert 'data-reg-document' in frontend.text and 'a.pathname+a.search+a.hash' in frontend.text
    assert 'memoria visuale' in media_frontend and 'prossimi progetti' in media_frontend
    assert any(x['id']=='chatterbox' and 'Chatterbox Multilingual V3' in x['name'] for x in client.get('/api/tts').json()['engines'])

def test_voice_reference_upload_and_project_selection(client):
    pcm=array.array('h',[800]*16000*5);raw=io.BytesIO()
    with wave.open(raw,'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm.tobytes())
    uploaded=client.post('/api/tts/references?filename=MiaVoce.wav',content=raw.getvalue(),headers={'Content-Type':'audio/wav'});assert uploaded.status_code==201
    voice=uploaded.json();status=client.get('/api/tts').json()
    assert status['voices'][0]['id']==voice['id'] and status['voices'][0]['name']=='MiaVoce'
    project=client.post('/api/projects',json={'topic':'Battaglia di prova','start':False,'tts_engine':'chatterbox','tts_reference_id':voice['id']}).json()
    assert project['tts_engine']=='chatterbox' and project['tts_reference_id']==voice['id']
def test_create_draft_and_preserve_on_revision(client):
    p=client.post("/api/projects",json={"topic":"Battaglia di prova","minutes":5,"start":False}).json()
    assert p["status"]=="draft"
    store.update(p['id'],result={'research':{'fallback_used':True}})
    root=server.JOBS/p["id"];(root/"checkpoints").mkdir();(root/"workspace").mkdir()
    (root/"workspace/battle.json").write_text("old")
    r=client.patch("/api/projects/"+p["id"],json={"notes":"Nuove indicazioni"})
    assert r.status_code==200
    assert r.json()['result']=={}
    assert not(root/"workspace").exists()
    assert list(root.glob("workspace-previous-*/battle.json"))[0].read_text()=="old"

def test_visual_review_is_opt_in_persistent_and_cannot_be_skipped(client):
    project=client.post('/api/projects',json={'topic':'Revisione visuale di prova','start':False,'review_visuals':True}).json()
    assert project['review_visuals']==1
    store.update(project['id'],status='review',stage='Revisione immagini e sfondi')
    response=client.post('/api/projects/'+project['id']+'/start')
    assert response.status_code==400 and 'revisione delle immagini' in response.text
    store.update(project['id'],status='completed')
    clone=store.clone_completed(project['id'])
    assert clone['review_visuals']==1

def test_completed_regeneration_creates_numbered_twins_and_keeps_original(client):
    original=client.post('/api/projects',json={'topic':'Viaggio di prova','minutes':3,'start':False}).json()
    store.update(original['id'],status='completed',stage='Documentario completato',progress=100,result={'sha256':'old'})
    old_file=server.JOBS/original['id']/'workspace/output/old.mp4';old_file.parent.mkdir(parents=True);old_file.write_bytes(b'old-film')
    second=client.post('/api/projects/'+original['id']+'/regenerate')
    assert second.status_code==200 and second.json()['mode']=='new_version'
    v2=second.json()['project'];assert v2['id']!=original['id'] and v2['version']==2 and v2['parent_id']==original['id']
    assert store.project(original['id'])['status']=='completed' and old_file.read_bytes()==b'old-film'
    third=client.post('/api/projects/'+original['id']+'/regenerate').json()['project']
    assert third['version']==3 and third['family_id']==v2['family_id']==original['id']

def test_completed_regeneration_accepts_a_complete_new_configuration(client):
    original=client.post('/api/projects',json={'topic':'Biografia iniziale','minutes':3,'notes':'Prima versione','start':False,'review_visuals':False}).json()
    store.update(original['id'],status='completed',stage='Documentario completato',progress=100,result={'sha256':'old'})
    response=client.post('/api/projects/'+original['id']+'/regenerate',json={
        'topic':'Biografia aggiornata di Napoleone','minutes':12,'notes':'Segui soprattutto gli anni italiani',
        'source_urls':['https://museum.example/napoleone'],'documentary_type':'biography','start':False,
        'use_media':False,'review_visuals':True,'use_documents':False,'document_ids':[],
        'tts_engine':'kokoro','tts_profile_id':'','tts_reference_id':''})
    assert response.status_code==200,response.text
    changed=response.json()['project']
    assert response.json()['mode']=='new_version' and changed['version']==2 and changed['parent_id']==original['id']
    assert changed['topic']=='Biografia aggiornata di Napoleone' and changed['minutes']==12
    assert changed['notes']=='Segui soprattutto gli anni italiani' and changed['source_urls']==['https://museum.example/napoleone']
    assert changed['documentary_type']=='biography' and changed['review_visuals']==1 and changed['use_documents']==0
    assert changed['use_media']==1 and store.project(original['id'])['notes']=='Prima versione'

def test_processing_time_accumulates_across_resumes(client):
    project=client.post('/api/projects',json={'topic':'Cronometro di prova','start':False}).json();pid=project['id']
    store.begin_processing(pid,'2026-09-04T10:00:00+00:00')
    assert store.pause_processing(pid,'2026-09-04T10:00:30+00:00')==30
    store.begin_processing(pid,'2026-09-04T10:01:00+00:00')
    assert store.pause_processing(pid,'2026-09-04T10:01:25+00:00')==55
    saved=store.project(pid)
    assert saved['processing_started']=='' and saved['processing_seconds']==55

def test_failed_regeneration_restarts_same_project_and_archives_attempt(client):
    project=client.post('/api/projects',json={'topic':'Progetto da correggere','start':False}).json();pid=project['id']
    store.update(pid,status='failed',stage='Voce italiana',progress=55,error='errore precedente',result={'partial':True},processing_seconds=123)
    checkpoint=server.JOBS/pid/'checkpoints/research.done.json';checkpoint.parent.mkdir();checkpoint.write_text('{}')
    workspace=server.JOBS/pid/'workspace/partial.txt';workspace.parent.mkdir();workspace.write_text('tentativo precedente')
    store.event(pid,'Vecchio errore','error')
    rejected=client.post('/api/projects/'+pid+'/regenerate',json={
        'topic':'Progetto da correggere','start':False,'use_documents':True,'document_ids':['0'*24]})
    assert rejected.status_code==404
    assert store.project(pid)['status']=='failed' and checkpoint.is_file() and workspace.is_file()
    assert [x['message'] for x in store.events(pid)]==['Vecchio errore']
    response=client.post('/api/projects/'+pid+'/regenerate')
    assert response.status_code==200 and response.json()['mode']=='restart' and response.json()['project']['id']==pid
    restarted=store.project(pid);assert restarted['status']=='draft' and restarted['progress']==0 and restarted['result']=={} and not restarted['error']
    assert restarted['processing_started']=='' and restarted['processing_seconds']==0
    attempt=next((server.JOBS/pid/'attempts').iterdir())
    assert (attempt/'checkpoints/research.done.json').is_file() and (attempt/'workspace/partial.txt').read_text()=='tentativo precedente'
    assert [x['message'] for x in store.events(pid)]==['Rigenerazione da zero richiesta. Il tentativo precedente è stato archiviato.']

def test_delete_project_removes_inactive_record_and_files_but_rejects_active(client):
    removable=client.post('/api/projects',json={'topic':'Progetto eliminabile','start':False}).json();folder=server.JOBS/removable['id']
    (folder/'temporary.txt').write_text('private')
    response=client.delete('/api/projects/'+removable['id'])
    assert response.status_code==200 and response.json()['deleted'] and not folder.exists()
    assert client.get('/api/projects/'+removable['id']).status_code==404
    active=client.post('/api/projects',json={'topic':'Progetto in corso','start':False}).json();store.update(active['id'],status='running')
    assert client.delete('/api/projects/'+active['id']).status_code==409
    assert client.post('/api/projects/'+active['id']+'/regenerate').status_code==409
def test_file_routes_reject_traversal(client):
    p=client.post("/api/projects",json={"topic":"Battaglia di prova","start":False}).json()
    assert client.get("/api/projects/"+p["id"]+"/file",params={"path":"../../settings.json"}).status_code==404
    assert client.get("/api/projects/"+p["id"]+"/preview",params={"path":"../settings.json"}).status_code==404
def test_missing_provider_does_not_start(client):
    p=client.post("/api/projects",json={"topic":"Battaglia di prova","start":False}).json()
    r=client.post("/api/projects/"+p["id"]+"/start")
    assert r.status_code==400 and "Configura" in r.text
def test_json_thinking_and_invalid():
    assert extract_json('<think>reasoning</think>\n```json\n{"ok":true}\n```')=={"ok":True}
    with pytest.raises(ModelError):extract_json("No JSON")

def test_provider_error_is_safe_and_400_retries_once():
    class Response:
        status_code=400
        def json(self):return {'error':{'message':'backend busy; Bearer private-token','type':'server_busy'}}
    assert provider_error(Response(),'private-token')=='backend busy; Bearer [chiave rimossa] · server_busy'
    class Session:
        def __init__(self):self.calls=[]
        def post(self,*args,**kwargs):
            self.calls.append(copy.deepcopy(kwargs['json']))
            if len(self.calls)==1:return Response()
            return type('Ok',(),{'status_code':200,'json':lambda self:{'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]}})()
    llm=LLM(Settings(model='fixture',api_key='private-token',reasoning_mode='off').model_dump());llm.session=Session()
    assert extract_json(llm.chat([{'role':'user','content':'test'}]))=={'ok':True}
    assert len(llm.session.calls)==2

def test_lmstudio_loads_the_configured_model_when_memory_is_empty():
    class Response:
        def __init__(self,status,data):self.status_code=status;self.data=data
        def json(self):return self.data
    class Session:
        def __init__(self):self.calls=[];self.chat_calls=0
        def post(self,url,**kwargs):
            self.calls.append((url,copy.deepcopy(kwargs['json'])))
            if url.endswith('/api/v1/models/load'):
                return Response(200,{'status':'loaded','model_instance_id':'fixture'})
            self.chat_calls+=1
            if self.chat_calls==1:return Response(400,{'error':{'message':'No models loaded. Please load a model.','type':'invalid_request_error','param':'model'}})
            return Response(200,{'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]})
    config=Settings(provider='lmstudio',base_url='http://localhost:1234/v1',model='google/gemma-fixture',context_length=65536,reasoning_mode='off').model_dump()
    llm=LLM(config);llm.session=Session()
    assert extract_json(llm.chat([{'role':'user','content':'test'}]))=={'ok':True}
    load=next(call for call in llm.session.calls if call[0].endswith('/api/v1/models/load'))
    assert load==('http://localhost:1234/api/v1/models/load',{'model':'google/gemma-fixture','context_length':65536})
def test_visual_review_blocks_only_specific_severe_defects():
    assert runner.visual_blockers({'acceptable':False,'issues':['Nella terza mappa le etichette sono sovrapposte.']})
    assert runner.visual_blockers({'acceptable':False,'issues':['La scena 4 è corrotta.']})
    assert runner.visual_blockers({'acceptable':False,'issues':['Bassa definizione generale e contrasto migliorabile.']})==[]
def test_structured_recovers_values_from_schema_echo():
    llm=LLM(Settings(model='fixture').model_dump())
    llm.chat=lambda *args,**kwargs: json.dumps({'properties':{
        'acceptable':True,'issues':[],'source_ids':['S1'],'summary':'Controllo completato.'
    },'required':['acceptable','summary'],'title':'Review','type':'object'})
    result=llm.structured('system','review',Review)
    assert result=={'acceptable':True,'issues':[],'source_ids':['S1'],'summary':'Controllo completato.'}
def test_public_research_refuses_internal():
    from app.research import public_url
    for url in ["http://127.0.0.1/private","http://169.254.169.254/latest","file:///C:/Windows","http://10.0.0.1"]:
        with pytest.raises(ValueError):public_url(url)
def test_restart_marks_running_interrupted():
    p=store.create(ProjectRequest(topic="Battaglia di prova"))
    store.update(p["id"],status="running");store.init()
    assert store.project(p["id"])["status"]=="interrupted"
def test_pipeline_snapshot_is_separate(tmp_path):
    src=tmp_path/"original";src.mkdir()
    for name in ["documentary.py","engine/common.py","engine/atlas.py",".venv/Scripts/python.exe",
       "assets/voice/kokoro/kokoro-v1.0.onnx","assets/voice/kokoro/voices-v1.0.bin"]:
        p=src/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text("original")
    (src/"tools").mkdir()
    work,python=pipeline.isolate("example",src)
    (work/"engine/common.py").write_text("changed in isolated copy")
    assert(src/"engine/common.py").read_text()=="original"
    assert not(src/"output").exists()
def test_real_http_compatible_contract():
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def do_GET(self):
            assert self.path=="/v1/models";self.send_response(200);self.end_headers();self.wfile.write(b'{"data":[{"id":"test-model"}]}')
        def do_POST(self):
            payload=json.loads(self.rfile.read(int(self.headers["Content-Length"])));calls.append((self.path,self.headers.get("Authorization"),payload))
            self.send_response(200);self.send_header("Content-Type","application/json");self.end_headers()
            self.wfile.write(json.dumps({"choices":[{"finish_reason":"stop","message":{"content":'{"ok":true}'}}]}).encode())
    http=ThreadingHTTPServer(("127.0.0.1",0),Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    try:
        c=Settings(base_url=f"http://127.0.0.1:{http.server_port}/v1",model="test-model",api_key="fixture",json_mode=True,reasoning_mode='off').model_dump()
        llm=LLM(c);assert llm.models()==["test-model"]
        assert extract_json(llm.chat([{"role":"user","content":"test"}]))=={"ok":True}
        schema={'title':'Fixture','type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok']}
        assert llm.structured('system','test',schema)=={'ok':True}
        assert calls[0][0]=="/v1/chat/completions" and calls[0][1]=="Bearer fixture"
        assert calls[0][2]["response_format"]=={"type":"json_object"} and calls[0][2]["stream"] is False
        assert calls[0][2]['reasoning_effort']=='none'
        assert calls[1][2]['response_format']['type']=='json_schema'
        assert calls[1][2]['response_format']['json_schema']['schema']==schema
    finally:http.shutdown();http.server_close()

def test_cancel_stops_owned_local_process(tmp_path):
    import sys,time
    flag=threading.Event();outcome=[]
    def check():
        if flag.is_set():raise pipeline.Cancelled()
    def worker():
        try:pipeline.run("cancel-fixture",sys.executable,tmp_path,["-c","import time; print('ready',flush=True); time.sleep(30)"],check,lambda _:None)
        except pipeline.Cancelled:outcome.append("cancelled")
    t=threading.Thread(target=worker);t.start()
    deadline=time.monotonic()+5
    while "cancel-fixture" not in pipeline.PROCESSES and time.monotonic()<deadline:time.sleep(.02)
    assert "cancel-fixture" in pipeline.PROCESSES
    flag.set();t.join(timeout=12)
    assert not t.is_alive() and outcome==["cancelled"]
    assert "cancel-fixture" not in pipeline.PROCESSES
