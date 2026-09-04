"""Local neural voice, measured cue points, automatic duration fitting."""
import re, wave, math, hashlib
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from piper import PiperVoice,SynthesisConfig
from .common import ROOT,write_json,read_json,fingerprint,run_ff

def pronounce(text, replacements):
    for a,b in sorted(replacements.items(),key=lambda kv:-len(kv[0])):
        text=text.replace(a,b)
    return text

def trim(y,sr):
    # Keep leading/trailing breathing space, remove only redundant synthesis silence.
    active=np.flatnonzero(np.abs(y.astype(float))>180)
    if len(active): y=y[max(0,active[0]-int(.09*sr)):min(len(y),active[-1]+int(.16*sr))]
    return y

def synthesis_key(pack,scene_id,index,spoken):
    values=[spoken,pack['voice'],pack.get('voice_engine','piper'),pack.get('voice_speaker'),1.0,.45,.65]
    if f'{scene_id}:{index}' in pack.get('voice_custom_chunks',{}):values.extend(['custom-chunks-v2',pack['voice_custom_chunks'][f'{scene_id}:{index}']])
    elif f'{scene_id}:{index}' in pack.get('voice_clause_chunks',[]):values.append('clause-chunks-v1')
    elif f'{scene_id}:{index}' in pack.get('voice_sentence_chunks',[]):values.append('sentence-chunks-v1')
    overrides=pack.get('voice_phoneme_overrides',{}).get(f'{scene_id}:{index}')
    if overrides:values.append(overrides)
    fragments=pack.get('voice_chunk_assets',{}).get(f'{scene_id}:{index}',{})
    if fragments:
        values.append({key:{**asset,'sha256':hashlib.sha256((ROOT/asset['path']).read_bytes()).hexdigest()} for key,asset in fragments.items()})
    return fingerprint(values)[:18]

def select_voice_tempo(pack,backend,natural,gaps):
    """Fit narration to the requested duration without penalising slow external voices."""
    target=float(pack['target_minutes'])*60
    available=max(1.,target-gaps)
    required=natural/available
    configured=pack.get('max_voice_tempo')
    soft_limit=float(configured) if isinstance(configured,(int,float)) and configured>0 else 1.22
    hard_limit=soft_limit
    if backend in ('chatterbox','tts_api'):
        adaptive=pack.get('external_max_voice_tempo',1.15)
        adaptive=float(adaptive) if isinstance(adaptive,(int,float)) and adaptive>0 else 1.15
        hard_limit=adaptive
    return max(.90,min(hard_limit,required))

def synthesize(pack,keep_timing=False):
    out=ROOT/'build'/pack['slug']/'voice'; out.mkdir(parents=True,exist_ok=True)
    voice=None; g2p=None; raw=[]; backend=pack.get('voice_engine','piper')
    external_items={}
    if backend in ('chatterbox','tts_api'):
        manifest=out/'external-voice-cache.json'
        if manifest.exists():
            cache=read_json(manifest)
            if cache.get('backend')!=backend:raise ValueError('La cache vocale appartiene a un altro motore. Riprendi la produzione per rigenerarla.')
            external_items=cache.get('items',{})
    for scene in pack['scenes']:
        for i,line in enumerate(scene['lines']):
            spoken=pronounce(line,pack.get('pronunciation',{}))
            key=synthesis_key(pack,scene['id'],i,spoken)
            path=out/f'{key}.wav'
            if backend in ('chatterbox','tts_api'):
                cached=external_items.get(f'{scene["id"]}:{i}',{})
                if cached.get('spoken_sha256')!=hashlib.sha256(spoken.encode('utf-8')).hexdigest():
                    raise ValueError(f'Cache voce esterna non valida per {scene["id"]}, frase {i+1}. Riprendi la produzione per rigenerarla.')
                path=out/Path(cached.get('file','')).name
                if not path.is_file():
                    raise ValueError(f'Segmento voce esterna mancante per {scene["id"]}, frase {i+1}. Riprendi la produzione per rigenerarlo.')
            if not path.exists():
                if backend=='kokoro':
                    if voice is None:
                        from kokoro_onnx import Kokoro
                        from misaki.espeak import EspeakG2P
                        voice=Kokoro(str(ROOT/pack['voice']),str(ROOT/pack['voice_styles']))
                        g2p=EspeakG2P(language='it')
                    custom=pack.get('voice_custom_chunks',{}).get(f'{scene["id"]}:{i}')
                    if custom:
                        assert ' '.join(custom)==line,'Custom TTS chunks must retain the exact narration words and punctuation.'
                        parts=[pronounce(part if part.endswith(('.', '!', '?')) else part.rstrip(',:;')+'.',pack.get('pronunciation',{})) for part in custom]
                    elif f'{scene["id"]}:{i}' in pack.get('voice_clause_chunks',[]):parts=re.split(r'(?<=[.!?:;])\s+',spoken)
                    elif f'{scene["id"]}:{i}' in pack.get('voice_sentence_chunks',[]):parts=re.split(r'(?<=[.!?])\s+',spoken)
                    else:parts=[spoken]
                    chunks=[]
                    for part_index,part in enumerate(parts):
                        fragment=pack.get('voice_chunk_assets',{}).get(f'{scene["id"]}:{i}',{}).get(str(part_index))
                        if fragment:
                            assert fragment['text'].casefold()==part.casefold(),'Reviewed voice fragment must match the spoken text.'
                            sample_rate,pcm=wavfile.read(ROOT/fragment['path'])
                            assert sample_rate==24000 and pcm.ndim==1 and pcm.dtype==np.int16
                            chunks.extend([pcm,np.zeros(round(sample_rate*.09),dtype=np.int16)])
                            continue
                        phonemes=g2p(part)
                        if isinstance(phonemes,tuple):phonemes=phonemes[0]
                        for original,replacement in pack.get('voice_phoneme_overrides',{}).get(f'{scene["id"]}:{i}',{}).items():phonemes=phonemes.replace(original,replacement)
                        samples,sample_rate=voice.create(phonemes,pack['voice_speaker'],is_phonemes=True)
                        pcm=trim(np.clip(samples*32767,-32767,32767).astype(np.int16),sample_rate)
                        chunks.extend([pcm,np.zeros(round(sample_rate*.09),dtype=np.int16)])
                    wavfile.write(path,sample_rate,np.concatenate(chunks[:-1]))
                elif backend=='piper':
                    if voice is None:voice=PiperVoice.load(str(ROOT/pack['voice']))
                    with wave.open(str(path),'wb') as wav:
                        voice.synthesize_wav(spoken,wav,SynthesisConfig(length_scale=1.0,noise_scale=.45,noise_w_scale=.65))
                else:raise ValueError('La voce esterna non ha preparato tutti i segmenti richiesti.')
                sr,y=wavfile.read(path); wavfile.write(path,sr,trim(y,sr))
            sr,y=wavfile.read(path)
            raw.append(dict(scene=scene['id'],index=i,path=path,duration=len(y)/sr,spoken=spoken,text=line))
        print('Voice ready',scene['id'],scene['title'],flush=True)
    natural=sum(x['duration'] for x in raw)
    if keep_timing:
        previous=read_json(ROOT/'build'/pack['slug']/'timeline.json')
        minimum=pack.get('min_minutes',pack['target_minutes']*.88)*60
        maximum=pack.get('max_minutes',pack['target_minutes']*1.12)*60
        if not minimum<=previous['duration']<=maximum:
            raise ValueError('Existing timeline does not meet the requested duration. Rebuild without --keep-timing.')
        fit_report=[]
        # Validate every stretch before replacing any already-rendered scene audio.
        for item in raw:
            scene=next(s for s in previous['scenes'] if s['id']==item['scene'])
            cue=scene['cues'][item['index']];factor=item['duration']/(cue['end']-cue['start'])
            assert cue['text']==item['text'],'Keep-timing requires unchanged narration text.'
            if not .65<=factor<=1.48:raise ValueError(f'Excessive tempo change in {scene["id"]}/{item["index"]}: {factor}. Rebuild without --keep-timing.')
        for scene in previous['scenes']:
            authored=next(s for s in pack['scenes'] if s['id']==scene['id'])
            scene.update(authored)
            sr=48000; combined=np.zeros(round(scene['duration']*sr),dtype=np.int16)
            for item in [x for x in raw if x['scene']==scene['id']]:
                cue=scene['cues'][item['index']]
                cue['spoken']=item['spoken']
                assert cue['text']==item['text'],'Keep-timing requires unchanged narration text.'
                duration=cue['end']-cue['start']; factor=item['duration']/duration
                if not .65<=factor<=1.48:raise ValueError(f'Excessive voice tempo change in {scene["id"]}/{item["index"]}: {factor}. Rebuild without --keep-timing.')
                fitted=out/(item['path'].stem+f'-locked{duration:.6f}.wav')
                if not fitted.exists():
                    run_ff(['-i',item['path'],'-af',f'atempo={factor:.8f},highpass=f=65,lowpass=f=10500,apad',
                            '-t',f'{duration:.6f}','-ar',sr,'-ac',1,'-c:a','pcm_s16le',fitted])
                _,y=wavfile.read(fitted);rms=np.sqrt(np.mean(y.astype(float)**2))/32768
                gain=min(.115/max(rms,1e-7),.86/max(np.max(np.abs(y.astype(float)))/32768,1e-7))
                y=np.clip(y.astype(float)*gain,-32767,32767).astype(np.int16)
                start=round(cue['start']*sr);n=min(len(y),len(combined)-start)
                combined[start:start+n]=y[:n]
                fit_report.append(dict(scene=scene['id'],cue=item['index'],tempo=factor))
            wavfile.write(ROOT/scene['audio'],sr,combined)
            print('Voice replaced on measured cue grid',scene['id'],flush=True)
        previous.update({key:value for key,value in pack.items() if key!='scenes'})
        previous['voice_tempo_mode']='individual cues, locked to existing timeline'
        write_json(ROOT/'build'/pack['slug']/'voice-fit-report.json',fit_report)
        if previous.get('documentary_schema_version')==2:
            from .history_schema import enrich_timeline
            enrich_timeline(previous)
        write_json(ROOT/'build'/pack['slug']/'timeline.json',previous);write_json(ROOT/'timeline.json',previous)
        return previous
    gaps=len(pack['scenes'])*1.5+len(raw)*.18
    target=pack['target_minutes']*60
    tempo=select_voice_tempo(pack,backend,natural,gaps)
    print(f'Natural voice {natural:.1f}s. Tempo factor {tempo:.3f}.',flush=True)
    timeline={k:v for k,v in pack.items() if k!='scenes'}
    timeline['scenes']=[]; cursor=0.; fps=pack['fps']
    for scene in pack['scenes']:
        sr=48000; audio=[np.zeros(int(sr*.65),dtype=np.int16)]; cues=[]; offset=.65
        for line in [a for a in raw if a['scene']==scene['id']]:
            fitted=out/(line['path'].stem+f'-tempo{tempo:.5f}.wav')
            if not fitted.exists():
                run_ff(['-i',line['path'],'-af',f'atempo={tempo:.6f},highpass=f=65,lowpass=f=10500',
                        '-ar',sr,'-ac',1,'-c:a','pcm_s16le',fitted])
            _,y=wavfile.read(fitted)
            # Consistent sentence RMS, with a hard ceiling before the final true-peak limiter.
            rms=np.sqrt(np.mean(y.astype(float)**2))/32768
            if rms>0:
                gain=min(.115/rms,.86/(np.max(np.abs(y.astype(float)))/32768))
                y=np.clip(y.astype(float)*gain,-32767,32767).astype(np.int16)
            cues.append(dict(index=line['index'],start=round(offset,6),end=round(offset+len(y)/sr,6),text=line['text'],spoken=line['spoken']))
            audio.extend([y,np.zeros(int(sr*.18),dtype=np.int16)]); offset+=len(y)/sr+.18
        duration=math.ceil((offset+.85)*fps)/fps
        tail=round(duration*sr)-sum(len(x) for x in audio)
        audio.append(np.zeros(tail,dtype=np.int16))
        combined=np.concatenate(audio)
        scene_path=out/f'{scene["id"]}-narration.wav'; wavfile.write(scene_path,sr,combined)
        item=dict(scene,start=round(cursor,6),end=round(cursor+duration,6),duration=duration,cues=cues,
                  audio=str(scene_path.relative_to(ROOT)).replace('\\','/'),frames=round(duration*fps))
        timeline['scenes'].append(item); cursor+=duration
    timeline['duration']=cursor; timeline['voice_tempo']=tempo
    minimum=pack.get('min_minutes',pack['target_minutes']*.88)*60
    maximum=pack.get('max_minutes',pack['target_minutes']*1.12)*60
    if backend in ('chatterbox','tts_api'):
        maximum=max(maximum,pack['target_minutes']*1.5*60)
    if not minimum<=cursor<=maximum:
        raise ValueError(f'Duration {cursor:.1f}s outside requested {minimum/60:.1f}–{maximum/60:.1f} minutes. Adjust the narration or target duration.')
    if timeline.get('documentary_schema_version')==2:
        from .history_schema import enrich_timeline
        enrich_timeline(timeline)
    write_json(ROOT/'build'/pack['slug']/'timeline.json',timeline)
    write_json(ROOT/'timeline.json',timeline)
    print(f'Timeline: {cursor:.2f}s, {cursor/60:.2f}min',flush=True)
    return timeline
