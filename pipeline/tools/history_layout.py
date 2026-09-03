"""Preflight generic scene focus: geography, text budget, source-linked visual data."""
import sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.common import ROOT,read_json,write_json,validate_pack
from engine.atlas import camera,screen,merc
from engine.history_visuals import NONMAP

def main():
    raw=read_json(ROOT/sys.argv[1]);pack=validate_pack(raw)
    path=ROOT/'build'/pack['slug']/'timeline.json';timeline=read_json(path);report=[];repairs=[];previous=None
    for s in timeline['scenes']:
        if s['scene_type'] in NONMAP:continue
        # Allow transitions to traverse locations; require the settled framing to show focus.
        cam=camera(s,s['duration']*.65)
        places=[timeline['places'][pid]['pos'] for pid in s.get('location_ids',[])]
        bad=any(not (90<screen(p,cam)[0]<1830 and 190<screen(p,cam)[1]<745) for p in places)
        if bad and places:
            xs=[p[0] for p in places];ys=[merc(p[1]) for p in places]
            width=max(s['camera_end'][2],(max(xs)-min(xs))*1920/1550,(max(ys)-min(ys))*1920/460,6)
            cy=(max(ys)+min(ys))/2-70*width/1920
            view=[(min(xs)+max(xs))/2,math.degrees(math.atan(math.sinh(math.radians(cy)))),width]
            s['camera_end']=view;s['camera_keys']=[{'at':0,'view':s['camera_start']},{'at':.30,'view':view},{'at':1,'view':view}]
            repairs.append({'scene':s['id'],'camera_end':view});cam=camera(s,s['duration']*.65)
        if previous is not None:
            s['camera_start']=previous;s['camera_keys'][0]['view']=previous
        previous=s['camera_end']
        authored=next(x for x in raw['scenes'] if x['id']==s['id'])
        for key in ['camera_start','camera_end','camera_keys']:authored[key]=s[key]
        for pid in s.get('location_ids',[]):
            p=timeline['places'][pid];x,y=screen(p['pos'],cam)
            report.append({'scene':s['id'],'place':pid,'x':round(x),'y':round(y),'visible':bool(60<x<1860 and 175<y<900)})
    bad=[r for r in report if not r['visible']]
    write_json(path.parent/'history-layout.json',{'focus':report,'outside':bad,'repairs':repairs})
    if bad:raise ValueError('Inquadrature focali da correggere: '+str(bad))
    write_json(ROOT/sys.argv[1],raw);write_json(path,timeline);write_json(ROOT/'timeline.json',timeline)
    print('Fuochi geografici verificati; layout fisso, nessun riposizionamento per fotogramma.')

if __name__=='__main__':main()
