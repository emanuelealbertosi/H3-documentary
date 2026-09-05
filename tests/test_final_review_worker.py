"""Selective rendering tracks programme-wide graphics and immutable inputs."""
import copy
import hashlib
import io
from pathlib import Path

import pytest
from PIL import Image

from app import store, visual_slots
from app.final_review_worker import (render_plan, preserve_external_manifest,
    _geography_covered, install_revision_voice_tools)


def timeline(style='history', sequence=False):
    return {'visual_style':style, 'visual_direction':{'timeline_mode':'sequence' if sequence else 'years'},
            'scenes':[{'id':str(i),'scene_type':'artwork','start':i*3,'end':(i+1)*3,
                       'duration':3,'frames':72,'lines':['Il racconto.']} for i in range(3)]}


def test_image_change_reuses_other_clips():
    old=timeline();new=copy.deepcopy(old)
    new['scenes'][1]['image_insets']=[{'asset_id':'new-image','cue':0}]
    plan=render_plan(old,new,{'1'})
    assert plan['scene_ids']==['1'] and plan['reused_scene_ids']==['0','2']
    assert not plan['timing_changed']


@pytest.mark.parametrize('style,sequence,expected',[
    ('history',False,['0','1','2']),('atlas',False,['0','1','2']),('history',True,['1'])])
def test_longer_narration_updates_dependent_progress_bars(style,sequence,expected):
    old=timeline(style,sequence);new=copy.deepcopy(old)
    new['scenes'][1].update(duration=4,frames=96,end=7)
    new['scenes'][2].update(start=7,end=10)
    plan=render_plan(old,new,{'1'})
    assert plan['scene_ids']==expected and plan['timing_changed']


def test_rebuilt_map_does_not_invalidate_independent_artwork():
    old=timeline();old['scenes'][0]['scene_type']='animated_route'
    old['scenes'][2]['scene_type']='event_focus'
    old['visual_direction']['map_led']=True
    plan=render_plan(old,copy.deepcopy(old),set(),True)
    assert plan['scene_ids']==['0','2'] and plan['reused_scene_ids']==['1']


def test_shared_locator_extent_is_a_real_visual_dependency():
    old=timeline('atlas');old['atlas_locator']=[10,40,20]
    new=copy.deepcopy(old);new['atlas_locator']=[15,40,25]
    assert render_plan(old,new,{'1'})['scene_ids']==['0','1','2']


@pytest.mark.parametrize('change',['order','unknown'])
def test_no_silent_restructure_or_unknown_scene(change):
    old=timeline();new=copy.deepcopy(old)
    if change=='order':new['scenes'].reverse()
    with pytest.raises(ValueError):render_plan(old,new,{'nonexistent'} if change=='unknown' else set())


def test_partial_external_voice_manifest_keeps_untouched_segments(tmp_path):
    path=tmp_path/'external-voice-cache.json'
    before={'backend':'tts_api','synthesis':{'seed':42},'items':{'01:0':{'file':'a.wav'},'02:0':{'file':'b.wav'}}}
    store.write_json(path,{'backend':'tts_api','items':{'02:0':{'file':'corrected.wav'}}})
    preserve_external_manifest(path,before)
    merged=store.read_json(path)
    assert merged['items']=={'01:0':{'file':'a.wav'},'02:0':{'file':'corrected.wav'}}
    assert merged['synthesis']=={'seed':42}


def test_atlas_reuse_requires_both_coverage_and_detail(tmp_path):
    geo={'output':'assets/atlas','bounds':[-20,20,40,60],'terrain_zoom':8,
         'patches':{'detail':{'bounds':[0,30,20,50],'zoom':9}}}
    store.write_json(tmp_path/'assets/atlas/atlas.json',{'layers':[{'levels':['raster.npy']}]})
    (tmp_path/'raster.npy').write_bytes(b'private raster fixture')
    new=copy.deepcopy(geo);new['bounds']=[-10,25,30,55]
    new['patches']['detail']['bounds']=[5,35,10,40]
    assert _geography_covered(tmp_path,new,geo)
    new['patches']['detail']['zoom']=10
    assert not _geography_covered(tmp_path,new,geo)
    new['patches']['detail']['zoom']=9;new['bounds'][0]=-30
    assert not _geography_covered(tmp_path,new,geo)
    (tmp_path/'raster.npy').unlink()
    assert not _geography_covered(tmp_path,geo,geo)


def test_old_workspace_gets_subset_voice_support_and_retains_renderer(tmp_path):
    engine=tmp_path/'engine';engine.mkdir()
    (engine/'narration.py').write_text('old full-film-only narration',encoding='utf-8')
    (engine/'render.py').write_bytes(b'old renderer must remain byte identical')
    before=(engine/'render.py').read_bytes()
    install_revision_voice_tools(tmp_path)
    assert (engine/'render.py').read_bytes()==before
    assert (engine/'voice_delivery.py').is_file()
    assert 'manual_narration' in (engine/'narration.py').read_text(encoding='utf-8')
    assert (tmp_path/'tools/revise_narration.py').is_file()


def test_visual_replacement_uses_frozen_bytes_after_live_library_changes(tmp_path,monkeypatch):
    def png(color):
        out=io.BytesIO();Image.new('RGB',(40,40),color).save(out,format='PNG');return out.getvalue()
    frozen=tmp_path/'snapshot';live=tmp_path/'live';work=tmp_path/'work'
    for folder,data in ((frozen,png('red')),(live,png('blue'))):
        (folder/'abc').mkdir(parents=True);(folder/'abc/image.png').write_bytes(data)
    monkeypatch.setattr(visual_slots.media,'folder',lambda ident:live/ident)
    data=(frozen/'abc/image.png').read_bytes()
    item={'id':'abc','image_sha256':hashlib.sha256(data).hexdigest(),'title':'Dipinto'}
    slot={'path':'assets/paint.png'}
    target,_=visual_slots._copy_replacement(item,slot,work,media_root=frozen)
    assert target.read_bytes()==data and target.read_bytes()!=(live/'abc/image.png').read_bytes()
    with pytest.raises(ValueError):visual_slots._replacement_folder('../outside',frozen)
