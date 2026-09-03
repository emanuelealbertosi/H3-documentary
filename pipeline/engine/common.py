from pathlib import Path
import json, subprocess, hashlib
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
FFMPEG=imageio_ffmpeg.get_ffmpeg_exe()

def read_json(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write_json(p,data):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def fingerprint(data): return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def run_ff(args,**kw):
    return subprocess.run([FFMPEG,'-hide_banner','-loglevel','error','-y',*map(str,args)],check=True,**kw)
def stamp(seconds,millis=False):
    n=round(seconds*1000); h=n//3600000; m=(n//60000)%60; s=(n//1000)%60
    return f'{h:02}:{m:02}:{s:02}'+(f',{n%1000:03}' if millis else '')

def validate_pack(p):
    if p.get('schema_version')==2:
        from .history_schema import adapt
        p=adapt(p)
    for k in ['schema_version','slug','scenes','maps','commanders','sources','voice']: assert k in p,k
    assert p['schema_version']==1
    assert p['width']==1920 and p['height']==1080
    ids=[s['id'] for s in p['scenes']]; assert len(set(ids))==len(ids)
    source_ids={x['id'] for x in p['sources']}
    for s in p['scenes']:
        assert s['lines'] and s['map'] in p['maps']
        assert set(s['sources'])<=source_ids
        for key in ['arrows','commanders','sfx','focus']:
            for a in s[key]: assert 0<=a.get('cue',0)<len(s['lines']),(s['id'],a)
        for a in s['commanders']: assert a['id'] in p['commanders']
        for c in ['camera_start','camera_end']: assert s[c][2]>0
    return p
