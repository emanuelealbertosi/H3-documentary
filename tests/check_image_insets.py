"""Run with the pipeline Python inside an isolated test workspace."""
import sys,copy,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from engine.common import ROOT,read_json,write_json
from engine.visuals import Visuals
from engine.image_insets import interval,rectangle,signature

t=read_json(ROOT/'build/demo-riquadri/timeline.json');s=t['scenes'][0]
base=copy.deepcopy(t);base.pop('user_media');base['scenes'][0].pop('image_insets')
wrapped=Visuals(t);plain=Visuals(base)
assert np.array_equal(np.asarray(wrapped.frame(s,.25)),np.asarray(plain.frame(s,.25)))
out=ROOT/'output/inset-checks';out.mkdir(parents=True,exist_ok=True)
for i,item in enumerate(s['image_insets']):
    a,b=interval(s,item);time=(a+b)/2
    overlay=wrapped.frame(s,time);reference=plain.frame(s,time)
    x,y,w,h=rectangle(item['layout']);diff=np.any(np.asarray(overlay)!=np.asarray(reference),axis=2)
    assert diff[y:y+h,x:x+w].sum()>w*h*.5
    diff[y:y+h,x:x+w]=False;assert not diff.any(),'Existing map changed outside inset'
    assert np.array_equal(np.asarray(overlay),np.asarray(wrapped.frame(s,time))),'Non-deterministic flicker'
    overlay.save(out/f'{i+1}-inset.jpg',quality=94)
# The same wrapper covers map and non-map historical scenes.
history=copy.deepcopy(t);history.update(visual_style='history',events=[],persons=[],visual_assets=[],visual_layers=[],historical_period={'start':1,'end':2})
hs=history['scenes'][0];hs.update(historical_range=[1,2],scene_type='map_overview',movements=[],territory_ids=[],location_ids=[])
for scene_type in ['map_overview','summary']:
    hs['scene_type']=scene_type
    v=Visuals(history);a,b=interval(hs,hs['image_insets'][0]);frame=v.frame(hs,(a+b)/2)
    reference=v.base.frame(hs,(a+b)/2)
    assert np.array_equal(np.asarray(frame)[:165],np.asarray(reference)[:165]),'History header changed'
    assert np.array_equal(np.asarray(frame)[938:],np.asarray(reference)[938:]),'History chronology changed'
    frame.save(out/f'history-{scene_type}.jpg',quality=94)
write_json(out/'checks.json',{'unchanged_outside_inset':True,'same_time_identical_pixels':True,'no_inset_before_cue':True,'modes':['atlas','history map','history summary'],'image_slots':3})
print('Inset checks passed: unchanged maps, measured cues, deterministic frames and history modes.',flush=True)
