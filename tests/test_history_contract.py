"""Regression coverage for compiled plans entering the unchanged battle renderer."""
import copy,json,sys,threading
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/'pipeline'
sys.path.insert(0,str(CORE))
from engine.common import validate_pack
from engine.history_contract import normalize_document
from engine.history_schema import validate_document


def old_general_pack():
    doc=json.loads((CORE/'documentaries/rinascimento/documentary.json').read_text(encoding='utf-8'))
    for s in doc['scenes']:s['focus']=list(s.get('location_ids',[]))
    return doc


def test_old_general_focus_preserves_all_editorial_and_geographic_content():
    old=old_general_pack();original=copy.deepcopy(old)
    repaired=normalize_document(old)
    assert old==original  # Do not mutate the caller's saved plan.
    expected=copy.deepcopy(old)
    for s in expected['scenes']:s['focus']=[]
    assert repaired==expected
    legacy=validate_pack(old)
    assert all(s['focus']==[] for s in legacy['scenes'])
    assert [s.get('location_ids',[]) for s in legacy['scenes']]==[s['focus'] for s in old['scenes']]
    assert normalize_document(repaired)==repaired


def test_place_only_focus_is_migrated_and_legacy_cue_objects_are_preserved():
    doc=old_general_pack();scene=doc['scenes'][0]
    ids=scene.pop('location_ids')
    assert normalize_document(doc)['scenes'][0]['location_ids']==ids
    scene['location_ids']=ids;scene['focus']=[{'cue':0,'place':ids[0]}]
    assert normalize_document(doc)['scenes'][0]['focus']==scene['focus']
    assert validate_pack(doc)['scenes'][0]['focus']==scene['focus']


@pytest.mark.parametrize('broken',[
    ['unknown-place'],['firenze',{'cue':0,'place':'firenze'}],{'place':'firenze'},
])
def test_ambiguous_focus_is_rejected_without_discarding_content(broken):
    doc=old_general_pack();doc['scenes'][0]['focus']=broken
    with pytest.raises(ValueError,match='focus'):normalize_document(doc)


def test_conflicting_place_fields_require_correction():
    doc=old_general_pack();doc['scenes'][0]['location_ids']=[]
    with pytest.raises(ValueError,match='luoghi diversi'):normalize_document(doc)


@pytest.mark.parametrize('field',['arrows','commanders','sfx','routes','units'])
def test_other_malformed_effect_lists_fail_with_useful_error(field):
    doc=old_general_pack();doc['scenes'][0][field]=['not-an-effect']
    with pytest.raises(ValueError,match=field+' deve contenere oggetti'):validate_document(doc)


def test_cue_bounds_and_legacy_battle_compatibility():
    doc=old_general_pack();s=doc['scenes'][0]
    s['focus']=[{'cue':len(s['lines']),'place':s['location_ids'][0]}]
    with pytest.raises(ValueError,match='cue non valido'):validate_document(doc)
    battle=json.loads((CORE/'battles/waterloo/battle.json').read_text(encoding='utf-8'))
    original=copy.deepcopy(battle)
    assert normalize_document(battle) is battle
    assert validate_pack(battle)==original


def test_all_shipped_general_examples_pass_full_cli_contract():
    for path in (CORE/'documentaries').glob('*/documentary.json'):
        pack=json.loads(path.read_text(encoding='utf-8'))
        assert validate_pack(pack)['documentary_schema_version']==2,path


def test_saved_pack_repair_is_scoped_backed_up_and_idempotent(tmp_path):
    from app.pack_migrations import repair_pack
    from app.store import write_json,read_json
    work=tmp_path/'workspace';path=work/'battles/film/battle.json'
    write_json(path,old_general_pack());original=path.read_bytes();messages=[]
    assert repair_pack(path,work,messages.append)
    assert list(path.parent.glob('battle.before-focus-fix-*.json'))[0].read_bytes()==original
    assert validate_pack(read_json(path))['documentary_schema_version']==2
    repaired=path.read_bytes()
    assert not repair_pack(path,work,messages.append)
    assert path.read_bytes()==repaired and len(messages)==1
    with pytest.raises(ValueError,match='soltanto nel workspace'):repair_pack(path,tmp_path/'other')
    battle=work/'battles/old/battle.json'
    write_json(battle,{'schema_version':1,'scenes':[{'focus':[{'cue':0,'place':'a'}]}]})
    original=battle.read_bytes()
    assert not repair_pack(battle,work) and battle.read_bytes()==original


def test_resume_reuses_editorial_checkpoints_and_maps_then_reaches_assets(tmp_path,monkeypatch):
    """Real repair and pack validation; model/downloads forbidden, stop at assets."""
    from app import store,runner,pipeline
    from app.models import ProjectRequest,Settings
    from app.research import assessment
    jobs=tmp_path/'jobs';jobs.mkdir()
    for module in (store,runner,pipeline):
        if hasattr(module,'DATA'):monkeypatch.setattr(module,'DATA',tmp_path)
        if hasattr(module,'JOBS'):monkeypatch.setattr(module,'JOBS',jobs)
    store.init();p=store.create(ProjectRequest(topic='Rinascimento',start=False,documentary_type='cultural_movement'))
    work=jobs/p['id']/'workspace';cp=jobs/p['id']/'checkpoints'
    pack=old_general_pack();pack['slug']='film-'+p['id']
    path=work/'battles'/pack['slug']/'battle.json';store.write_json(path,pack)
    geo=path.with_name('geography.json');store.write_json(geo,{'output':'assets/geography/atlas-film'})
    atlas=work/'assets/geography/atlas-film/saved-raster.bin';atlas.parent.mkdir(parents=True);atlas.write_bytes(b'immutable raster fixture')
    sources=[{**s,'text':'Recorded evidence fixture.'} for s in pack['sources']]
    store.write_json(cp/'sources.json',sources);store.write_json(cp/'research.json',assessment(sources,'strict'))
    store.write_json(cp/'outline.json',{'documentary_type':'cultural_movement','scenes':pack['scenes']})
    store.write_json(cp/'narration.json',[{'index':i,'lines':s['lines']} for i,s in enumerate(pack['scenes'])])
    store.write_json(cp/'review.json',{'acceptable':True,'summary':'Saved review fixture.'})
    for key in ['research','outline','narration','review','geography']:store.write_json(cp/(key+'.done.json'),{'completed':'saved fixture'})
    preserved={p:p.read_bytes() for p in [*cp.iterdir(),geo,atlas]}
    class NoModel:
        calls=0
        def __init__(self,*a):pass
        def structured(self,*a,**k):raise AssertionError('Completed editorial work must not call the model again')
    def forbidden(*a,**k):raise AssertionError('Completed maps and source collection must be reused')
    monkeypatch.setattr(runner,'LLM',NoModel);monkeypatch.setattr(runner,'collect',forbidden)
    monkeypatch.setattr(runner,'reuse_atlas',forbidden)
    monkeypatch.setattr(runner,'prepare_hybrid_engine',forbidden)
    monkeypatch.setattr(runner,'isolate',lambda *a:(work,Path('python')))
    commands=[]
    def run(pid,python,folder,args,*a,**k):
        assert args[0]=='documentary.py'
        commands.append(args[1])
        validate_pack(store.read_json(path))
        if args[1]=='assets':raise pipeline.Cancelled()
    monkeypatch.setattr(runner,'run',run)
    runner.FLAGS[p['id']]=threading.Event()
    runner.produce(p['id'],Settings(model='FORBIDDEN_TEST_MODEL',pipeline_path=str(CORE)).model_dump())
    assert store.project(p['id'])['status']=='cancelled',store.project(p['id'])['error']
    assert commands==['validate','assets']
    assert all(p.read_bytes()==content for p,content in preserved.items())
    assert store.read_json(path)==normalize_document(pack)
    assert list(path.parent.glob('battle.before-focus-fix-*.json'))
