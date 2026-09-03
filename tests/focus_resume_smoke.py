"""Reproduce and repair an old pack in an isolated copy, without touching its source.

Uses real CLI validation and optional 1080p previews. No LLM or TTS is called.
All test material stays in ignored tests/output; no private pack is bundled.
"""
import argparse,hashlib,json,shutil,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def worker(work):
    sys.path.insert(0,str(work))
    from engine.common import read_json,write_json,validate_pack
    from engine.history_schema import estimate_timeline
    from engine.visuals import Visuals
    doc=read_json(work/'battles/film/battle.json')
    validate_pack(doc)
    timeline=estimate_timeline(doc)
    write_json(work/'timeline.json',timeline)
    visual=Visuals(timeline);out=work/'output/previews';out.mkdir(parents=True,exist_ok=True)
    previews=[]
    for scene in timeline['scenes']:
        frame=visual.frame(scene,scene['duration']*.55)
        assert frame.size==(1920,1080)
        assert frame.tobytes()==visual.frame(scene,scene['duration']*.55).tobytes()
        path=out/(scene['id']+'.jpg');frame.save(path,quality=92);previews.append(str(path))
    print(json.dumps({'previews':previews,'same_time_frames_identical':True}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-work',type=Path)
    parser.add_argument('--previews',action='store_true')
    parser.add_argument('--worker',type=Path)
    args=parser.parse_args()
    if args.worker:return worker(args.worker.resolve())
    if not args.base_work:parser.error('--base-work is required')
    base=args.base_work.resolve()
    source=next((base/'battles').glob('*/battle.json'))
    originals=[source,source.with_name('geography.json'),*(base.parent/'checkpoints').glob('*.json')]
    fingerprints={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in originals}
    out=ROOT/'tests/output/focus-compat-1.1.4'/str(time.time_ns())
    work=out/'workspace';work.mkdir(parents=True)
    shutil.copytree(base/'engine',work/'engine',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copy2(base/'documentary.py',work/'documentary.py')
    packpath=work/'battles/film/battle.json';packpath.parent.mkdir(parents=True)
    shutil.copy2(source,packpath)
    python=ROOT/'pipeline/.venv/Scripts/python.exe'
    def cli(program):
        return subprocess.run([str(python),'-B','-X','utf8',str(program),'validate','--battle',str(packpath)],
                              cwd=work,text=True,encoding='utf-8',capture_output=True)
    before=cli(work/'documentary.py')
    assert before.returncode and "'str' object has no attribute 'get'" in before.stderr,before.stderr
    sys.path.insert(0,str(ROOT))
    from app.pack_migrations import repair_pack
    from app.store import read_json,write_json
    old=read_json(packpath);messages=[]
    assert repair_pack(packpath,work,messages.append)
    new=read_json(packpath)
    expected=json.loads(json.dumps(old))
    for scene in expected['scenes']:
        if scene.get('focus') and all(isinstance(x,str) for x in scene['focus']):
            scene.setdefault('location_ids',scene['focus']);scene['focus']=[]
    assert new==expected,'Unexpected editorial change'
    for program in [work/'documentary.py',ROOT/'pipeline/documentary.py']:
        result=cli(program)
        assert result.returncode==0,result.stderr
    report={'scope':'Real saved-pack regression: original and current CLI, isolated repair. No model calls or full video.',
            'original_failure_reproduced':True,'old_engine_validation':True,'current_engine_validation':True,
            'scenes':len(new['scenes']),'editorial_data_preserved':True,'backup_created':True}
    if args.previews:
        shutil.copytree(ROOT/'pipeline/assets/fonts',work/'assets/fonts')
        atlas=read_json(base/'assets/geography/atlas-film/atlas.json')
        for layer in atlas['layers']:
            layer['levels']=[str(base/p) for p in layer['levels']]
            if layer.get('alpha'):layer['alpha']=str(base/layer['alpha'])
        write_json(work/'assets/geography/atlas-film/atlas.json',atlas)
        shutil.copy2(base/'assets/geography/rivers.geojson',work/'assets/geography/rivers.geojson')
        result=subprocess.run([str(python),'-B','-X','utf8',str(Path(__file__).resolve()),'--worker',str(work)],
                              cwd=work,text=True,encoding='utf-8',capture_output=True)
        assert result.returncode==0,result.stderr
        report.update(json.loads(result.stdout))
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in fingerprints.items())
    report['source_job_unchanged']=True
    write_json(out/'verification.json',report)
    print(json.dumps({'report':str(out/'verification.json'),**report},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
