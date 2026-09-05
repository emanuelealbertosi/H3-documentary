"""Offline PDF planning, immutable still views and readable complete-text export."""
import copy,json,sys
from pathlib import Path

import pytest

PIPELINE=Path(__file__).resolve().parents[1]/'pipeline'
sys.path.insert(0,str(PIPELINE))
from engine.presentation_plan import plan_pages,load_timeline
from engine.still_render import prepare_scene,output_path,workspace_context


def timeline():
    return {'slug':'presentation-test','title':'Presentazione di collaudo','duration':5,'visual_style':'history',
        'places':{'a':{'pos':[10,40]},'b':{'pos':[11,41]},'c':{'pos':[12,42]}},
        'sources':[{'id':'S1','title':'Fonte della fixture','url':'https://example.test/source','use':'Collaudo'}],
        'scenes':[{'id':'01','title':'Una sequenza di prova','date':'Periodo della fixture','historical_range':[1500,1500],
            'start':0,'end':5,'duration':5,'location_ids':['a','b'],'sources':['S1'],
            'camera_start':[10,40,6],'camera_end':[11,41,6],
            'movements':[{'cue':0,'points':[[10,40],[11,41]],'semantic':'journey'},
                         {'cue':1,'points':[[11,41],[12,42]],'semantic':'journey'}],
            'cues':[{'start':.65,'end':1.1,'text':'Prima frase approvata.','spoken':'Testo fonetico da non esportare.'},
                    {'start':1.3,'end':4.1,'text':'Seconda frase approvata.'}],
            'image_insets':[{'asset_id':'uno','cue':0,'slot':0,'slots':2,'layout':{'x':.71,'width':.25}},
                            {'asset_id':'due','cue':0,'slot':1,'slots':2,'layout':{'x':.71,'width':.25}}]}]}


def test_compact_is_one_visual_per_scene_and_preserves_all_text():
    data=timeline();before=copy.deepcopy(data);pages=plan_pages(data)
    assert len(pages)==1 and pages[0]['time']==5
    assert pages[0]['text']=='Prima frase approvata.\n\nSeconda frase approvata.'
    assert data==before
    assert plan_pages(data,narration='none')[0]['text']==''


def test_teaching_uses_cue_route_endpoints_and_alternating_images_once():
    data=timeline();pages=plan_pages(data,'teaching')
    assert len(pages)==5
    assert [p['phase'] for p in pages]==['start','end','end','start','end']
    assert [p['inset_asset_id'] for p in pages[:3]]==['uno','uno','due']
    combined='\n'.join(p['text'] for p in pages)
    assert combined.count('Prima frase approvata.')==1 and combined.count('Seconda frase approvata.')==1
    with pytest.raises(ValueError,match='Nessun testo'):plan_pages(data,'teaching',max_visual_pages=2)


def test_still_view_hides_future_routes_completes_current_and_keeps_coordinates():
    data=timeline();before=copy.deepcopy(data)
    pages=plan_pages(data,'teaching');view=prepare_scene(data,data['scenes'][0],pages[1])
    assert len(view['movements'])==1 and view['movements'][0]['_still_progress']==1
    assert view['movements'][0]['points']==before['scenes'][0]['movements'][0]['points']
    assert view['image_insets'][0]['asset_id']=='uno' and len(view['image_insets'])==1
    assert view['historical_range']==before['scenes'][0]['historical_range'] and data==before
    start=prepare_scene(data,data['scenes'][0],pages[0])
    assert start['movements'][0]['_still_progress']==0


def test_short_cue_reaches_destination_in_still_without_changing_video_progress():
    from engine.atlas import progress
    from engine.visuals import cue_progress
    data=timeline();scene=data['scenes'][0];item=scene['movements'][0]
    assert progress(scene,item,1.09)<1 and cue_progress(scene,item,1.09)<1
    view=prepare_scene(data,scene,plan_pages(data,'teaching')[1])
    assert progress(view,view['movements'][0],1.09)==1
    assert cue_progress(view,view['movements'][0],1.09)==1


def test_export_paths_and_workspace_roots_are_scoped_and_restored(tmp_path):
    from engine import common,visuals,atlas,image_insets
    modules=[common,visuals,atlas,image_insets];before=[m.ROOT for m in modules]
    with pytest.raises(RuntimeError):
        with workspace_context(tmp_path):
            assert all(m.ROOT==tmp_path.resolve() for m in modules)
            raise RuntimeError('Fixture interruption')
    assert [m.ROOT for m in modules]==before
    with pytest.raises(ValueError):output_path(tmp_path,tmp_path/'elsewhere.pdf','.pdf')
    with pytest.raises(ValueError):output_path(tmp_path,'output/presentations/a.pdf','.pdf')
    path=tmp_path/'output/presentations/a.pdf'
    assert output_path(tmp_path,path,'.pdf')==path


def test_single_city_does_not_overzoom_beyond_approved_map():
    data=timeline();scene=data['scenes'][0]
    scene.update(location_ids=['a'],movements=[],image_insets=[])
    view=prepare_scene(data,scene,plan_pages(data)[0])
    assert view['camera_end'][2]>=6


def test_unused_or_disabled_missing_art_does_not_block_pdf(tmp_path,monkeypatch):
    from engine import visuals
    from engine.still_render import StillRenderer
    data=timeline();data['scenes'][0]['asset_ids']=['off']
    data['scenes'][0]['image_insets']=[]
    data['visual_assets']=[{'id':'off','path':'assets/off.jpg'},{'id':'unused','path':'assets/unused.jpg'}]
    data['user_media']=[{'id':'unused','path':'assets/unused.jpg'}]
    data['disabled_visual_asset_ids']=['off']
    monkeypatch.setattr(visuals,'Visuals',lambda data:object())
    StillRenderer(data,tmp_path,tmp_path/'frames')
    data['disabled_visual_asset_ids']=[]
    with pytest.raises(ValueError,match='non disponibile'):StillRenderer(data,tmp_path,tmp_path/'frames')


def test_timeline_reader_uses_existing_cues_without_generating_timing(tmp_path):
    data=timeline();path=tmp_path/'build/presentation-test/timeline.json';path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data),encoding='utf-8');before=path.read_bytes()
    loaded,source=load_timeline(tmp_path)
    assert loaded==data and source==path and path.read_bytes()==before
    assert not (tmp_path/'timeline.json').exists()


def test_pdf_has_selectable_complete_text_and_keeps_project_files(tmp_path):
    pytest.importorskip('reportlab');pypdf=pytest.importorskip('pypdf')
    from PIL import Image,ImageDraw
    from engine.presentation_pdf import export_presentation
    work=tmp_path/'workspace';font=work/'assets/fonts/Manrope[wght].ttf';font.parent.mkdir(parents=True)
    font.write_bytes((PIPELINE/'assets/fonts/Manrope[wght].ttf').read_bytes())
    data=timeline();text=' '.join(f'Parola{i:04}' for i in range(550))+' Città, perché, più.'
    data['scenes'][0]['cues'][0]['text']=text
    source=work/'timeline.json';source.write_text(json.dumps(data),encoding='utf-8')
    credits=work/'credits.md';credits.write_text('Credito conservato · Autore fixture · CC BY-NC-SA 4.0',encoding='utf-8')
    before={p:p.read_bytes() for p in (source,font,credits)}
    class FixtureRenderer:
        def __init__(self,*args):pass
        def frame(self,page):
            image=Image.new('RGB',(1920,1080),'#23464C');draw=ImageDraw.Draw(image)
            draw.line((50,50,1870,1030),fill='gold',width=12);return image
    output=work/'output/presentations/fixture.pdf'
    result=export_presentation(work,output,renderer_factory=FixtureRenderer)
    reader=pypdf.PdfReader(output);extracted='\n'.join(page.extract_text() for page in reader.pages)
    assert len(reader.pages)==result['pages'] and result['visual_pages']==1 and result['pages']>3
    assert all(f'Parola{i:04}' in extracted for i in range(550))
    assert 'Città, perché, più.' in extracted and 'Seconda frase approvata.' in extracted
    assert 'Testo fonetico da non esportare' not in extracted
    assert 'CC BY-NC-SA 4.0' in extracted and 'Fonte della fixture' in extracted
    assert all(p.read_bytes()==raw for p,raw in before.items())
    with pytest.raises(ValueError,match='esiste già'):export_presentation(work,output,renderer_factory=FixtureRenderer)
