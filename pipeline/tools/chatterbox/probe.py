"""Offline CPU audition and benchmark, isolated from the documentary pipeline."""
import argparse,json,os,time,threading,hashlib,sys,platform,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
os.environ.setdefault('HF_HOME',str(ROOT/'.cache/chatterbox/huggingface'))
os.environ.setdefault('PKUSEG_HOME',str(ROOT/'assets/tts/chatterbox-v3/pkuseg'))
os.environ.setdefault('HF_HUB_OFFLINE','1')
os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY','1')
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
os.environ.setdefault('OMP_NUM_THREADS','4')
os.environ.setdefault('MKL_NUM_THREADS','4')
os.environ.setdefault('NUMBA_NUM_THREADS','4')
os.environ.setdefault('TQDM_MININTERVAL','5')

TEXTS={
 'it':"Nel Rinascimento, le città europee erano collegate da viaggi, commerci e scambi di idee. Pittori, studiosi e tipografi portarono nuove conoscenze oltre i confini, trasformando il modo di osservare il mondo.",
 'en':"During the Renaissance, European cities were connected by travel, trade, and the exchange of ideas. Artists and scholars carried new knowledge across borders."
}

def main():
    p=argparse.ArgumentParser();p.add_argument('--languages',nargs='+',default=['it']);p.add_argument('--reference',type=Path)
    p.add_argument('--text-file',type=Path);p.add_argument('--threads',type=int,default=4,choices=range(1,9));p.add_argument('--name',default='builtin')
    p.add_argument('--sentences',action='store_true',help='Generate individual sentences with a shared voice reference')
    args=p.parse_args()
    if not args.name.replace('-','').replace('_','').isalnum():raise ValueError('Invalid output name')
    if args.reference and not args.reference.is_file():raise ValueError('Reference audio does not exist')
    if args.text_file and len(args.languages)!=1:raise ValueError('Use one language with a custom text')
    out=ROOT/'output/chatterbox-test';out.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()
    import torch,psutil,numpy as np,soundfile as sf
    torch.set_num_threads(args.threads);torch.set_num_interop_threads(1)
    process=psutil.Process();peak=[process.memory_info().rss];stop=threading.Event()
    def monitor():
        while not stop.wait(.25):peak[0]=max(peak[0],process.memory_info().rss)
    threading.Thread(target=monitor,daemon=True).start()
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    checkpoint=ROOT/'assets/tts/chatterbox-v3'
    print('Loading Chatterbox Multilingual V3 on CPU...',flush=True);t=time.perf_counter()
    model=ChatterboxMultilingualTTS.from_local(checkpoint,device='cpu',t3_model='v3')
    load_seconds=time.perf_counter()-t
    print(f'Model loaded in {load_seconds:.1f}s; RSS {process.memory_info().rss/2**30:.2f} GiB',flush=True)
    report=dict(model='Chatterbox Multilingual V3',device='cpu',threads=args.threads,python=platform.python_version(),
        torch=torch.__version__,model_revision=json.loads((checkpoint/'manifest.json').read_text())['revision'],
        source_revision='5de7a54aa4e5e2baadb0182dde554908b48b85c2',model_load_seconds=load_seconds,
        generation_parameters=dict(seed=42,exaggeration=.35,cfg_weight=.5,temperature=.7,repetition_penalty=1.2,sentence_chunks=args.sentences),
        reference=str(args.reference.resolve()) if args.reference else 'Included model conditioning; no personal voice cloning',samples=[])
    if args.reference:
        report['reference_sha256']=hashlib.sha256(args.reference.read_bytes()).hexdigest()
    for lang in args.languages:
        text=args.text_file.read_text(encoding='utf-8').strip() if args.text_file else TEXTS[lang]
        print(f'Generating {lang}: {len(text.split())} words...',flush=True)
        torch.manual_seed(42);np.random.seed(42);t=time.perf_counter()
        parts=re.split(r'(?<=[.!?])\s+',text) if args.sentences else [text]
        chunks=[]
        with torch.inference_mode():
            for index,part in enumerate(parts):
                audio=model.generate(part,language_id=lang,audio_prompt_path=str(args.reference) if args.reference and index==0 else None,
                    exaggeration=.35,cfg_weight=.5,temperature=.7,repetition_penalty=1.2)
                if index:chunks.append(np.zeros(round(model.sr*.18),dtype=np.float32))
                chunks.append(audio.detach().cpu().numpy().reshape(-1))
        elapsed=time.perf_counter()-t;y=np.concatenate(chunks)
        if not np.isfinite(y).all() or len(y)<model.sr:raise ValueError('Invalid or empty audio')
        raw_peak=float(np.max(np.abs(y)));gain=min(1,.94/max(raw_peak,1e-9))
        master=out/f'chatterbox_{lang}_{args.name}_float.wav';sf.write(master,y,model.sr,subtype='FLOAT')
        y=y*gain
        file=out/f'chatterbox_{lang}_{args.name}.wav';sf.write(file,y,model.sr,subtype='PCM_16')
        duration=len(y)/model.sr
        sample=dict(language=lang,text=text,file=str(file),duration_seconds=duration,generation_seconds=elapsed,
            real_time_factor=elapsed/duration,sample_rate=model.sr,peak_amplitude=float(np.max(np.abs(y))),
            rms=float(np.sqrt(np.mean(y*y))),clipped_samples=int(np.sum(np.abs(y)>=1)),
            unscaled_peak=raw_peak,output_gain=gain,float_master=str(master),
            peak_process_gib=peak[0]/2**30,sha256=hashlib.sha256(file.read_bytes()).hexdigest())
        report['samples'].append(sample);report['total_seconds']=time.perf_counter()-started
        report['peak_process_gib']=peak[0]/2**30
        (out/f'benchmark_{args.name}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        (out/f'text_{lang}_{args.name}.txt').write_text(text,encoding='utf-8')
        print(json.dumps(sample,ensure_ascii=False,indent=2),flush=True)
    stop.set();print('Benchmark complete.',flush=True)

if __name__=='__main__':main()
