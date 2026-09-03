"""Deterministic failure/resume and provenance tests; no real LLM assertions."""
import copy,json,threading
from pathlib import Path
import pytest
from app import store,runner,pipeline,research
from app.models import Settings,ProjectRequest,Outline
from app.general import HistoryOutline,history_tools
from app.research_policy import validate_references,annotate_review

CORE=Path(__file__).resolve().parents[1]/'pipeline'


def pages(count):
    return [dict(id=f'S{i+1}',title=f'Explicit test fixture {i}',url=f'https://museum{i}.example/history',
                 text='Consulted text fixture. '*60,retrieved=store.now(),links=[]) for i in range(count)]


def web_fixture(monkeypatch,count):
    source=pages(count)
    monkeypatch.setattr(research,'search',lambda *a:[{'url':s['url']} for s in source])
    monkeypatch.setattr(research,'discover_wikipedia',lambda *a:[])
    monkeypatch.setattr(research,'extract',lambda url:copy.deepcopy(next(s for s in source if s['url']==url)))
    return source


@pytest.mark.parametrize('count',[0,1,2,3])
@pytest.mark.parametrize('mode',['hybrid','strict'])
def test_missing_partial_and_sufficient_sources(tmp_path,monkeypatch,count,mode):
    web_fixture(monkeypatch,count);folder=tmp_path/'research'
    if mode=='strict' and count<3:
        with pytest.raises(ValueError,match='Fonti consultabili insufficienti'):
            research.collect('Test topic',[],{'research_mode':mode},folder,lambda:None,lambda _:None)
    else:
        result=research.collect('Test topic',[],{'research_mode':mode},folder,lambda:None,lambda _:None)
        assert len(result)==count
        assert all(s['url'].startswith('https://museum') for s in result)
    audit=store.read_json(folder/'acquisition.json')
    assert audit['research']['fallback_used']==(mode=='hybrid' and count<3)


def test_network_failures_are_recorded_but_cancellation_is_not_swallowed(tmp_path,monkeypatch):
    def unavailable(*a):raise OSError('Network unavailable fixture')
    monkeypatch.setattr(research,'search',unavailable)
    monkeypatch.setattr(research,'discover_wikipedia',unavailable)
    assert research.collect('Test',[],{},tmp_path,lambda:None,lambda _:None)==[]
    assert len(store.read_json(tmp_path/'acquisition.json')['errors'])==3
    def cancel():raise pipeline.Cancelled()
    with pytest.raises(pipeline.Cancelled):research.collect('Test',[],{},tmp_path,cancel,lambda _:None)


def test_old_settings_get_hybrid_default_and_strict_can_be_saved(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path)
    store.write_json(tmp_path/'settings.json',{'model':'test-only'})
    assert store.settings()['research_mode']=='hybrid'
    assert store.save_settings(Settings(model='test-only',research_mode='strict'))['research_mode']=='strict'


def plan(kind,source_ids):
    outline=dict(title='Prova tecnica della ricerca',short_title='Ricerca',description='Fixture dichiarata.',display_date='Prova',
                 places=[dict(id='a',name='Luogo A',pos=[12,43]),dict(id='b',name='Luogo B',pos=[13,44])],uncertainties=[])
    outline['scenes']=[dict(title=f'Scena {i}',date='Prova',focus=['a','b'],event='Controllo tecnico delle fonti.',
                            source_ids=source_ids if i==0 else [],routes=[],commander_ids=[]) for i in range(3)]
    if kind=='battle':outline.update(factions=['Percorso','Riferimento'],commanders=[],river_names=[])
    else:
        outline.update(documentary_type=kind,historical_period={'start':1400,'end':1500},analysis={},persons=[],entities=[],events=[],visual_layers=[],visual_assets=[])
        for s,t in zip(outline['scenes'],['map_overview','comparison','timeline']):
            s.update(historical_range=[1400,1500],scene_type=t,person_ids=[],event_ids=[],asset_ids=[],territory_ids=[],movements=[])
        outline['scenes'][1]['comparison']=[{'title':'Prima','text':'Primo momento'},{'title':'Dopo','text':'Secondo momento'}]
    narration=[dict(index=i,lines=[('Questa prova controlla il percorso dei dati nello studio locale. '*6).strip()]*2,
                    fact='Prova tecnica dichiarata del generatore.',kicker='Controllo delle informazioni') for i in range(3)]
    return outline,narration


@pytest.mark.parametrize('kind',['battle','cultural_movement'])
@pytest.mark.parametrize('count',[0,1])
def test_resume_failed_research_reaches_delivery_and_preserves_policy(tmp_path,monkeypatch,kind,count):
    """Real collector/compiler/exporter; model and expensive production commands are fixtures."""
    jobs=tmp_path/'jobs';jobs.mkdir()
    for module in (store,runner,pipeline):
        if hasattr(module,'DATA'):monkeypatch.setattr(module,'DATA',tmp_path)
        if hasattr(module,'JOBS'):monkeypatch.setattr(module,'JOBS',jobs)
    store.init();web_fixture(monkeypatch,count)
    outline,narration=plan(kind,['S1'] if count else [])
    seen=[];reviews=[]
    class Model:
        calls=0
        def __init__(self,*a):pass
        def structured(self,system,prompt,schema):
            self.calls+=1;seen.append((system,prompt,schema.__name__))
            assert 'MODALITÀ IBRIDA' in system
            if schema.__name__ in ('Outline','HistoryOutline'):
                assert 'Usa SOLO le fonti fornite' not in prompt
                value=copy.deepcopy(outline)
            elif schema.__name__=='NarrationBatch':value={'scenes':copy.deepcopy(narration)}
            elif schema.__name__=='Review':
                assert 'La mancanza di fonti da sola NON' in prompt
                reviews.append(prompt)
                value={'acceptable':len(reviews)>1,'issues':[] if len(reviews)>1 else ['Correggere un dettaglio: fixture.'],
                       'source_ids':['S1'] if count else [],'summary':'Revisione simulata: nessun modello reale.'}
            else:raise AssertionError(schema)
            return schema.model_validate(value).model_dump()
    monkeypatch.setattr(runner,'LLM',Model)
    p=store.create(ProjectRequest(topic='Test della ricerca',minutes=2,start=False,documentary_type=kind))
    work=jobs/p['id']/'workspace';(work/'engine').mkdir(parents=True)
    (work/'engine/old-marker.txt').write_text('preserve old engine')
    monkeypatch.setattr(runner,'isolate',lambda *a:(work,Path('python')))
    monkeypatch.setattr(runner,'reuse_atlas',lambda *a:True)
    commands=[]
    def command(pid,python,folder,args,*a,**k):
        commands.append(args)
        if args[0]=='documentary.py' and args[1]=='verify':
            store.write_json(work/'output'/('film-'+pid+'_verification')/'report.json',
                             {'video_duration':120,'bytes':0,'sha256':'EXPLICIT_STUB_NOT_VIDEO'})
    monkeypatch.setattr(runner,'run',command)
    cfg=Settings(model='TEST_STUB',pipeline_path=str(CORE),fps=24,research_mode='strict').model_dump()
    runner.FLAGS[p['id']]=threading.Event()
    runner.produce(p['id'],cfg)
    assert 'Fonti consultabili insufficienti' in store.project(p['id'])['error']
    assert not seen and not commands
    cfg['research_mode']='hybrid'
    runner.produce(p['id'],cfg)
    result=store.project(p['id'])
    assert result['status']=='completed',result['error']
    assert len(reviews)==2
    assert result['result']['research']['fallback_used']
    assert list(work.glob('engine-before-hybrid-*/old-marker.txt'))
    pack=store.read_json(next((work/'battles').glob('*/battle.json')))
    assert len(pack['sources'])==count
    assert pack['research']['source_count']==count
    assert pack['scenes'][-1]['evidence_status']=='model_knowledge_unverified'
    if count:assert pack['scenes'][0]['evidence_status']=='external_references_not_independently_verified'
    cp=jobs/p['id']/'checkpoints'
    review=store.read_json(cp/'review.json')
    assert review['independent_historical_verification'] is False
    before=len(seen)
    cfg['research_mode']='strict'
    runner.produce(p['id'],cfg)
    assert len(seen)==before
    assert store.project(p['id'])['result']['research']['mode']=='hybrid'
    # Exercise the real exporter and its archived copies with a measured-shape fixture timeline.
    from engine.history_schema import estimate_timeline
    from engine import export as exporter
    if kind!='battle':timeline=estimate_timeline(pack)
    else:
        timeline=copy.deepcopy(pack);timeline['duration']=120
        for i,s in enumerate(timeline['scenes']):
            s.update(start=i*40,end=(i+1)*40,duration=40,cues=[dict(start=0,end=39,text='Fixture di sottotitoli')])
    monkeypatch.setattr(exporter,'ROOT',work)
    (work/'build'/pack['slug']).mkdir(parents=True,exist_ok=True)
    store.write_json(work/'timeline.json',timeline)
    exporter.export_documents(timeline)
    text=(work/'sources.md').read_text(encoding='utf-8')
    assert 'conoscenza' in text and 'non verificati' in text
    assert 'Ogni scena cita le fonti consultate.' not in text
    if count==0:assert 'Nessuna pagina esterna consultabile' in text and 'https://' not in text
    archive=work/('battles' if kind=='battle' else 'documentaries')/pack['slug']
    assert (archive/'sources.md').read_text(encoding='utf-8')==text
    assert 'VERIFICA DELLE INFORMAZIONI' in (archive/'youtube_description.txt').read_text(encoding='utf-8')


def test_fabricated_references_and_unsupported_charts_still_fail():
    history_tools(str(CORE))
    from engine.history_schema import validate_document
    from engine.research_provenance import apply_context
    outline,narration=plan('cultural_movement',[])
    context=research.assessment([])
    invalid=copy.deepcopy(outline);invalid['scenes'][0]['movements']=[{'sources':['S99']}]
    with pytest.raises(ValueError,match='inesistenti'):validate_references(invalid,[],context)
    with pytest.raises(ValueError,match='mai consultate'):
        annotate_review({'acceptable':True,'source_ids':['S99']},[],context)
    compile=history_tools(str(CORE))[2]
    pack,_=compile(outline,narration,[],{'id':'test','minutes':2},{'research_context':context})
    assert validate_document(pack)
    strict=copy.deepcopy(pack);strict.pop('research')
    with pytest.raises(ValueError,match='Fonti mancanti'):validate_document(strict)
    pack['scenes'][0]['chart']={'kind':'bar','values':[{'label':'Unsupported','value':10}],'sources':[]}
    with pytest.raises(ValueError,match='Fonte mancante'):validate_document(pack)
    with pytest.raises(ValueError,match='grafico quantitativo'):apply_context(pack,context)


def test_upgrade_does_not_replace_authored_or_external_workspaces(tmp_path,monkeypatch):
    jobs=tmp_path/'jobs';work=jobs/'id/workspace';cp=jobs/'id/checkpoints'
    work.mkdir(parents=True);cp.mkdir()
    monkeypatch.setattr(pipeline,'JOBS',jobs)
    (cp/'outline.json').write_text('{}')
    with pytest.raises(ValueError,match='già scene'):pipeline.prepare_hybrid_engine(work,CORE,cp)
    with pytest.raises(ValueError,match='esterno'):pipeline.prepare_hybrid_engine(work,tmp_path/'external',cp)
    assert not (work/'engine').exists()
