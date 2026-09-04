"""Small battle authoring requests through the provider-neutral Chat Completions client."""
import copy,json
from pathlib import Path
import pytest
from app.battle_outline import build_battle_outline
from app.battle_visuals import verify_place_coordinates,enrich_battle_outline
from app.compiler import compile_pack
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


def test_battle_geocoder_repairs_places_and_existing_route_endpoints(tmp_path):
    value={**copy.deepcopy(CATALOG),'scenes':[{'title':'Ritirata','date':'1815','focus':['ligny','waterloo'],
        'event':'Le forze si ritirano verso Waterloo.','source_ids':[],
        'routes':[{'side':'b','points':[[4.87,50.52],[4.412,50.68]]}],'commander_ids':[]} for _ in range(3)]}
    answers={'Waterloo':[{'lon':'4.3977','lat':'50.7154','display_name':'Waterloo, Brabant wallon, Belgique'}],
             'Ligny':[{'lon':'4.5747','lat':'50.5121','display_name':'Ligny, Namur, Belgique'}]}
    class Response:
        def __init__(self,data):self.data=data
        def raise_for_status(self):pass
        def json(self):return self.data
    class Session:
        headers={}
        def get(self,url,params,timeout):return Response(answers[params['q']])
    result=verify_place_coordinates(value,tmp_path,lambda _:None,Session(),lambda _:None)
    positions={p['id']:p['pos'] for p in result['places']}
    assert positions['ligny']==[4.5747,50.5121] and positions['waterloo']==[4.3977,50.7154]
    assert result['scenes'][0]['routes'][0]['points']==[positions['ligny'],positions['waterloo']]
    assert (tmp_path/'battle-geocoding.json').exists()


def test_battle_geocoder_rejects_distant_same_named_places_from_cache(tmp_path):
    value={**copy.deepcopy(CATALOG),'places':[
        {'id':'waterloo','name':'Waterloo','pos':[4.412,50.68]},
        {'id':'la_haye','name':'La Haye Sainte','pos':[4.415,50.678]}],
        'scenes':[{'title':'Campo','date':'1815','focus':['waterloo','la_haye'],'event':'Il campo di battaglia.',
          'source_ids':[],'routes':[{'side':'a','points':[[4.415,50.678],[4.412,50.68]]}],'commander_ids':[]} for _ in range(3)]}
    (tmp_path/'battle-geocoding.json').write_text(json.dumps([
        {'id':'waterloo','old':[4.412,50.68],'pos':[4.4084,50.7033]},
        {'id':'la_haye','old':[4.415,50.678],'pos':[-0.96537,49.20759]}]),encoding='utf-8')
    logs=[];result=verify_place_coordinates(value,tmp_path,logs.append)
    positions={p['id']:p['pos'] for p in result['places']}
    assert positions['waterloo']==[4.4084,50.7033]
    assert positions['la_haye']==[4.415,50.678]
    assert result['scenes'][0]['routes'][0]['points'][0]==[4.415,50.678]
    assert any('risultati omonimi lontani scartati' in line for line in logs)


def test_battle_visual_pass_uses_semantic_endpoints_and_compiler_draws_tactics(tmp_path):
    value={**copy.deepcopy(CATALOG),'scenes':[
        {'title':'Apertura','date':'1815','focus':['waterloo'],'event':'Il campo di battaglia.','source_ids':['S1'],'routes':[],'commander_ids':['napoleone']},
        {'title':'Assalto','date':'1815','focus':['waterloo'],'event':'La cavalleria francese carica il centro.','source_ids':['S1'],'routes':[],'commander_ids':['napoleone','wellington']},
        {'title':'Ritirata','date':'1815','focus':['waterloo','ligny'],'event':'Le forze francesi si ritirano.','source_ids':['S1'],'routes':[],'commander_ids':['wellington']} ]}
    # Avoid network in the visual-plan test; geocoding itself is covered above.
    (tmp_path/'battle-geocoding.json').write_text('[]')
    class Model:
        def structured(self,system,prompt,schema,validator=None):
            rows=[]
            if "'index': 1" in prompt:rows.append({'index':1,'moves':[{'side':'a','kind':'attack','label':'Cavalleria francese','unit_kind':'cavalry','to_place':'waterloo','approach':'south'}]})
            if "'index': 2" in prompt:rows.append({'index':2,'moves':[{'side':'a','kind':'retreat','label':'Armata francese','unit_kind':'infantry','from_place':'waterloo','to_place':'ligny'}]})
            return validator({'scenes':rows})
    result=enrich_battle_outline(Model(),'Sistema',value,tmp_path,lambda _:None,lambda:None)
    assert result['scenes'][1]['routes'][0]['kind']=='attack'
    assert result['scenes'][1]['routes'][0]['points'][-1]==[4.412,50.68]
    paragraph=' '.join(['Narrazione']+['storica']*49)
    narration=[{'index':i,'lines':[paragraph,paragraph],'fact':'Fatto storico della scena.','kicker':'Movimento sulla mappa'} for i in range(3)]
    pack,geography=compile_pack(result,narration,[{'id':'S1','title':'Fonte','url':'https://example.org','retrieved':'2026-01-01'}],
        {'id':'fixture','minutes':2},{'fps':30,'research_context':{'fallback_used':False}})
    assert pack['scenes'][1]['camera_end'][2]<.2
    assert pack['scenes'][1]['routes'] and pack['scenes'][1]['arrows']
    assert {u['side'] for u in pack['scenes'][1]['units']}=={'a','b'}
    assert pack['commanders']['wellington']['side']=='b'
    assert all(isinstance(spec,dict) and {'bounds','zoom'}<=set(spec) for spec in geography['patches'].values())
    assert max(spec['zoom'] for spec in geography['patches'].values())>=14
