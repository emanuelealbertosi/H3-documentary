"""Small battle authoring requests through the provider-neutral Chat Completions client."""
import copy,json
from pathlib import Path
import pytest
from app.battle_outline import build_battle_outline
from app.llm import LLM
from app.models import Settings
from app.research import assessment

CATALOG={'title':'Waterloo: il giorno decisivo','short_title':'Waterloo','description':'Fixture tecnica in italiano.',
         'display_date':'18 giugno 1815','factions':['Francia','Settima coalizione'],
         'places':[{'id':'waterloo','name':'Waterloo','pos':[4.412,50.68]},{'id':'ligny','name':'Ligny','pos':[4.87,50.52]}],
         'commanders':[{'id':'napoleone','name':'Napoleone Bonaparte','role':'Imperatore dei francesi','wikipedia_page':'Napoleon'},
                       {'id':'wellington','name':'Duca di Wellington','role':'Comandante alleato','wikipedia_page':'Arthur Wellesley, 1st Duke of Wellington'}],
         'river_names':[],'scenes':[],'uncertainties':['Fixture tecnica.']}


class Provider:
    def __init__(self,remote=False):self.requests=[];self.remote=remote;self.bad=True
    def post(self,url,**kwargs):
        payload=kwargs['json'];self.requests.append(payload);spec=json.loads(payload['messages'][0]['content'].split('secondo questo schema:\n')[1])
        if spec['title']=='BattleCatalog':value=copy.deepcopy(CATALOG)
        else:
            text=payload['messages'][1]['content'];assign=json.JSONDecoder().raw_decode(text.split('ASSEGNAZIONI ESATTE:\n')[1])[0]
            rows=[]
            for item in assign:
                focus=['Attacco francese'] if self.bad else ['waterloo']
                rows.append({'index':item['index'],'title':f'Scena {item["index"]+1}','date':'18 giugno 1815',
                             'focus':focus,'event':'Movimenti documentati nella fixture tecnica.','source_ids':[],
                             'routes':[{'side':'a','points':[[4.35,50.66],[4.42,50.68]],'uncertain':True}],
                             'commander_ids':['Napoleone Bonaparte']})
            value={'scenes':rows};self.bad=False
        response={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]}
        return type('Response',(),{'status_code':200,'json':lambda self:response})()


@pytest.mark.parametrize('provider,url',[('lmstudio','http://localhost:1234/v1'),('openai','https://model.example/v1')])
def test_local_and_remote_compatible_servers_use_same_checkpointed_contract(tmp_path,provider,url):
    logs=[];cfg=Settings(provider=provider,base_url=url,model='FIXTURE',request_limit=30).model_dump()
    llm=LLM(cfg,audit=lambda _:None);llm.session=Provider(provider=='openai');llm.progress=logs.append
    result=build_battle_outline(llm,'Sistema di prova',{'topic':'Battaglia di Waterloo','minutes':2,'notes':''},
                                [],assessment([]),tmp_path,logs.append,lambda:None)
    assert len(result['scenes'])==4
    assert all(s['focus']==['waterloo'] and s['commander_ids']==['napoleone'] for s in result['scenes'])
    assert llm.calls==4  # catalog, invalid pair, corrected pair, second pair
    assert any('Correzione dei dati' in line and 'Attacco francese' in line for line in logs)
    assert (tmp_path/'battle-catalog.json').exists() and (tmp_path/'battle-progress.json').exists()
    # Complete checkpoints resume without any provider call.
    second=LLM(cfg);second.session=type('Forbidden',(),{'post':lambda *a,**k:(_ for _ in ()).throw(AssertionError('provider called'))})()
    assert build_battle_outline(second,'Sistema',{'topic':'Battaglia di Waterloo','minutes':2,'notes':''},[],assessment([]),tmp_path,logs.append,lambda:None)==result


def test_battle_reference_error_names_scene_field_bad_values_and_allowed_ids():
    from app.models import Outline
    value={**copy.deepcopy(CATALOG),'scenes':[{'title':'Assalto','date':'1815','focus':['attacco'],'event':'Fixture.',
                                             'source_ids':[],'routes':[],'commander_ids':['imperatore']}] * 3}
    with pytest.raises(ValueError) as caught:Outline.model_validate(value)
    message=str(caught.value)
    assert all(term in message for term in ['Scena 1 (Assalto)','focus',"['attacco']",'waterloo','non temi'])
