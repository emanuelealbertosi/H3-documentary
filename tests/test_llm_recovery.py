"""Real structured-request logic with bounded, explicitly simulated HTTP responses."""
import copy
import json

import pytest
import requests
from pydantic import BaseModel,Field

from app.llm import LLM,InvalidStructuredData,ModelError,TruncatedResponse
from app.models import Settings


class Candidate(BaseModel):
    index:int
    values:list[int]=Field(default_factory=list)


def response(value,*,status=200,finish='stop'):
    reply=requests.Response();reply.status_code=status
    data=({'error':{'message':'Fixture denied'}} if status!=200 else
          {'choices':[{'finish_reason':finish,'message':{'content':value if isinstance(value,str) else json.dumps(value)}}]})
    reply._content=json.dumps(data).encode('utf-8')
    return reply


class FakeHTTP:
    def __init__(self,replies):self.replies=iter(replies);self.requests=[]
    def post(self,url,**kwargs):
        self.requests.append(copy.deepcopy(kwargs['json']))
        item=next(self.replies)
        if isinstance(item,Exception):raise item
        return item


def model(replies,limit=20):
    config=Settings(model='EXPLICIT_HTTP_FIXTURE',json_mode=True,temperature=.25).model_dump()
    config['request_limit']=limit
    llm=LLM(config);llm.session=FakeHTTP(replies)
    return llm


def reject(candidate):raise ValueError('Destinazione non presente nella scena')


def test_repeated_canonical_data_stops_after_two_and_keeps_pre_callback_snapshot():
    llm=model([response('{"index":1,"values":[3,2]}'),response('{"values":[3,2],"index":1}')])
    mutated=[]
    def mutate_then_reject(candidate):
        mutated.append(candidate)
        candidate['values'].append(99)
        reject(candidate)
    with pytest.raises(InvalidStructuredData) as captured:
        llm.structured('system','user',Candidate,validator=mutate_then_reject,stop_on_repeated_invalid=True)
    error=captured.value
    assert error.repeated and len(llm.session.requests)==llm.calls==2
    assert error.data=={'index':1,'values':[3,2]}
    mutated[-1]['values'].append(100)
    assert error.data['values']==[3,2]
    assert str(error).startswith('Il modello non riesce a produrre dati validi per questa fase. ')


def test_different_candidates_with_same_problem_do_not_stop_early():
    llm=model([response({'index':i}) for i in (1,2,3)])
    with pytest.raises(InvalidStructuredData) as captured:
        llm.structured('system','user',Candidate,validator=reject,stop_on_repeated_invalid=True)
    assert llm.calls==3 and not captured.value.repeated
    assert captured.value.data=={'index':3,'values':[]}


def test_same_candidate_with_different_problems_is_not_a_repeated_failure():
    llm=model([response({'index':1}) for _ in range(3)])
    problems=iter(['Primo problema','Secondo problema','Terzo problema'])
    def different_issue(candidate):raise ValueError(next(problems))
    with pytest.raises(InvalidStructuredData) as captured:
        llm.structured('system','user',Candidate,validator=different_issue,stop_on_repeated_invalid=True)
    assert llm.calls==3 and not captured.value.repeated and captured.value.problem=='Terzo problema'


def test_schema_error_has_no_schema_validated_data():
    llm=model([response({'index':'non numerico'}) for _ in range(2)])
    with pytest.raises(InvalidStructuredData) as captured:
        llm.structured('system','user',Candidate,stop_on_repeated_invalid=True)
    assert captured.value.data is None and captured.value.repeated
    assert 'index' in captured.value.problem and llm.calls==2


def test_final_callback_error_keeps_normalized_schema_data():
    llm=model([response({'index':'2','values':['4']})])
    with pytest.raises(InvalidStructuredData) as captured:
        llm.structured('system','user',Candidate,attempts=1,validator=reject)
    assert captured.value.data=={'index':2,'values':[4]}
    assert not captured.value.repeated and captured.value.problem=='Destinazione non presente nella scena'


def test_default_third_request_changes_prompt_without_echo_or_configuration_changes():
    llm=model([response({'index':1}),response({'index':1}),response({'index':2})])
    before=copy.deepcopy(llm.config)
    def accept_second(candidate):
        if candidate['index']==1:reject(candidate)
        return candidate
    result=llm.structured('system','user',Candidate,validator=accept_second)
    assert result['index']==2 and llm.calls==3 and llm.config==before
    first,second,third=llm.session.requests
    assert any(m['role']=='assistant' for m in second['messages'])
    assert not any(m['role']=='assistant' for m in third['messages'])
    assert third['messages'][:2]==first['messages']
    assert 'Dati ripetuti' in third['messages'][-1]['content']
    assert 'Rigenera' in third['messages'][-1]['content']
    assert {k:v for k,v in first.items() if k!='messages'}=={k:v for k,v in third.items() if k!='messages'}


@pytest.mark.parametrize('failure',[response(None,status=401),response(None,status=403),requests.Timeout('fixture'),requests.ConnectionError('fixture')])
def test_transport_and_auth_failures_are_distinct_and_not_retried_as_repairs(failure):
    llm=model([failure])
    with pytest.raises(ModelError) as captured:
        llm.structured('system','user',Candidate,stop_on_repeated_invalid=True)
    assert not isinstance(captured.value,InvalidStructuredData) and llm.calls==1


def test_request_budget_is_not_extended_for_structured_recovery():
    llm=model([response({'index':1}),response({'index':1})],limit=2)
    with pytest.raises(ModelError,match='limite di richieste') as captured:
        llm.structured('system','user',Candidate,validator=reject)
    assert not isinstance(captured.value,InvalidStructuredData) and llm.calls==2


def test_truncated_response_is_not_salvaged_as_a_valid_nested_candidate():
    llm=model([response('{"data":{"index":1},"unfinished":',finish='length')])
    callbacks=[]
    with pytest.raises(TruncatedResponse):
        llm.structured('system','user',Candidate,validator=lambda value:callbacks.append(value),
                       stop_on_repeated_invalid=True,split_on_truncation=True)
    assert not callbacks and llm.calls==1


def test_malformed_json_never_exposes_recoverable_candidate_data():
    llm=model([response('{"index":') for _ in range(3)])
    with pytest.raises(ModelError,match='oggetto JSON valido') as captured:
        llm.structured('system','user',Candidate,stop_on_repeated_invalid=True)
    assert not isinstance(captured.value,InvalidStructuredData) and llm.calls==3
