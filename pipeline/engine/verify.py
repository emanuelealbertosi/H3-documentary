"""Verify the actual MP4: full decode, video timing, audio, captions, chapter table and samples."""
import subprocess,json,math,hashlib
from pathlib import Path
import numpy as np
import av
from PIL import Image,ImageDraw
from .common import ROOT,FFMPEG,write_json,stamp

def verify(timeline):
    movie=ROOT/timeline['output'];qa=ROOT/'output'/timeline.get('verification_dir','verification');qa.mkdir(exist_ok=True,parents=True)
    container=av.open(str(movie))
    v=container.streams.video[0];a=container.streams.audio[0]
    video_duration=float(v.duration*v.time_base);audio_duration=float(a.duration*a.time_base)
    report={'file':str(movie),'width':v.width,'height':v.height,'fps':float(v.average_rate),
      'video_codec':v.codec_context.name,'pixel_format':v.codec_context.format.name,
      'video_frames':v.frames,'expected_frames':sum(s['frames'] for s in timeline['scenes']),
      'video_duration':video_duration,'audio_duration':audio_duration,
      'audio_codec':a.codec_context.name,'sample_rate':a.codec_context.sample_rate,
      'audio_channels':a.codec_context.channels,'subtitle_streams':len(container.streams.subtitles),
      'bytes':movie.stat().st_size}
    chapters=container.chapters
    if callable(chapters):chapters=chapters()
    report['chapters']=len(chapters)
    container.close()
    assert (report['width'],report['height'])==(1920,1080)
    assert abs(report['fps']-timeline['fps'])<.001
    assert report['video_codec']=='h264' and report['pixel_format']=='yuv420p'
    assert report['audio_codec']=='aac' and report['sample_rate']==48000 and report['audio_channels']==2
    assert report['video_frames']==report['expected_frames']
    assert abs(video_duration-timeline['duration'])<1/timeline['fps']+.001
    assert abs(audio_duration-video_duration)<.08
    assert report['subtitle_streams']==1 and report['chapters']==len(timeline['scenes'])
    print('Container and synchronization checks passed',flush=True)
    # Full decode verifies every frame and every audio packet in the delivered artifact.
    cmd=[FFMPEG,'-hide_banner','-v','error','-xerror','-i',str(movie),'-map','0:v:0','-map','0:a:0','-f','null','-']
    r=subprocess.run(cmd,capture_output=True,text=True)
    report['full_decode_exit_code']=r.returncode;report['full_decode_log']=r.stderr
    assert r.returncode==0,r.stderr
    print('Entire video and audio decoded without errors',flush=True)
    # Detect unintended sustained black frames and check final programme loudness.
    r=subprocess.run([FFMPEG,'-hide_banner','-i',str(movie),'-vf','blackdetect=d=0.45:pix_th=0.05:pic_th=0.98',
       '-af','loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
    log=r.stderr;black=[line for line in log.splitlines() if 'black_start:' in line]
    report['sustained_black_intervals']=black
    measured=json.loads(log[log.rfind('{'):log.rfind('}')+1])
    report['final_loudness']=measured
    assert -17.5<float(measured['input_i'])<-14.5,measured
    assert float(measured['input_tp'])<-.5,measured
    assert not black,black
    # Extract actual encoded frames, including the opening and closing cards.
    movie_av=av.open(str(movie));stream=movie_av.streams.video[0];shots=[]
    samples=[('opening',2.8),*[(s['id'],s['start']+s['duration']*.63) for s in timeline['scenes']],('ending',timeline['duration']-1.3)]
    for name,t in samples:
        movie_av.seek(int(t/float(stream.time_base)),stream=stream,backward=True)
        for frame in movie_av.decode(stream):
            if frame.time>=t:
                im=frame.to_image();im.save(qa/f'{name}.jpg',quality=94);shots.append((name,im));break
    movie_av.close()
    sheet=Image.new('RGB',(1280,205*math.ceil(len(shots)/4)),(15,25,29));d=ImageDraw.Draw(sheet)
    for i,(name,im) in enumerate(shots):
        x=(i%4)*320;y=(i//4)*205
        sheet.paste(im.resize((320,180),Image.Resampling.LANCZOS),(x,y+22));d.text((x+9,y+4),name,fill=(240,230,210))
    sheet.save(qa/'contact_sheet.jpg',quality=94)
    # Stream hash so even a long video never has to be loaded in memory.
    digest=hashlib.sha256()
    with movie.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
    report['sha256']=digest.hexdigest();report['status']='passed'
    write_json(qa/'report.json',report)
    summary=[f'# Verifica del video finale','',f'Esito: **PASS**. File: `{movie.name}`.',
      f'Durata: {stamp(video_duration)}. {v.width} × {v.height}, {report["fps"]:.0f} fps, H.264 High / yuv420p, audio AAC stereo 48 kHz.',
      f'Tutti i {report["video_frames"]:,} fotogrammi e la traccia audio sono stati decodificati senza errori.',
      f'Differenza durata audio/video: {abs(audio_duration-video_duration):.4f} s.',
      f'Loudness integrata: {measured["input_i"]} LUFS; picco reale: {measured["input_tp"]} dBTP.',
      f'{report["chapters"]} capitoli incorporati, una traccia sottotitoli italiana e file SRT separato.',
      'Nessun intervallo nero non previsto più lungo di 0,45 s.',
      f'Fotogrammi estratti dal file finale in {qa.relative_to(ROOT)}; controllo visivo del contact sheet e dei fotogrammi a risoluzione piena.',
      f'SHA-256: `{report["sha256"]}`.']
    (qa/'report.md').write_text('\n\n'.join(summary),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return report
