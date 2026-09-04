"""CLI entrypoint; topic-specific content lives entirely in battle packs."""
import argparse,copy,math
from pathlib import Path
from engine.common import ROOT,read_json,write_json,validate_pack

def estimated_timeline(raw,pack):
    """Create a disposable cue grid for visual review before TTS exists."""
    if raw.get('schema_version')==2:
        from engine.history_schema import estimate_timeline
        return estimate_timeline(raw)
    timeline=copy.deepcopy(pack);cursor=0
    for scene in timeline['scenes']:
        offset=.65;cues=[]
        for index,line in enumerate(scene['lines']):
            duration=max(1.2,len(line.split())/(170/60))
            cues.append(dict(index=index,start=offset,end=offset+duration,text=line,spoken=line));offset+=duration+.18
        duration=math.ceil((offset+.85)*timeline['fps'])/timeline['fps']
        scene.update(start=cursor,end=cursor+duration,duration=duration,frames=round(duration*timeline['fps']),cues=cues)
        cursor+=duration
    timeline['duration']=cursor;timeline['timing_status']='estimated'
    return timeline

def main():
    p=argparse.ArgumentParser(description='Generatore locale di documentari storici in italiano')
    p.add_argument('command',choices=['build','assets','voice','render','finalize','verify','preview','validate'])
    p.add_argument('--battle','--document',dest='battle',default='battles/waterloo/battle.json')
    p.add_argument('--scenes',help='Scene IDs separated by commas')
    p.add_argument('--seconds',type=float,help='Short render test; finalizer rejects incomplete scenes')
    p.add_argument('--jobs',type=int,default=2,help='Concurrent scene render processes')
    p.add_argument('--keep-timing',action='store_true',help='Replace voice while preserving an unchanged script and existing cue grid')
    args=p.parse_args();raw=read_json(ROOT/args.battle);pack=validate_pack(raw)
    if args.command=='validate':print('Document pack valid' if pack.get('documentary_schema_version')==2 else 'Battle pack valid');return
    if args.command=='assets':
        if pack.get('documentary_schema_version')==2:
            from engine.history_assets import acquire_history as acquire
        else:
            from engine.acquire import acquire
        acquire(pack);return
    if args.command in ('voice','build'):
        from engine.narration import synthesize
        previous_path=ROOT/'build'/pack['slug']/'timeline.json'
        preserve=args.keep_timing
        if args.command=='build' and previous_path.exists():
            previous=read_json(previous_path)
            same_script=[(s['id'],s['lines']) for s in previous['scenes']]==[(s['id'],s['lines']) for s in pack['scenes']]
            same_target=previous['target_minutes']==pack['target_minutes']
            preserve=preserve or (same_script and same_target)
        timeline=synthesize(pack,keep_timing=preserve)
        if args.command=='voice':return
    else:
        timeline_path=ROOT/'build'/pack['slug']/'timeline.json'
        if args.command=='preview' and not timeline_path.exists():
            timeline=estimated_timeline(raw,pack);write_json(timeline_path,timeline);write_json(ROOT/'timeline.json',timeline)
            print('Anteprima con tempi provvisori; la voce creerà la timeline definitiva.')
        else:timeline=read_json(timeline_path)
    if args.command in ('render','build'):
        from engine.render import render_scenes
        render_scenes(timeline,args.scenes.split(',') if args.scenes else None,args.seconds,jobs=args.jobs)
        if args.command=='render':return
    if args.command in ('finalize','build'):
        from engine.render import final_encode
        final_encode(timeline)
        if args.command=='finalize':return
    if args.command=='preview':
        from engine.visuals import Visuals
        visual=Visuals(timeline);out=ROOT/'build'/pack['slug']/'previews';out.mkdir(exist_ok=True,parents=True)
        for s in timeline['scenes']:
            if args.scenes and s['id'] not in args.scenes.split(','):continue
            for fraction in [.15,.55,.85]:
                visual.frame(s,s['duration']*fraction).save(out/f'{s["id"]}-{fraction}.jpg',quality=92)
        print(out)
    if args.command in ('verify','build'):
        from engine.verify import verify
        verify(timeline)

if __name__=='__main__':main()
