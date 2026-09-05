"""Frame generation, resumable per-scene encoding, measured audio and final MP4 mux."""
import subprocess,time,json,hashlib
from pathlib import Path
import cv2
from concurrent.futures import ProcessPoolExecutor
from .common import ROOT,FFMPEG,run_ff,fingerprint,write_json,read_json
from .visuals import Visuals
from .sound import mix_all
from .export import export_documents

def _worker(args):
    return render_scenes(*args,jobs=1)

def render_scenes(timeline,only=None,preview_seconds=None,jobs=2):
    if jobs>1:
        selected=only or [s['id'] for s in timeline['scenes']]
        batches=[selected[k::jobs] for k in range(jobs)]
        batches=[b for b in batches if b]
        with ProcessPoolExecutor(max_workers=len(batches)) as pool:
            results=list(pool.map(_worker,[(timeline,b,preview_seconds) for b in batches]))
        return results[0]
    cv2.setNumThreads(1)
    folder=ROOT/'build'/timeline['slug']/'scenes';folder.mkdir(parents=True,exist_ok=True)
    visual=Visuals(timeline)
    files=['visuals.py','cartography.py','render.py']+(['atlas.py'] if timeline.get('visual_style')=='atlas' else [])
    if timeline.get('visual_style')=='history':files+=['atlas.py','history_visuals.py','history_schema.py','history_profiles.py']
    source=''.join((ROOT/'engine'/f).read_text(encoding='utf-8') for f in files)
    if timeline.get('presentation_mode')=='slides':source+=(ROOT/'engine/slide_visuals.py').read_text(encoding='utf-8')
    # BEGIN H3 IMAGE INSETS
    if timeline.get('user_media'):
        from .image_insets import signature
        source+=(ROOT/'engine/image_insets.py').read_text(encoding='utf-8')+json.dumps(signature(timeline))
    # END H3 IMAGE INSETS
    asset_signature=None
    if timeline.get('presentation_mode')=='slides':
        paths=[p['path'] for p in timeline.get('visual_assets',[]) if p.get('path')]
        asset_signature=[(p,(ROOT/p).stat().st_size,(ROOT/p).stat().st_mtime_ns) for p in paths]
    if timeline.get('visual_style') in ('atlas','history') and timeline.get('presentation_mode')!='slides':
        atlas=read_json(ROOT/timeline['atlas'])
        paths=[timeline['atlas']]+[p for layer in atlas['layers'] for p in layer['levels']]+[layer['alpha'] for layer in atlas['layers'] if 'alpha' in layer]
        asset_signature=[(p,(ROOT/p).stat().st_size,(ROOT/p).stat().st_mtime_ns) for p in paths]
        if timeline.get('visual_style')=='history':
            paths=[p['path'] for p in timeline.get('visual_assets',[])]+[p['portrait'] for p in timeline.get('persons',[]) if p.get('portrait')]
            asset_signature += [(p,(ROOT/p).stat().st_size,(ROOT/p).stat().st_mtime_ns) for p in paths]
    for scene in timeline['scenes']:
        if only is not None and scene['id'] not in only:continue
        output=folder/f'{scene["id"]}.mp4'; manifest=folder/f'{scene["id"]}.render.json'
        frames=min(scene['frames'],round(preview_seconds*timeline['fps'])) if preview_seconds else scene['frames']
        key=fingerprint([scene,timeline['maps'],source,frames,asset_signature])
        if timeline.get('presentation_mode')=='slides':key=fingerprint([key,{k:v for k,v in timeline.items() if k!='scenes'}])
        if timeline.get('visual_style')=='history':key=fingerprint([key,{k:v for k,v in timeline.items() if k!='scenes'}])
        if output.exists() and manifest.exists() and read_json(manifest)['fingerprint']==key:
            print('Cached scene',scene['id'],flush=True);continue
        temp=folder/f'{scene["id"]}.rendering.mp4'
        log=open(folder/f'{scene["id"]}.ffmpeg.log','wb')
        args=[FFMPEG,'-hide_banner','-loglevel','error','-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24',
              '-s','1920x1080','-r',str(timeline['fps']),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','19',
              '-profile:v','high','-level','4.1','-pix_fmt','yuv420p','-threads','2','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709',
              '-vf','scale=out_color_matrix=bt709:out_range=tv','-movflags','+faststart',str(temp)]
        proc=subprocess.Popen(args,stdin=subprocess.PIPE,stderr=log)
        start=time.monotonic()
        try:
            for i in range(frames):
                im=visual.frame(scene,i/timeline['fps'])
                proc.stdin.write(im.tobytes())
                if i and i%(timeline['fps']*10)==0:
                    print(f'Scene {scene["id"]}: {i/frames:.0%} ({i/(time.monotonic()-start):.1f} frames/s)',flush=True)
            proc.stdin.close(); code=proc.wait();log.close()
            if code:raise RuntimeError(f'Encoding failed: scene {scene["id"]}')
            temp.replace(output)
            write_json(manifest,{'fingerprint':key,'frames':frames,'render_seconds':time.monotonic()-start})
            print('Rendered',scene['id'],scene['title'],f'{time.monotonic()-start:.1f}s',flush=True)
        except BaseException:
            if proc.poll() is None:proc.kill();proc.wait()
            log.close();raise
    return folder

def final_encode(timeline):
    work=ROOT/'build'/timeline['slug'];folder=work/'scenes'
    # Refuse partial scene previews, stale frame counts or accidentally missing chapters.
    for s in timeline['scenes']:
        assert (folder/f'{s["id"]}.mp4').exists(),s['id']
        assert read_json(folder/f'{s["id"]}.render.json')['frames']==s['frames'],s['id']
    fullmix=mix_all(timeline); srt,meta=export_documents(timeline)
    concat=work/'scenes.txt'
    concat.write_text('\n'.join("file '"+(folder/f'{s["id"]}.mp4').as_posix()+"'" for s in timeline['scenes'])+'\n',encoding='utf-8')
    joined=work/'picture.mp4'
    run_ff(['-f','concat','-safe','0','-i',concat,'-c','copy',joined])
    # EBU R128 two-pass loudness, preserving the local voice's dynamics.
    print('Measuring final loudness...',flush=True)
    result=subprocess.run([FFMPEG,'-hide_banner','-i',str(fullmix),'-af','loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
    j=result.stderr[result.stderr.rfind('{'):result.stderr.rfind('}')+1]; measured=json.loads(j)
    write_json(work/'loudness-input.json',measured)
    filt=f'loudnorm=I=-16:TP=-1.5:LRA=9:measured_I={measured["input_i"]}:measured_TP={measured["input_tp"]}:measured_LRA={measured["input_lra"]}:measured_thresh={measured["input_thresh"]}:offset={measured["target_offset"]}:linear=true:print_format=summary'
    output=ROOT/timeline['output'];output.parent.mkdir(exist_ok=True,parents=True)
    run_ff(['-i',joined,'-i',fullmix,'-i',srt,'-i',meta,'-map','0:v:0','-map','1:a:0','-map','2:0',
       '-map_metadata','3','-map_chapters','3','-c:v','copy','-c:a','aac','-b:a','256k','-ar','48000','-af',filt,
       '-c:s','mov_text','-metadata:s:a:0','language=ita','-metadata:s:s:0','language=ita','-metadata:s:s:0','title=Italiano',
       '-disposition:s:0','0','-movflags','+faststart','-t',f'{timeline["duration"]:.6f}',output])
    print('FINAL MP4:',output,flush=True)
    return output
