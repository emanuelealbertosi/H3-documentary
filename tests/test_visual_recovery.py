"""Replay complete archived responses offline; historical assertions are not fixtures' purpose."""
import copy,json
from pathlib import Path
import pytest
from app.general import history_tools
from app.llm import LLM,ModelError
from app.models import Settings
from app.outline_builder import build_history_outline,HistorySceneBatch
from app.outline_normalization import movement_endpoints
from app.research import assessment
from app.visual_recovery import normalize_inline_visuals,recover_visuals,strip_model_recovery

CORE=Path(__file__).resolve().parents[1]/'pipeline'
ARCHIVE=json.loads((Path(__file__).parent/'fixtures/visual_recovery_indo_european.json').read_text(encoding='utf-8'))


def test_historical_review_sees_real_plan_not_rejected_visual_proposals():
    from app.visual_recovery import reviewable_outline
    audit={'placeholder':True,'omitted_items':[{'data':'REJECTED_DESTINATION'}]}
    original={'title':'Titolo conservato','visual_warnings':[audit],
              'metadata':{'visual_warnings':[audit],'author':'invariato'},
              'scenes':[{'event':'Evento conservato','source_ids':['S1'],'movements':[],'visual_recovery':audit}]}
    before=copy.deepcopy(original);result=reviewable_outline(original)
    assert 'REJECTED_DESTINATION' not in json.dumps(result)
    assert result['manual_visual_scene_ids']==['01']
    assert result['scenes'][0]['event']=='Evento conservato' and result['scenes'][0]['source_ids']==['S1']
    assert original==before


def shape(raw):
    batch=HistorySceneBatch.model_validate(raw).model_dump()
    return movement_endpoints(normalize_inline_visuals(strip_model_recovery(batch)),ARCHIVE['catalog']['places'])


@pytest.mark.parametrize('number',[0,1,2])
def test_archived_movement_and_unbound_area_become_reviewable_placeholder(number):
    history_tools(CORE)
    raw=copy.deepcopy(ARCHIVE['batches'][number]);before=copy.deepcopy(raw);catalog=copy.deepcopy(ARCHIVE['catalog'])
    batch=shape(raw);comparison=copy.deepcopy(batch['scenes'][0]);events=copy.deepcopy(batch['events'])
    known={'asset_ids':set(),'territory_ids':{layer['id'] for layer in batch['visual_layers']}}
    reports=recover_visuals(batch,catalog['places'],known,{'version':1,'journey':False},4)
    assert len(reports)==1 and reports[0]['scene_id']=='02'
    scene=batch['scenes'][1]
    assert scene['scene_type']=='event_focus' and scene['visual_recovery']['placeholder']
    assert scene['movements']==[] and scene['territory_ids']==[]
    assert scene['event']==raw['scenes'][1]['event'] and scene['historical_range']==tuple(raw['scenes'][1]['historical_range'])
    assert batch['scenes'][0]==comparison and batch['events']==events
    assert raw==before and catalog==ARCHIVE['catalog']
    assert batch['visual_layers'][0]['id']=='layer_01'  # No guess mapping pontic-steppe to this ID.
    omitted=scene['visual_recovery']['omitted_items']
    assert any(row['element']=='territory_ids' and row['data']==['pontic-steppe'] for row in omitted)
    assert any(row['element'].startswith('movements[') for row in omitted)


def test_keeps_every_valid_route_without_changing_direction_geometry_or_evidence():
    history_tools(CORE);batch=shape(ARCHIVE['batches'][2]);scene=batch['scenes'][1]
    scene['territory_ids']=[];scene['event']='Le migrazioni raggiungono Europa Centrale.'
    valid=copy.deepcopy(scene['movements'][0]);valid.update(cue=1,sources=[],entity_id='population',note='Geometria originale')
    wrong={**copy.deepcopy(valid),'to':'central-asia','points':[[38,45],[73,40]]}
    scene['movements']=[valid,wrong]
    before=copy.deepcopy(valid)
    reports=recover_visuals(batch,ARCHIVE['catalog']['places'],{'asset_ids':set(),'territory_ids':set()},{'journey':False},4)
    assert scene['movements']==[before] and not scene['visual_recovery']['placeholder']
    assert scene['scene_type']=='map_overview' and len(reports)==1
    assert reports[0]['omitted_items'][0]['data']==wrong


def test_inline_declarations_are_lossless_and_conflicts_are_not_guessed():
    batch=HistorySceneBatch.model_validate(ARCHIVE['batches'][0]).model_dump()
    original=copy.deepcopy(batch['scenes'][1]['visual_layers'])
    normalize_inline_visuals(batch)
    assert batch['visual_layers']==original and 'visual_layers' not in batch['scenes'][1]
    assert batch['scenes'][1]['territory_ids']==['pontic-steppe']
    batch['scenes'][0]['visual_layers']=[{**original[0],'label':'Conflicting label'}]
    with pytest.raises(ValueError,match='contenuti diversi'):normalize_inline_visuals(batch)


def setup_plan(path):
    concept={'title':'Technical replay','short_title':'Replay','description':'Regression fixture','display_date':'Fixture',
             'historical_period':{'start':-4000,'end':2024},'narrative_basis':'history','analysis':{},'uncertainties':[],
             'chapters':[{'title':f'Chapter {i}','purpose':'Technical regression fixture.'} for i in range(3)]}
    path.mkdir(exist_ok=True)
    (path/'outline-concept.json').write_text(json.dumps(concept),encoding='utf-8')
    (path/'outline-catalog.json').write_text(json.dumps(ARCHIVE['catalog']),encoding='utf-8')


class ReplaySession:
    def __init__(self,batch):self.batch=batch;self.calls=[]
    def post(self,url,**kwargs):
        request=kwargs['json'];self.calls.append(request)
        text=request['messages'][1]['content'].split('ASSEGNAZIONI ESATTE:\n')[1]
        assignments=json.JSONDecoder().raw_decode(text)[0];indices=[row['index'] for row in assignments]
        if min(indices)<2:
            batch=copy.deepcopy(self.batch);batch['scenes']=[scene for scene in batch['scenes'] if scene['index'] in indices]
        else:
            batch={'scenes':[{'index':index,'title':['Archivi di scrittura','Trasmissione delle testimonianze'][index-2],
                    'date':'Fixture','historical_range':[-1000,1900],'scene_type':'timeline','focus':[],
                    'event':['I materiali scritti conservano forme linguistiche confrontabili.',
                             'Le comunità trasmettono testimonianze attraverso epoche diverse.'][index-2]} for index in indices]}
        class Reply:
            status_code=200
            def json(self):return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(batch)}}]}
        return Reply()


def run_plan(path,batch):
    setup_plan(path);logs=[]
    model=LLM(Settings(model='OFFLINE_REPLAY').model_dump());model.session=ReplaySession(batch)
    project={'topic':'Evoluzione delle lingue indoeuropee','minutes':2,'notes':''}
    result=build_history_outline(model,'Technical fixture',project,'general_history',[],assessment([]),path,
                                  history_tools(CORE)[1],logs.append,lambda:None)
    return result,model,logs


@pytest.mark.parametrize('number',[0,1,2])
def test_actual_builder_recovers_complete_archived_batches_and_resume_is_identical(tmp_path,number):
    result,model,logs=run_plan(tmp_path,copy.deepcopy(ARCHIVE['batches'][number]))
    assert len(result['scenes'])==4 and model.calls==3  # Two complete rejected replies, then the next pair.
    assert result['scenes'][1]['scene_type']=='event_focus'
    assert result['scenes'][1]['event']==ARCHIVE['batches'][number]['scenes'][1]['event']
    assert result['visual_warnings'][0]['scene_id']=='02'
    assert any('rimandato alla revisione' in text for text in logs)
    checkpoint=json.loads((tmp_path/'outline-progress.json').read_text(encoding='utf-8'))
    assert checkpoint['visual_warnings']==result['visual_warnings']
    second,model2,_=run_plan(tmp_path,copy.deepcopy(ARCHIVE['batches'][number]))
    assert model2.calls==0 and second==result


@pytest.mark.parametrize('failure',['invented_source','zero_year','missing_event','invalid_catalog_coordinate'])
def test_visual_fallback_never_bypasses_historical_or_source_errors(tmp_path,failure):
    raw=copy.deepcopy(ARCHIVE['batches'][2])
    if failure=='invented_source':raw['scenes'][1]['movements']['m1']['sources']=['FAKE_SOURCE']
    elif failure=='zero_year':raw['scenes'][1]['historical_range']=[0,1500]
    elif failure=='missing_event':raw['scenes'][1]['event_ids']=['event-that-does-not-exist']
    else:
        setup_plan(tmp_path)
        catalog=copy.deepcopy(ARCHIVE['catalog']);catalog['places'][0]['pos']=[999,45]
        (tmp_path/'outline-catalog.json').write_text(json.dumps(catalog),encoding='utf-8')
        model=LLM(Settings(model='OFFLINE_REPLAY').model_dump());model.session=ReplaySession(raw)
        with pytest.raises(ValueError):build_history_outline(model,'Technical fixture',{'topic':'Lingue indoeuropee','minutes':2,'notes':''},
            'general_history',[],assessment([]),tmp_path,history_tools(CORE)[1],lambda text:None,lambda:None)
        assert not model.session.calls;return
    with pytest.raises(ModelError):run_plan(tmp_path,raw)
    if (tmp_path/'outline-progress.json').is_file():
        saved=json.loads((tmp_path/'outline-progress.json').read_text(encoding='utf-8'))
        assert all(scene['index']!=1 for scene in saved['scenes'])


def test_model_cannot_self_declare_recovery_to_bypass_visual_contract():
    raw={'visual_warnings':[{'reason':'trust me'}],'scenes':[{'visual_recovery':{'version':1,'placeholder':True,'reason':'trust me'},'event':'unchanged'}]}
    assert strip_model_recovery(raw)=={'scenes':[{'event':'unchanged'}]}


def test_valid_portrait_survives_rejected_route_with_a_suitable_scene_type():
    history_tools(CORE);batch=shape(ARCHIVE['batches'][2]);scene=batch['scenes'][1]
    scene.update(scene_type='animated_route',person_ids=['researcher'],territory_ids=[])
    recover_visuals(batch,ARCHIVE['catalog']['places'],{'asset_ids':set(),'territory_ids':set()},{'journey':False},4)
    assert scene['scene_type']=='person_intro' and scene['person_ids']==['researcher'] and not scene['movements']
    assert not scene['visual_recovery']['placeholder']


def test_recovered_outline_compiles_through_all_existing_document_and_coverage_gates(tmp_path):
    outline,_,_=run_plan(tmp_path,copy.deepcopy(ARCHIVE['batches'][2]))
    from engine.history_authoring import compile_outline
    from engine.history_schema import validate_document
    from engine.history_direction import require_coverage
    text='Questa frase serve soltanto a verificare il formato tecnico della narrazione. '
    narration=[{'index':i,'lines':[text*4,text*4],'fact':'Fixture tecnica','kicker':'Prova'} for i in range(4)]
    project={'id':'offline-replay','topic':'Lingue indoeuropee','minutes':2,'notes':''}
    pack,_=compile_outline(outline,narration,[],project,{'fps':24,'research_context':assessment([])})
    validated=validate_document(pack)
    assert validated['slug']==pack['slug'] and require_coverage(validated)['passed']
    assert pack['scenes'][1]['visual_recovery']['placeholder']
    assert pack['scenes'][1]['movements']==[] and pack['metadata']['visual_warnings']


def test_narrator_receives_only_accepted_scene_data_not_omitted_route_audit(monkeypatch):
    from app import narration_builder
    row={'index':0,'title':'Scena originale','event':'Testo invariato.','source_ids':[],'movements':[],
         'visual_recovery':{'omitted_items':[{'data':{'to':'SECRET_REJECTED_DESTINATION'}}]}}
    before=copy.deepcopy(row);seen=[]
    class Model:
        def structured(self,system,prompt,schema):seen.append(prompt);return {'scenes':[{'index':0,'lines':['Uno.','Due.']}]}
    monkeypatch.setattr(narration_builder,'issue',lambda *args,**kwargs:'')
    narration_builder.request_rows(Model(),'Fixture',{'title':'Prova','scenes':[row]},[row],[],80,lambda value:None,1)
    assert 'SECRET_REJECTED_DESTINATION' not in seen[0] and 'visual_recovery' not in seen[0]
    assert 'non aggiungere spostamenti' in seen[0] and row==before


def test_malformed_optional_endpoint_and_nonfinite_audit_never_crash_or_emit_nan():
    history_tools(CORE);batch=shape(ARCHIVE['batches'][2]);scene=batch['scenes'][1]
    scene['movements']=[{'from':['bad'],'to':'central-europe','points':[[float('nan'),45],[15,48]],'semantic':'migration'}]
    batch=movement_endpoints(batch,ARCHIVE['catalog']['places'])
    from app.movement_sync import prepare_scene,plan_issue
    prepare_scene(batch['scenes'][1],ARCHIVE['catalog']['places']);plan_issue(batch['scenes'][1],ARCHIVE['catalog']['places'])
    reports=recover_visuals(batch,ARCHIVE['catalog']['places'],{'asset_ids':set(),'territory_ids':set()},{'journey':False},4)
    json.dumps(reports,allow_nan=False)
    assert reports[0]['omitted_items'][0]['data']['points'][0][0]=={'invalid_numeric_value':'nan'}
