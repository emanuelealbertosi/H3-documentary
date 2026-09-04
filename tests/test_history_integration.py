import json,copy,sys,sqlite3
from pathlib import Path
import pytest
from app import store
from app.models import ProjectRequest
from app.general import HistoryOutline,history_tools
CORE=Path(__file__).resolve().parents[1]/"pipeline"

def test_shared_compiler_real_editorial_example():
    detect,prompt,compile=history_tools(str(CORE))
    d=json.loads((CORE/"documentaries/rinascimento/documentary.json").read_text(encoding="utf-8"))
    outline={k:copy.deepcopy(d.get(k,[])) for k in ['persons','entities','events','visual_layers','visual_assets','historical_period']}
    outline.update(documentary_type='cultural_movement',title=d['title'],short_title=d['short_title'],description=d['title'],display_date='1400–1550',analysis={'period':'Quattrocento e Cinquecento'},uncertainties=d['editorial_notes'])
    outline['places']=[{k:p[k] for k in ['id','name','pos']} for p in d['locations']]
    outline['scenes']=[{**s,'focus':s.get('location_ids',[]),'event':s['facts'][0],'source_ids':s['sources']} for s in d['scenes']]
    outline=HistoryOutline.model_validate(outline).model_dump()
    narration=[dict(index=i,lines=s['lines'],fact=s['facts'][0],kicker=s['kicker']) for i,s in enumerate(d['scenes'])]
    pack,geo=compile(outline,narration,d['sources'],{'id':'history-test','minutes':7},{'fps':24})
    assert pack['schema_version']==2 and pack['documentary_type']=='cultural_movement'
    assert {'artwork','person_intro','comparison','network_map'} <= {s['scene_type'] for s in pack['scenes']}
    assert all('sources' in s for s in pack['scenes'])
    assert geo['output']=='assets/geography/atlas-film'
    assert all(a['path'].startswith('assets/history/film-history-test/') for a in pack['visual_assets'])
    # Validate the actual CLI boundary, not just the general authoring schema.
    from engine.common import validate_pack
    legacy=validate_pack(pack)
    assert all(isinstance(f,dict) for s in legacy['scenes'] for f in s['focus'])
    assert all(s['location_ids']==o['focus'] for s,o in zip(pack['scenes'],outline['scenes']))

def test_type_and_source_guard():
    from engine.history_schema import validate_document
    d=json.loads((CORE/'documentaries/via-della-seta/documentary.json').read_text(encoding='utf-8'))
    d['scenes'][0]['network']['edges'][0]['to']='nonexistent'
    with pytest.raises(ValueError):validate_document(d)
    assert ProjectRequest(topic='Diffusione del Rinascimento').documentary_type=='auto'
    assert ProjectRequest(topic='Storia del Rinascimento',documentary_type='cultural_movement').documentary_type=='cultural_movement'
    with pytest.raises(ValueError):ProjectRequest(topic='Qualunque storia',documentary_type='arbitrary-code')

def test_old_database_migration(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);jobs=tmp_path/'jobs';jobs.mkdir();monkeypatch.setattr(store,'JOBS',jobs)
    with sqlite3.connect(tmp_path/'studio.db') as c:
        c.execute("CREATE TABLE projects(id TEXT PRIMARY KEY,topic TEXT,minutes INTEGER,notes TEXT,source_urls TEXT,status TEXT,stage TEXT,progress REAL DEFAULT 0,created TEXT,updated TEXT,error TEXT DEFAULT '',result TEXT DEFAULT '{}')")
        c.execute("INSERT INTO projects(id,topic,minutes,notes,source_urls,status,stage,created,updated) VALUES ('old','Waterloo',10,'','[]','draft','','','')")
        c.execute("INSERT INTO projects(id,topic,minutes,notes,source_urls,status,stage,created,updated) VALUES ('finished','Roma',5,'','[]','completed','Documentario completato','2026-01-01T10:00:00+00:00','2026-01-01T10:02:00+00:00')")
        c.execute("CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT,at TEXT,level TEXT,message TEXT)")
        c.execute("INSERT INTO events(project_id,at,level,message) VALUES ('finished','2026-01-01T10:00:00+00:00','info','Avvio'),('finished','2026-01-01T10:02:00+00:00','info','Fine')")
    store.init()
    assert store.project('old')['documentary_type']=='battle'
    assert store.project('old')['use_media']==0
    assert store.project('old')['processing_started']==''
    assert store.project('old')['processing_seconds']==0
    assert 119.9<store.project('finished')['processing_seconds']<120.1
    new=store.create(ProjectRequest(topic='Rinascimento',start=False))
    assert new['documentary_type']=='auto'


def test_generic_runner_dispatch_with_explicit_stubs(tmp_path,monkeypatch):
    """Tests orchestration only: stub research/model/commands, no claim of rendered media."""
    import threading
    from app import runner,pipeline
    from app.models import Settings
    detect,prompt,compile=history_tools(str(CORE))
    d=json.loads((CORE/'documentaries/rinascimento/documentary.json').read_text(encoding='utf-8'))
    outline={k:copy.deepcopy(d.get(k,[])) for k in ['persons','entities','events','visual_layers','visual_assets','historical_period']}
    outline.update(documentary_type='cultural_movement',title=d['title'],short_title=d['short_title'],description=d['title'],display_date='1400–1550',analysis={},uncertainties=[])
    outline['places']=[{k:p[k] for k in ['id','name','pos']} for p in d['locations']]
    outline['scenes']=[{**s,'focus':s.get('location_ids',[]),'event':s['facts'][0],'source_ids':s['sources']} for s in d['scenes'][:3]]
    narration=[dict(index=i,lines=s['lines'],fact=s['facts'][0],kicker=s['kicker']) for i,s in enumerate(d['scenes'][:3])]
    narration[0]['lines'][0]+=' Questa frase serve soltanto alla prova tecnica del flusso.'
    sources=[{**s,'text':'Explicit test evidence fixture.','retrieved':store.now()} for s in d['sources']]
    class Model:
        calls=0
        def __init__(self,*a,**k):pass
        def structured(self,system,prompt,schema):
            self.calls+=1
            if schema.__name__=='HistoryOutline':return copy.deepcopy(outline)
            if schema.__name__=='NarrationBatch':return {'scenes':copy.deepcopy(narration)}
            if schema.__name__=='Review':return {'acceptable':True,'issues':[],'source_ids':['R1'],'summary':'Test fixture only.'}
            raise AssertionError('The generic job must not request a battle outline')
    jobs=tmp_path/'jobs';jobs.mkdir()
    for module in [store,runner,pipeline]:
        if hasattr(module,'DATA'):monkeypatch.setattr(module,'DATA',tmp_path)
        if hasattr(module,'JOBS'):monkeypatch.setattr(module,'JOBS',jobs)
    store.init()
    project=store.create(ProjectRequest(topic='Rinascimento europeo',minutes=2,start=False))
    work=jobs/project['id']/'workspace';work.mkdir()
    monkeypatch.setattr(runner,'isolate',lambda *a:(work,Path('python')))
    monkeypatch.setattr(runner,'LLM',Model);monkeypatch.setattr(runner,'collect',lambda *a,**k:sources)
    monkeypatch.setattr(runner,'build_history_outline',lambda *a,**k:copy.deepcopy(outline))
    monkeypatch.setattr(runner,'reuse_atlas',lambda *a:True)
    commands=[]
    def command(pid,python,folder,args,*a,**k):
        commands.append(args)
        if args[0]=='documentary.py' and args[1]=='verify':
            target=work/'output'/('film-'+pid+'_verification')/'report.json'
            store.write_json(target,{'video_duration':120,'bytes':0,'sha256':'STUB_NOT_A_VIDEO'})
    monkeypatch.setattr(runner,'run',command)
    runner.FLAGS[project['id']]=threading.Event()
    runner.produce(project['id'],Settings(model='TEST_STUB',pipeline_path=str(CORE),fps=24).model_dump())
    result=store.project(project['id'])
    assert result['status']=='completed',result['error']
    assert any(c[0]=='tools/history_layout.py' for c in commands)
    assert any(c[0]=='tools/check_history_final.py' for c in commands)
    pack=store.read_json(next((work/'battles').glob('*/battle.json')))
    assert pack['schema_version']==2 and pack['documentary_type']=='cultural_movement'
    assert 'factions' not in pack
