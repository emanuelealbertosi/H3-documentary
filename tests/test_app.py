import os,json,threading,copy
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import pytest
os.environ.setdefault("DOCUMENTARIAI_DATA",str(Path(__file__).parent/"output/state"))
from app import store,server,pipeline,runner
from app.models import Settings,ProjectRequest,Outline
from app.llm import LLM,extract_json,ModelError
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
    shell=client.get('/admin')
    assert shell.status_code==200 and shell.headers['cache-control']=='no-cache'
    assert '/static/app.js?v=1.1.8' in shell.text
    frontend=client.get('/static/app.js?v=1.1.8')
    assert frontend.headers['cache-control']=='no-cache'
    assert frontend.text.index("select('reasoning_mode','Reasoning del modello'") < frontend.text.index("'<details><summary>Parametri del modello")
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
