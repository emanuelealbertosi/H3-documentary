"""Provider fixtures reproduce truncation and semantic IDs without paid API calls."""
import copy,json
from pathlib import Path
import pytest,requests
from app.models import Settings
from app.general import HistoryOutline,history_tools
from app.outline_builder import build_history_outline,HistoryCatalog,merge_rows
from app.outline_normalization import collections,movement_endpoints
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


def test_truncated_outer_json_does_not_become_a_nested_object():
    with pytest.raises(ModelError):extract_json('{"scene":{"title":"complete nested value"},"incomplete":')
    assert extract_json('```json\n{"ok":true}\n```')=={'ok':True}


def test_geographic_contract_is_checked_before_checkpoint(tmp_path):
    def reply(title,payload,number):
        result=normal_reply(title,payload,number)
        if title=='HistorySceneBatch':result['scenes'][0]['movements']=[{'sources':[],'points':[[999,41],[14,41]],'semantic':'journey'}]
        return result
    llm,audit,logs=model(reply)
    with pytest.raises(ModelError,match='Coordinate'):build(llm,tmp_path,logs)
    assert not (tmp_path/'outline-progress.json').exists()


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
