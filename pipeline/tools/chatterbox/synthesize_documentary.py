"""Generate the raw narration cache with one Chatterbox model load."""
import argparse,hashlib,json,os,re,warnings
from pathlib import Path

def fingerprint(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def pronounce(text,replacements):
    for source,target in sorted(replacements.items(),key=lambda item:-len(item[0])):text=text.replace(source,target)
    return text

def synthesis_key(pack,scene_id,index,spoken,workspace):
    values=[spoken,pack['voice'],pack.get('voice_engine','piper'),pack.get('voice_speaker'),1.0,.45,.65]
    cue=f'{scene_id}:{index}'
    if cue in pack.get('voice_custom_chunks',{}):values.extend(['custom-chunks-v2',pack['voice_custom_chunks'][cue]])
    elif cue in pack.get('voice_clause_chunks',[]):values.append('clause-chunks-v1')
    elif cue in pack.get('voice_sentence_chunks',[]):values.append('sentence-chunks-v1')
    overrides=pack.get('voice_phoneme_overrides',{}).get(cue)
    if overrides:values.append(overrides)
    fragments=pack.get('voice_chunk_assets',{}).get(cue,{})
    if fragments:
        values.append({key:{**asset,'sha256':hashlib.sha256((workspace/asset['path']).read_bytes()).hexdigest()} for key,asset in fragments.items()})
    return fingerprint(values)[:18]

def split_parts(pack,scene,index,spoken):
    cue=f'{scene["id"]}:{index}';custom=pack.get('voice_custom_chunks',{}).get(cue)
    if custom:
        if ' '.join(custom)!=scene['lines'][index]:raise ValueError('I segmenti TTS personalizzati non corrispondono al testo.')
        return [pronounce(part if part.endswith(('.','!','?')) else part.rstrip(',:;')+'.',pack.get('pronunciation',{})) for part in custom]
    if cue in pack.get('voice_clause_chunks',[]):return re.split(r'(?<=[.!?:;])\s+',spoken)
    if cue in pack.get('voice_sentence_chunks',[]):return re.split(r'(?<=[.!?])\s+',spoken)
    return [spoken]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--pack',type=Path,required=True)
    parser.add_argument('--model',type=Path,required=True);parser.add_argument('--threads',type=int,default=4,choices=range(1,9));args=parser.parse_args()
    workspace=args.workspace.resolve();pack_path=(workspace/args.pack).resolve()
    if not pack_path.is_relative_to(workspace):raise ValueError('Percorso del documentario non valido.')
    pack=json.loads(pack_path.read_text(encoding='utf-8'))
    if pack.get('voice_engine')!='chatterbox':raise ValueError('Il documentario non richiede Chatterbox.')
    out=workspace/'build'/pack['slug']/'voice';out.mkdir(parents=True,exist_ok=True)
    pending=[]
    cache_items={}
    total=sum(len(scene['lines']) for scene in pack['scenes'])
    for scene in pack['scenes']:
        for index,line in enumerate(scene['lines']):
            spoken=pronounce(line,pack.get('pronunciation',{}));key=synthesis_key(pack,scene['id'],index,spoken,workspace);path=out/f'{key}.wav'
            cache_items[f'{scene["id"]}:{index}']={'file':path.name,'spoken_sha256':hashlib.sha256(spoken.encode('utf-8')).hexdigest()}
            if not path.exists():pending.append((scene,index,spoken,path))
    manifest=out/'external-voice-cache.json'
    manifest.write_text(json.dumps({'version':1,'backend':'chatterbox','items':cache_items},ensure_ascii=False,indent=2),encoding='utf-8')
    if not pending:
        print('Chatterbox: voce già presente nella cache.',flush=True);return
    cached=total-len(pending)
    print(f'Chatterbox: {len(pending)} segmenti da generare, {cached} già in cache.',flush=True)
    os.environ.setdefault('HF_HOME',str(args.model.parent.parent/'.cache/huggingface'))
    os.environ.setdefault('PKUSEG_HOME',str(args.model/'pkuseg'));os.environ.setdefault('HF_HUB_OFFLINE','1')
    os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY','1');os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
    os.environ.setdefault('TQDM_DISABLE','1')
    os.environ.setdefault('OMP_NUM_THREADS',str(args.threads));os.environ.setdefault('MKL_NUM_THREADS',str(args.threads));os.environ.setdefault('NUMBA_NUM_THREADS',str(args.threads))
    warnings.filterwarnings('ignore',category=FutureWarning)
    import numpy as np,soundfile as sf,torch,tqdm
    progress=tqdm.tqdm
    def quiet_progress(*values,**options):
        options['disable']=True;return progress(*values,**options)
    tqdm.tqdm=quiet_progress
    torch.set_num_threads(args.threads);torch.set_num_interop_threads(1)
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    print('Chatterbox: caricamento del modello vocale locale…',flush=True)
    model=ChatterboxMultilingualTTS.from_local(args.model.resolve(),device='cpu',t3_model='v3')
    reference=(workspace/pack['voice_reference']).resolve() if pack.get('voice_reference') else None
    if reference and (not reference.is_file() or not reference.is_relative_to(workspace)):raise ValueError('Campione vocale del progetto non disponibile.')
    conditioned=False
    torch.manual_seed(42);np.random.seed(42)
    for pending_index,(scene,index,spoken,path) in enumerate(pending,1):
        parts=split_parts(pack,scene,index,spoken);chunks=[]
        for part_index,part in enumerate(parts):
            with torch.inference_mode():
                audio=model.generate(part,language_id=pack.get('voice_language','it'),
                    audio_prompt_path=str(reference) if reference and not conditioned else None,
                    exaggeration=pack.get('chatterbox_exaggeration',.35),cfg_weight=pack.get('chatterbox_cfg_weight',.5),
                    temperature=pack.get('chatterbox_temperature',.7),repetition_penalty=pack.get('chatterbox_repetition_penalty',1.2))
            conditioned=conditioned or bool(reference)
            y=audio.detach().cpu().numpy().reshape(-1).astype(np.float32)
            active=np.flatnonzero(np.abs(y)>.002)
            if len(active):y=y[max(0,active[0]-round(model.sr*.09)):min(len(y),active[-1]+round(model.sr*.16))]
            if part_index:chunks.append(np.zeros(round(model.sr*.12),dtype=np.float32))
            chunks.append(y)
        joined=np.concatenate(chunks);peak=float(np.max(np.abs(joined)))
        if not np.isfinite(joined).all() or len(joined)<model.sr//4:raise ValueError('Chatterbox ha prodotto un segmento audio non valido.')
        joined*=min(1,.94/max(peak,1e-9));sf.write(path,joined,model.sr,subtype='PCM_16')
        print('Chatterbox voice ready',scene['id'],scene['title'],f'frase {index+1}/{len(scene["lines"])}',
              f'· segmento {cached+pending_index}/{total}',flush=True)

if __name__=='__main__':main()
