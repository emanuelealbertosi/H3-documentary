"""CLI entrypoint; topic-specific content lives entirely in battle packs."""
import argparse
from pathlib import Path
from engine.common import ROOT,read_json,validate_pack

def main():
    p=argparse.ArgumentParser(description='Generatore locale di documentari storici in italiano')
    p.add_argument('command',choices=['build','assets','voice','render','finalize','verify','preview','validate'])
    p.add_argument('--battle','--document',dest='battle',default='battles/waterloo/battle.json')
    p.add_argument('--scenes',help='Scene IDs separated by commas')
    p.add_argument('--seconds',type=float,help='Short render test; finalizer rejects incomplete scenes')
    p.add_argument('--jobs',type=int,default=2,help='Concurrent scene render processes')
    p.add_argument('--keep-timing',action='store_true',help='Replace voice while preserving an unchanged script and existing cue grid')
    args=p.parse_args();pack=validate_pack(read_json(ROOT/args.battle))
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
    else:timeline=read_json(ROOT/'build'/pack['slug']/'timeline.json')
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
            for fraction in [.15,.55,.85]:
                visual.frame(s,s['duration']*fraction).save(out/f'{s["id"]}-{fraction}.jpg',quality=92)
        print(out)
    if args.command in ('verify','build'):
        from engine.verify import verify
        verify(timeline)

if __name__=='__main__':main()
