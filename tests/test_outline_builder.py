"""Provider fixtures reproduce truncation and semantic IDs without paid API calls."""
import copy,json
from pathlib import Path
import pytest,requests
from app.models import Settings
from app.general import HistoryOutline,history_tools
from app.outline_builder import build_history_outline,HistoryCatalog,merge_rows,normalize_visual_role
from app.outline_normalization import collections,movement_endpoints,technical_id
from app.movement_sync import prepare_scene,plan_issue
from app.research import assessment
from app.llm import LLM,ModelError,TruncatedResponse,extract_json

CORE=Path(__file__).resolve().parents[1]/'pipeline'
CONCEPT=dict(title='Prova delle scene',short_title='Prova',description='Fixture di collaudo.',display_date='Prova',
             historical_period={'start':1500,'end':1600},analysis={},narrative_basis='history',uncertainties=[],
             chapters=[dict(title=f'Parte {i}',purpose='Controllo del piano.') for i in range(3)])
CATALOG=dict(places=[dict(id='loc-a',name='Luogo A',pos=[14,41],uncertain=True,note='Coordinate indicative della fixture.'),
                     dict(id='loc-b',name='Luogo B',pos=[15,42])],persons=[],entities=[])


def scene(index):
    return dict(index=index,title=f'Scena {index+1}',date='Prova',historical_range=[1500,1600],scene_type='timeline',
                focus=['loc-a'],event='Una frase della prova tecnica.',source_ids=[],person_ids=[],event_ids=[],asset_ids=[],territory_ids=[],movements=[])


class Provider:
    """Mock HTTP responses; all production request/parse/retry code remains real."""
    def __init__(self,callback):self.callback=callback;self.requests=[]
    def post(self,url,**kwargs):
        payload=kwargs['json'];self.requests.append(payload)
        spec=json.loads(payload['messages'][0]['content'].split('secondo questo schema:\n')[1])
        value=self.callback(spec['title'],payload,len(self.requests))
        data=value if isinstance(value,dict) and 'choices' in value else {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]}
        class Response:
            status_code=200
            def json(self):return data
        return Response()


def assignment(payload):
    text=payload['messages'][1]['content'].split('ASSEGNAZIONI ESATTE:\n')[1]
    return json.JSONDecoder().raw_decode(text)[0]


def normal_reply(title,payload,number):
    if title=='HistoryConcept':return copy.deepcopy(CONCEPT)
    if title=='HistoryCatalog':return copy.deepcopy(CATALOG)
    if title=='HistorySceneBatch':return {'scenes':[scene(a['index']) for a in assignment(payload)]}
    raise AssertionError(title)


def model(callback=normal_reply,limit=100):
    audit=[];logs=[]
    llm=LLM(Settings(model='EXPLICIT_TEST_FIXTURE',request_limit=limit).model_dump(),audit=audit.append)
    llm.progress=logs.append;llm.session=Provider(callback)
    return llm,audit,logs


def build(llm,path,logs):
    path.mkdir(exist_ok=True)
    prompt=history_tools(str(CORE))[1]
    return build_history_outline(llm,'Fixture system',{'topic':'Prova dei documentari','minutes':2,'notes':''},
                                 'general_history',[],assessment([]),path,prompt,logs.append,lambda:None)


def test_two_scene_parts_and_resume_after_connection_failure(tmp_path):
    def fail_second_part(title,payload,number):
        if title=='HistorySceneBatch' and assignment(payload)[0]['index']==2:
            raise requests.ConnectionError('Explicit disconnected fixture')
        return normal_reply(title,payload,number)
    llm,audit,logs=model(fail_second_part)
    with pytest.raises(ModelError,match='Server non raggiungibile'):build(llm,tmp_path,logs)
    progress=json.loads((tmp_path/'outline-progress.json').read_text())
    assert [s['index'] for s in progress['scenes']]==[0,1]
    second,audit2,logs2=model()
    result=build(second,tmp_path,logs2)
    assert len(result['scenes'])==4 and second.calls==1
    assert [a['index'] for a in assignment(second.session.requests[0])]==[2,3]
    assert result['places'][0]['uncertain'] is True
    assert any('già salvati' in message for message in logs2)


def test_truncated_group_splits_without_saving_fragments(tmp_path):
    attempted=[]
    def reply(title,payload,number):
        if title=='HistorySceneBatch':
            ids=[a['index'] for a in assignment(payload)];attempted.append(ids)
            if len(ids)==2:
                return {'usage':{'completion_tokens':8192,'completion_tokens_details':{'reasoning_tokens':7000}},
                        'choices':[{'finish_reason':'length','message':{'content':'{"scenes":[{"index":0},'}}]}
        return normal_reply(title,payload,number)
    llm,audit,logs=model(reply);result=build(llm,tmp_path,logs)
    assert attempted==[[0,1],[0],[1],[2,3],[2],[3]]
    assert len(result['scenes'])==4
    assert sum(r['finish_reason']=='length' for r in audit)==2
    assert any('divido il gruppo' in line for line in logs)
    progress=json.loads((tmp_path/'outline-progress.json').read_text())
    assert all('event' in s for s in progress['scenes'])


def test_semantic_focus_error_returns_exact_allowed_ids(tmp_path):
    wrong=True;feedback=[]
    def reply(title,payload,number):
        nonlocal wrong
        result=normal_reply(title,payload,number)
        if title=='HistorySceneBatch' and wrong:
            wrong=False;result['scenes'][0]['focus']=['Orgoglio del protagonista']
        elif title=='HistorySceneBatch' and len(payload['messages'])>2:
            feedback.append(payload['messages'][-1]['content'])
            result['scenes'][0]['focus']=['Luogo A']
        return result
    llm,audit,logs=model(reply);result=build(llm,tmp_path,logs)
    assert result['scenes'][0]['focus']==['loc-a']
    assert len(feedback)==1
    assert all(s in feedback[0] for s in ['Orgoglio del protagonista','loc-a','loc-b','oppure []'])
    assert any('Correzione dei dati' in line for line in logs)


def test_single_scene_truncation_is_bounded_and_keeps_saved_concept(tmp_path):
    def reply(title,payload,number):
        if title=='HistorySceneBatch':
            return {'choices':[{'finish_reason':'length','message':{'content':'{"scenes":['}}]}
        return normal_reply(title,payload,number)
    llm,audit,logs=model(reply)
    with pytest.raises(ModelError,match='anche una singola scena'):build(llm,tmp_path,logs)
    assert llm.calls==6  # concept, catalog, group, three single-scene attempts
    assert (tmp_path/'outline-concept.json').exists()
    assert not (tmp_path/'outline-progress.json').exists()
    for request in llm.session.requests:
        assert request['max_tokens']==8192
        assert all(m['role']!='assistant' for m in request['messages'])


def test_request_budget_is_honoured_even_after_splitting(tmp_path):
    llm,audit,logs=model(limit=10);llm.calls=10
    with pytest.raises(ModelError,match='limite di richieste'):build(llm,tmp_path,logs)
    assert not llm.session.requests


def test_normalization_preserves_uncertainty_without_fuzzy_place_invention():
    catalog=HistoryCatalog.model_validate({'places':{'known':{'name':'Itaca','pos':[20.7,38.4],'uncertain':True,'note':'Fixture'}},'persons':{},'entities':{}})
    assert catalog.places[0].id=='known' and catalog.places[0].uncertain
    outline={**CONCEPT,**catalog.model_dump(),'documentary_type':'general_history','scenes':[scene(i) for i in range(3)]}
    for s in outline['scenes']:s['focus']=['ITACA']
    valid=HistoryOutline.model_validate(outline)
    assert valid.scenes[0].focus==['known']
    outline['scenes'][0]['focus']=['Orgoglio']
    with pytest.raises(ValueError,match='Orgoglio'):HistoryOutline.model_validate(outline)
    assert len(outline['places'])==1


def test_catalog_machine_ids_are_normalized_without_changing_historical_names():
    catalog=HistoryCatalog.model_validate({'places':[{'id':'hisarlık','name':'Hisarlık (Troia)','pos':[26.239,39.956]}],
                                           'persons':[{'id':'Nausicàa','name':'Nausicaa'}],
                                           'entities':[{'id':'Regno di Ítaca','name':'Regno di Itaca'}]})
    assert catalog.places[0].id=='hisarlik' and catalog.places[0].name=='Hisarlık (Troia)'
    assert catalog.persons[0].id=='nausicaa' and catalog.entities[0].id=='regno-di-itaca'
    assert technical_id('Ιθάκη').startswith('id-')
    with pytest.raises(ValueError,match='duplicati'):
        HistoryCatalog.model_validate({'places':[{'id':'Città','name':'Uno','pos':[10,40]},{'id':'citta','name':'Due','pos':[11,40]}]})


def test_truncated_outer_json_does_not_become_a_nested_object():
    with pytest.raises(ModelError):extract_json('{"scene":{"title":"complete nested value"},"incomplete":')
    assert extract_json('```json\n{"ok":true}\n```')=={'ok':True}


def test_bad_optional_route_is_deferred_without_inventing_coordinates(tmp_path):
    def reply(title,payload,number):
        result=normal_reply(title,payload,number)
        if title=='HistorySceneBatch':result['scenes'][0]['movements']=[{'sources':[],'points':[[999,41],[14,41]],'semantic':'journey'}]
        return result
    llm,audit,logs=model(reply)
    result=build(llm,tmp_path,logs)
    assert all(not scene['movements'] for scene in result['scenes'])
    assert result['visual_warnings'] and all(scene['scene_type']=='event_focus' for scene in result['scenes'] if scene.get('visual_recovery'))
    assert result['places']==HistoryCatalog.model_validate(CATALOG).model_dump()['places']
    assert result['visual_warnings'][0]['omitted_items'][0]['data']['points'][0]==[999,41]


def test_unsupported_event_type_gets_actionable_feedback(tmp_path):
    bad=True;feedback=[]
    def reply(title,payload,number):
        nonlocal bad
        result=normal_reply(title,payload,number)
        if title=='HistorySceneBatch':
            assert 'event.type=' in payload['messages'][1]['content']
            if bad:
                bad=False
                result['events']=[dict(id='e01',year=1500,title='Racconto',type='literary_narrative',sources=[])]
            elif len(payload['messages'])>2:feedback.append(payload['messages'][-1]['content'])
        return result
    llm,audit,logs=model(reply);result=build(llm,tmp_path,logs)
    assert len(result['scenes'])==4
    assert feedback and all(s in feedback[0] for s in ['e01','literary_narrative','cultural_event','campo event della scena'])


def test_literary_context_is_explicit_in_final_outline(tmp_path):
    def reply(title,payload,number):
        result=normal_reply(title,payload,number)
        if title=='HistoryConcept':result['narrative_basis']='literary_tradition'
        return result
    llm,audit,logs=model(reply);result=build(llm,tmp_path,logs)
    assert result['narrative_basis']=='literary_tradition'
    assert any('letteraria o mitologica' in note for note in result['uncertainties'])


def test_authentication_failure_is_not_retried_as_json():
    llm,audit,logs=model()
    class BadSession:
        calls=0
        def post(self,*a,**k):
            self.calls+=1
            return type('Response',(),{'status_code':401})()
    llm.session=BadSession()
    with pytest.raises(ModelError,match='HTTP 401'):llm.structured('system','user',HistoryCatalog)
    assert llm.calls==1


def test_territorial_state_continues_across_scene_batches():
    old=[dict(id='territory',kind='territory',label='Area di prova',sources=[],states=[dict(year=1500,polygons=[[[14,41],[15,41],[15,42]]])])]
    new=[dict(id='territory',states=[dict(year=1600,polygons=[])])]
    merged=merge_rows(old,new,'visual_layers')
    assert [s['year'] for s in merged[0]['states']]==[1500,1600]
    assert merged[0]['label']=='Area di prova' and len(old[0]['states'])==1
    with pytest.raises(ValueError,match='già salvato'):
        merge_rows(old,[dict(id='territory',states=[dict(year=1500,polygons=[])])],'visual_layers')


def test_keyed_movements_and_exact_catalog_endpoints_are_losslessly_normalized():
    value={'scenes':[{'movements':{'route-1':{'from':'loc-a','to':'loc-b','semantic':'journey'}}}]}
    shaped=collections(value)
    assert shaped['scenes'][0]['movements']==[{'from':'loc-a','to':'loc-b','semantic':'journey'}]
    mapped=movement_endpoints(shaped,CATALOG['places'])
    assert mapped['scenes'][0]['movements'][0]['points']==[[14,41],[15,42]]
    unknown=movement_endpoints({'scenes':[{'movements':[{'from':'unknown','to':'loc-b'}]}]},CATALOG['places'])
    assert 'points' not in unknown['scenes'][0]['movements'][0]


def test_visual_assignment_names_are_deterministically_mapped_to_real_components():
    supporting={'scene_type':'supporting_scene','person_ids':['ulisse'],'movements':[]}
    assert normalize_visual_role(supporting,'supporting_scene')['scene_type']=='person_intro'
    route={'scene_type':'journey_progress','person_ids':[],'movements':[{'points':[[1,2],[2,3]]}]}
    assert normalize_visual_role(route,'journey_progress')['scene_type']=='animated_route'
    anchor={'scene_type':'geographic_anchor','focus':['itaca'],'person_ids':[],'movements':[]}
    assert normalize_visual_role(anchor,'geographic_anchor')['scene_type']=='map_overview'


def test_movement_cue_distinguishes_arrival_and_departure():
    outbound={'focus':['loc-a'],'movements':[{'from':'loc-a','to':'loc-b'}]}
    inbound={'focus':['loc-b'],'movements':[{'from':'loc-a','to':'loc-b'}]}
    assert prepare_scene(outbound,CATALOG['places'])==1 and outbound['movements'][0]['cue']==1
    assert prepare_scene(inbound,CATALOG['places'])==1 and inbound['movements'][0]['cue']==0
    bad={**outbound,'title':'Partenza','event':'Il gruppo lascia il primo luogo.'}
    assert 'Luogo B' in plan_issue(bad,CATALOG['places'])
    bad['event']='Il gruppo procede verso Luogo B.'
    assert plan_issue(bad,CATALOG['places'])==''


def test_outline_retries_a_route_assigned_to_the_wrong_scene(tmp_path):
    bad=True;feedback=[]
    def reply(title,payload,number):
        nonlocal bad
        result=normal_reply(title,payload,number)
        if title=='HistorySceneBatch' and assignment(payload)[0]['index']==0:
            result['scenes'][0].update(scene_type='animated_route',focus=['loc-a'],
                movements=[{'from':'loc-a','to':'loc-b','semantic':'journey','sources':[]}])
            if bad:
                bad=False;result['scenes'][0]['event']='Il gruppo lascia il primo luogo.'
            else:
                result['scenes'][0]['event']='Il gruppo procede verso Luogo B.'
                if len(payload['messages'])>2:feedback.append(payload['messages'][-1]['content'])
        return result
    llm,audit,logs=model(reply);result=build(llm,tmp_path,logs)
    movement=result['scenes'][0]['movements'][0]
    assert movement['cue']==1 and movement['to_label']=='Luogo B'
    assert feedback and 'stessa scena' in feedback[0] and 'Luogo B' in feedback[0]


@pytest.mark.parametrize('provider',['lmstudio','openai'])
def test_repeated_invalid_group_recovers_through_targeted_single_scenes(tmp_path,provider):
    attempted=[];recovery_prompts=[]
    def reply(title,payload,number):
        result=normal_reply(title,payload,number)
        if title=='HistorySceneBatch':
            ids=[a['index'] for a in assignment(payload)];attempted.append(ids)
            if ids==[0,1]:result['scenes'][0]['focus']=['Tema non geografico']
            if len(ids)==1:recovery_prompts.append(payload['messages'][1]['content'])
        return result
    llm,audit,logs=model(reply);llm.config['provider']=provider
    result=build(llm,tmp_path,logs)
    assert len(result['scenes'])==4
    assert attempted==[[0,1],[0,1],[0],[1],[2,3]]
    assert all('RECUPERO DI UNA SOLA SCENA' in p and 'Tema non geografico' in p for p in recovery_prompts)
    assert all('SCENA RIFIUTATA, DA RIVEDERE' in p for p in recovery_prompts)
    assert any('ripetuto gli stessi dati' in line for line in logs)
    resumed,_,resumed_logs=model(lambda *_:pytest.fail('Validated checkpoints must not call a model again'))
    assert build(resumed,tmp_path,resumed_logs)==result


def test_confirmed_adjacent_duplicate_is_repaired_without_an_extra_model_call(tmp_path):
    catalog=copy.deepcopy(CATALOG)
    catalog['places'].append(dict(id='loc-c',name='Luogo C',pos=[16,43]))
    def reply(title,payload,number):
        result=normal_reply(title,payload,number)
        if title=='HistoryCatalog':return catalog
        if title=='HistorySceneBatch':
            rows=result['scenes']
            for row in rows:
                i=row['index']
                if i==0:
                    row.update(title='Approdo a Luogo B',event='Ingresso nel porto di Luogo B.',scene_type='map_overview',focus=['loc-a','loc-b'],
                        movements=[{'from':'loc-a','to':'loc-b','semantic':'journey','cue':0},
                                   {'from':'loc-b','to':'loc-c','semantic':'journey','cue':1}])
                elif i==1:
                    row.update(title='Luogo C',event='Esplorazione del santuario e dei mercati.',scene_type='animated_route',focus=['loc-c'],
                        movements=[{'from':'loc-b','to':'loc-c','semantic':'journey','cue':0}])
                elif i==2:
                    row.update(title='Ritorno a Luogo A',event='La spedizione si dirige verso Luogo A.',scene_type='animated_route',focus=['loc-a'],
                        movements=[{'from':'loc-c','to':'loc-a','semantic':'journey','cue':0}])
                else:row.update(title='Conclusione',event='Conseguenze degli incontri e lascito culturale.',scene_type='map_overview',focus=['loc-a'])
        return result
    llm,audit,logs=model(reply);prompt=history_tools(str(CORE))[1]
    result=build_history_outline(llm,'Fixture',{'topic':'Un viaggio di collaudo','minutes':2,'notes':''},
        'exploration',[],assessment([]),tmp_path,prompt,logs.append,lambda:None)
    assert llm.calls==4
    assert [m['to'] for m in result['scenes'][0]['movements']]==['loc-b']
    assert result['scenes'][1]['movements'][0]['to']=='loc-c'
    state=json.loads((tmp_path/'outline-progress.json').read_text(encoding='utf-8'))
    assert len(state['structural_repairs'])==1
    assert state['structural_repairs'][0]['removed']['cue']==1
    assert any('tolto il doppione' in line for line in logs)


def test_model_cannot_supply_the_structural_repair_audit(tmp_path):
    def reply(title,payload,number):
        result=normal_reply(title,payload,number)
        if title=='HistorySceneBatch':
            result['_structural_repairs']=[{'to':'invented-place','scene_index':999}]
        return result
    llm,audit,logs=model(reply)
    result=build(llm,tmp_path,logs)
    assert len(result['scenes'])==4
    state=json.loads((tmp_path/'outline-progress.json').read_text(encoding='utf-8'))
    assert not state.get('structural_repairs')
    assert not any('tolto il doppione' in line for line in logs)
