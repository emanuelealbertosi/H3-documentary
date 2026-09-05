"""Slide mode stays orthogonal to history types and preserves legacy layouts."""
import copy,io
from pathlib import Path
import pytest
from PIL import Image,ImageDraw
from app import media,store,visual_slots
from app.models import ProjectRequest
from pipeline.engine import slide_visuals
from pipeline.engine.history_direction import direction_for,direction_prompt,require_coverage
from pipeline.engine.history_schema import adapt
from pipeline.engine.still_render import workspace_context,StillRenderer
from pipeline.engine.visuals import Visuals

@pytest.fixture
def project(tmp_path,monkeypatch):
    (tmp_path/'jobs').mkdir()
    monkeypatch.setattr(store,'DATA',tmp_path);monkeypatch.setattr(store,'JOBS',tmp_path/'jobs');store.init()
    p=store.create(ProjectRequest(topic='Prova slide senza mappa',start=False,presentation_mode='slides'))
    work=store.JOBS/p['id']/'workspace';path=work/'documentaries/slides/documentary.json';path.parent.mkdir(parents=True)
    raw={'schema_version':2,'documentary_type':'exploration','presentation_mode':'slides','slug':'slides','title':'Prova slide',
         'historical_period':{'start':1400,'end':1500},'locations':[{'id':'ovest','name':'Ovest','pos':[-170,30]},{'id':'est','name':'Est','pos':[170,30]}],
         'persons':[],'sources':[{'id':'qa','title':'Fixture QA','url':'https://example.test/qa','use':'Collaudo'}],'visual_assets':[],'scenes':[{'id':f'{i:02}','title':f'Slide {i}',
         'scene_type':'event_focus','lines':['Testo della slide.'],'location_ids':[],'sources':['qa'],'historical_range':[1450,1450]} for i in range(1,3)]}
    visual_slots.materialize(raw,work,[]);store.write_json(path,raw);store.update(p['id'],status='review',review_visuals=True)
    return p,work,path,raw

def test_mode_persists_and_clone_keeps_it(project):
    p,_,_,_=project
    assert store.project(p['id'])['presentation_mode']=='slides'
    store.update(p['id'],status='completed')
    cloned=store.clone_completed(p['id'])
    assert cloned['presentation_mode']=='slides'
    assert ProjectRequest(topic='Vecchia battaglia').presentation_mode=='map'

def test_legacy_layout_is_byte_shape_compatible():
    assert media.Layout().model_dump()=={'x':.71,'y':.21,'width':.25,'fit':'contain'}
    with pytest.raises(ValueError):media.Layout.model_validate({'slide':{'effect':'execute'}})
    with pytest.raises(ValueError):media.Layout.model_validate({'slide':{'width':float('nan')}})

def test_journey_slides_do_not_require_maps():
    d=direction_for('Viaggio di Ulisse','exploration','literary_tradition','slides')
    assert not d['map_led'] and not d['journey'] and 'SENZA MAPPA' in direction_prompt(d)
    assert require_coverage({'visual_direction':d,'scenes':[{'scene_type':'event_focus'}]})['passed']
    assert direction_for('Viaggio di Ulisse','exploration')['journey']

def test_every_scene_has_background_even_battle(project):
    _,_,_,raw=project
    backgrounds=[s for s in visual_slots.derive(raw) if s['source_type']=='scene_background']
    assert len(backgrounds)==2 and all(s['enabled'] and s['required'] for s in backgrounds)
    battle={**raw,'schema_version':1,'documentary_type':'battle','commanders':{},'places':{}}
    assert len([s for s in visual_slots.derive(battle) if s['source_type']=='scene_background'])==2
    assert len([s for s in visual_slots.derive({**battle,'presentation_mode':'map'}) if s['source_type']=='scene_background'])==0

def test_layout_survives_replacement_and_targets_one_scene(project):
    p,work,path,raw=project
    layout=media.Layout(slide=media.SlideComposition(mode='box',effect='scroll_left',fade=True)).model_dump()
    visual_slots.set_layout(p['id'],'visual-background-01',layout)
    visual_slots.apply_options(raw,visual_slots.options(p['id']),visual_slots.layout_options(p['id']))
    buf=io.BytesIO();Image.new('RGB',(300,200),'gold').save(buf,format='PNG')
    upload=media.upload(buf.getvalue(),'prova.png')
    record=media.save(upload['id'],media.MediaEdit(title='Sfondo QA',rights='CC0',bindings=[{'kind':'scene','label':'Slide 1'}]))
    changed=visual_slots.materialize(raw,work,[record],replacements_only=True)
    entry=next(m for m in raw['user_media'] if m['id']=='visual-background-01')
    assert entry['layout']==layout and changed==['01']
    store.write_json(path,raw)
    assert visual_slots.status(p['id'])['presentation_mode']=='slides'
    assert next(s for s in visual_slots.status(p['id'])['slots'] if s['id']==entry['id'])['layout']==layout

@pytest.mark.parametrize('mode',['box','fullscreen','inset'])
def test_placement_stays_on_canvas(mode):
    layout=media.Layout(slide=media.SlideComposition(mode=mode,x=.95,y=.95,width=.8,height=.8)).model_dump()
    x,y,w,h=slide_visuals.placement(layout)
    assert 0<=x<x+w<=1920 and 0<=y<y+h<=1080

def test_effects_are_deterministic_and_bounded():
    for effect in ['fixed','zoom_in','zoom_out','scroll_left','scroll_right','scroll_up','scroll_down']:
        start=slide_visuals.motion({'effect':effect,'fade':True},0,0,4)
        end=slide_visuals.motion({'effect':effect,'fade':True},1,4,4)
        assert start[-1]==end[-1]==0
        assert start==slide_visuals.motion({'effect':effect,'fade':True},0,0,4)
        assert 1<=start[0]<=1.12 and 1<=end[0]<=1.12
        if effect!='fixed':assert start!=end

def test_manual_thumbnail_layout_changes_only_its_scene(project):
    _,work,_,raw=project
    layout=media.Layout(slide=media.SlideComposition(mode='box',effect='zoom_in')).model_dump()
    raw['user_media'].append({'id':'uploaded','title':'Immagine','path':'assets/user/test.png','layout':media.Layout().model_dump(),'bindings':[],'rights':'CC0'})
    raw['scenes'][0]['image_insets']=[{'asset_id':'uploaded','cue':0,'layout':media.Layout().model_dump()}]
    visual_slots.apply_options(raw,{}, {'visual-media-uploaded':layout})
    assert raw['user_media'][-1]['layout']==layout
    assert raw['scenes'][0]['image_insets'][0]['layout']==layout
    assert raw['_pending_visual_layout_scenes']==['01']

def test_slide_compilers_omit_geographic_downloads(project):
    from app.compiler import compile_pack
    from pipeline.engine.history_authoring import compile_outline
    _,_,_,raw=project
    narration=[{'index':i,'lines':['Parola '*85,'Storia '*85],'fact':'Collaudo','kicker':'Prova'} for i in range(3)]
    sources=[{**s,'retrieved':'2026-09-05'} for s in raw['sources']]
    outline={'title':'Prova','short_title':'Prova','description':'Collaudo','display_date':'1450','factions':['A','B'],
        'places':raw['locations'],'commanders':[],'scenes':[{'title':f'Scena {i}','date':'1450','event':'Evento',
          'focus':['ovest','est'],'source_ids':['qa'],'routes':[],'commander_ids':[]} for i in range(3)]}
    req={'id':'qa','minutes':3,'topic':'Viaggio di prova','presentation_mode':'slides'}
    battle,geo=compile_pack(outline,narration,sources,req,{'fps':24})
    assert battle['presentation_mode']=='slides' and geo=={}
    historical={**outline,'documentary_type':'exploration','historical_period':raw['historical_period'],'persons':[],
        'scenes':[{**s,'scene_type':'event_focus','historical_range':[1450,1450]} for s in outline['scenes']]}
    general,geo=compile_outline(historical,narration,sources,req,{'fps':24})
    assert general['presentation_mode']=='slides' and geo=={}
    assert not general['visual_direction']['map_led']
    with pytest.raises(ValueError):compile_pack(outline,narration,sources,{**req,'presentation_mode':'map'},{'fps':24})

def test_slide_revision_keeps_unaffected_clips_when_timing_changes():
    from app.final_review_worker import render_plan
    previous={'presentation_mode':'slides','scenes':[{'id':'01','start':0,'end':4,'duration':4,'frames':48},
        {'id':'02','start':4,'end':8,'duration':4,'frames':48}]}
    current=copy.deepcopy(previous);current['scenes'][0].update(end=5,duration=5,frames=60);current['scenes'][1].update(start=5,end=9)
    plan=render_plan(previous,current,['01'])
    assert plan['scene_ids']==['01'] and plan['reused_scene_ids']==['02']

def test_renderer_and_pdf_work_without_atlas(project):
    _,work,_,raw=project
    # Use shipped fonts read-only; no cartographic files exist in this fixture.
    import shutil
    source=Path(__file__).resolve().parents[1]/'pipeline/assets/fonts'
    shutil.copytree(source,work/'assets/fonts')
    pack=adapt(raw);pack.update(duration=8,fps=12)
    for i,s in enumerate(pack['scenes']):s.update(duration=4,start=i*4,end=i*4+4,cues=[{'start':0,'end':4,'text':s['lines'][0]}])
    with workspace_context(work):
        renderer=Visuals(pack);assert isinstance(renderer,slide_visuals.SlideVisuals)
        first=renderer.frame(pack['scenes'][0],2)
        assert first.size==(1920,1080) and first.getpixel((300,500))==(0,0,0)
        assert first.tobytes()==renderer.frame(pack['scenes'][0],2).tobytes()
        still=StillRenderer(pack,work,work/'output/presentations/cache')
        assert still.frame({'scene_id':'01','cue_index':0,'phase':'end','time':2}).size==(1920,1080)
    assert not (work/'assets/geography').exists()
