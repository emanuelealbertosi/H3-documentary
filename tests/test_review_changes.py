"""Human review reaches the existing renderer without changing unrelated history."""
import copy
import json
from pathlib import Path

import pytest

from app import store,runner,review_editor
from app.models import ProjectRequest
from app.review_changes import transform,commit

ROOT=Path(__file__).resolve().parents[1]


def general_pack():
    return json.loads((ROOT/'pipeline/documentaries/rinascimento/documentary.json').read_text(encoding='utf-8'))


def draft(scenes=None,places=None):
    return {'revision':'a'*64,'scenes':scenes or [],'places':places or []}


def test_text_edits_keep_history_assets_cue_count_and_sync_destination():
    pack=general_pack();scene=pack['scenes'][0];place=pack['locations'][0]
    scene['movements']=[{'from':place['id'],'to':place['id'],'points':[place['pos'],place['pos']],
                         'semantic':'cultural_diffusion','cue':0,'sources':[pack['sources'][0]['id']]}]
    original=copy.deepcopy(pack)
    text=['Prima frase riscritta.','Ora raccontiamo '+place['name']+'.',*scene['lines'][2:]]
    edited,geo,plan,speech,report=transform(pack,{}, {},[{'index':0,'lines':scene['lines']}],draft([{'id':scene['id'],'lines':text}]))
    assert pack==original and geo=={} and plan=={}
    assert edited['scenes'][0]['lines']==text and speech[0]['lines']==text
    assert edited['scenes'][0]['movements'][0]['cue']==1
    assert edited['metadata']['manual_narration'] is True and report['narration_modified']
    for field in ('locations','sources','persons','visual_layers','visual_assets'):
        assert edited.get(field)==pack.get(field)
    assert edited['scenes'][1:]==pack['scenes'][1:]


def test_named_route_ends_and_cameras_follow_pin_not_sourced_territories():
    pack=general_pack();place=pack['locations'][0];other=pack['locations'][1]
    scene=pack['scenes'][0];scene['location_ids']=[place['id'],other['id']]
    scene['movements']=[{'from':place['id'],'to':other['id'],'points':[place['pos'],[12,44],other['pos']],
                         'semantic':'cultural_diffusion','cue':0,'sources':[pack['sources'][0]['id']]}]
    plan={'places':copy.deepcopy(pack['locations']),'scenes':[copy.deepcopy(scene)]}
    original=copy.deepcopy(pack);new=[place['pos'][0]+.3,place['pos'][1]+.25]
    edited,geo,outline,_,report=transform(pack,{'output':'assets/geography/custom'},plan,[],draft(places=[{'id':place['id'],'pos':new}]))
    assert pack==original
    assert edited['locations'][0]['pos']==new and outline['places'][0]['pos']==new
    assert edited['scenes'][0]['movements'][0]['points']==[new,[12,44],other['pos']]
    assert outline['scenes'][0]['movements'][0]['points'][0]==new
    assert edited.get('visual_layers')==pack.get('visual_layers')
    assert geo['output']=='assets/geography/custom' and geo['bounds'][0]<new[0]<geo['bounds'][2]
    assert scene['id'] in report['map_scene_ids'] and report['place_ids']==[place['id']]
    for scene in edited['scenes']:
        assert scene['camera_end'][2]>0


def test_battle_routes_arrows_units_share_corrected_geographic_endpoint():
    from app.compiler import compile_pack
    outline={'title':'Battaglia di prova','short_title':'Prova','description':'Fixture','display_date':'1815',
             'factions':['A','B'],'places':[{'id':'a','name':'Porto A','pos':[11,43]},{'id':'b','name':'Porto B','pos':[12,44]}],
             'commanders':[],'scenes':[{'title':f'Scena {i}','date':'1815','focus':['a','b'],'event':'Evento',
              'source_ids':['S1'],'routes':[{'points':[[11,43],[11.4,43.3],[12,44]]}]} for i in range(3)]}
    narration=[{'index':i,'lines':['Parola '*57,'Storia '*57],'fact':'Dato di prova','kicker':'Prova'} for i in range(3)]
    pack,geo=compile_pack(outline,narration,[{'id':'S1','title':'Fonte','url':'https://example.test','retrieved':'2026-09-05'}],
                          {'id':'test','minutes':2},{'fps':24})
    before=copy.deepcopy(pack);new=[12.3,44.2]
    edited,_,_,_,report=transform(pack,geo,outline,narration,draft(places=[{'id':'b','pos':new}]))
    for scene in edited['scenes']:
        assert scene['routes'][0]['points'][-1]==scene['arrows'][0]['points'][-1]==scene['units'][0]['path'][-1]==new
    assert edited['places']['b']['pos']==new and edited['sources']==pack['sources']
    assert pack==before and report['geography_modified'] and not report['narration_modified']


def test_shared_coordinates_only_move_explicit_named_endpoint():
    from app.review_changes import _routes
    shared=[12,43];destination=[13,44]
    scene={'movements':[{'to':'a','points':[[10,41],shared]},
                         {'to':'b','points':[[10,41],shared]},
                         {'points':[[10,41],shared]}],
           'units':[{'pos':shared}]}
    _routes(scene,{'a':(shared,destination)},{tuple(shared)})
    assert scene['movements'][0]['points'][-1]==destination
    assert scene['movements'][1]['points'][-1]==scene['movements'][2]['points'][-1]==shared
    assert scene['units'][0]['pos']==shared


def test_static_camera_keyframes_reach_corrected_pin():
    pack=general_pack();scene=pack['scenes'][0];place=pack['locations'][0]
    view=[*place['pos'],6]
    scene.update(location_ids=[place['id']],camera_start=view,camera_end=view,
                 camera_keys=[{'at':0,'view':view},{'at':.42,'view':view},{'at':1,'view':view}])
    new=[place['pos'][0]+2,place['pos'][1]+1]
    edited,*_=transform(pack,{}, {},[],draft(places=[{'id':place['id'],'pos':new}]))
    result=edited['scenes'][0]
    assert result['camera_keys'][0]['view']==result['camera_start']
    assert result['camera_keys'][-1]['view']==result['camera_end']
    assert result['camera_end'][:2]==pytest.approx(new)


@pytest.fixture
def project(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);monkeypatch.setattr(store,'JOBS',tmp_path/'jobs')
    monkeypatch.setattr(runner,'JOBS',tmp_path/'jobs');(tmp_path/'jobs').mkdir();store.init()
    monkeypatch.setattr(runner,'active',lambda *a:False)
    p=store.create(ProjectRequest(topic='Revisione di prova',review_visuals=True,start=False))
    store.update(p['id'],status='review')
    work=store.JOBS/p['id']/'workspace';path=work/'battles/test/battle.json';pack=general_pack()
    store.write_json(path,pack);store.write_json(path.with_name('geography.json'),{})
    cp=store.JOBS/p['id']/'checkpoints'
    for name in ('research','outline','narration','review','geography','assets','voice','preview','render','finalize','verify'):
        store.write_json(cp/(name+'.done.json'),{'completed':'original'})
    store.write_json(cp/'outline.json',{'places':copy.deepcopy(pack['locations']),'scenes':[]})
    store.write_json(cp/'narration.json',[{'index':i,'lines':s['lines']} for i,s in enumerate(pack['scenes'])])
    store.write_json(work/'timeline.json',{'estimated':True});store.write_json(work/'build'/pack['slug']/'timeline.json',{'estimated':True})
    return p['id'],work,path,cp


def save_text(pid,pack,text):
    initial=review_editor.get_review(pid)
    return review_editor.put_review(pid,review_editor.EditorialEdit(revision=initial['revision'],
            scenes=[{'id':pack['scenes'][0]['id'],'lines':[text,*pack['scenes'][0]['lines'][1:]]}]))


def test_apply_persists_review_and_only_invalidates_derived_stages(project,monkeypatch):
    pid,work,path,cp=project;pack=store.read_json(path)
    save_text(pid,pack,'Testo corretto dall’utente.')
    pending=review_editor.pending(pid,pack)
    edited,geo,outline,narration,report=transform(pack,{},store.read_json(cp/'outline.json'),store.read_json(cp/'narration.json'),pending)
    commit(pid,path,edited,geo,outline,narration,report)
    assert store.read_json(path)['scenes'][0]['lines'][0]=='Testo corretto dall’utente.'
    assert store.read_json(cp/'narration.json')[0]['lines'][0]=='Testo corretto dall’utente.'
    for name in ('research','outline','narration','review','geography','assets'):
        assert (cp/(name+'.done.json')).exists()
    for name in ('voice','preview','render','finalize','verify'):
        assert not (cp/(name+'.done.json')).exists()
    assert not (work/'timeline.json').exists() and not (work/'build'/pack['slug']/'timeline.json').exists()
    assert not (cp/'editorial-review.json').exists()
    assert list((cp/'editorial-review-backups').rglob('battle.json'))
    assert list((cp/'editorial-review-applied').glob('*.json'))


def test_failed_write_rolls_back_pack_checkpoints_and_keeps_draft(project,monkeypatch):
    pid,work,path,cp=project;pack=store.read_json(path);save_text(pid,pack,'Nuove parole.')
    edited,geo,outline,narration,report=transform(pack,{},store.read_json(cp/'outline.json'),store.read_json(cp/'narration.json'),review_editor.pending(pid,pack))
    snapshot={file:file.read_bytes() for file in [path,cp/'narration.json',cp/'outline.json',work/'timeline.json',cp/'voice.done.json',cp/'editorial-review.json']}
    original_write=store.write_json
    def broken(file,value):
        if Path(file)==cp/'narration.json':raise OSError('Disco non disponibile')
        return original_write(file,value)
    monkeypatch.setattr(store,'write_json',broken)
    with pytest.raises(OSError,match='Disco'):commit(pid,path,edited,geo,outline,narration,report)
    assert all(file.read_bytes()==data for file,data in snapshot.items())


def test_continue_applies_text_before_resume_without_llm_or_tts(project,monkeypatch):
    pid,work,path,cp=project;pack=store.read_json(path);save_text(pid,pack,'Narrazione rivista a mano.')
    monkeypatch.setattr(runner.media,'catalog',lambda:[])
    monkeypatch.setattr(runner.visual_slots,'materialize',lambda *a,**k:[])
    resumed=[];monkeypatch.setattr(runner,'enqueue',resumed.append)
    runner.approve_visual_review(pid)
    assert resumed==[pid]
    assert store.read_json(path)['scenes'][0]['lines'][0]=='Narrazione rivista a mano.'
    assert store.read_json(cp/'visual-review.approved.json')['editorial']['narration_modified']
