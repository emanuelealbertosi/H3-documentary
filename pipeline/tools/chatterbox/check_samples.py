"""Decode and independently transcribe the generated auditions, locally."""
import json,sys,re,unicodedata,difflib,argparse,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from engine.common import ROOT,write_json
from faster_whisper import WhisperModel
import av

def words(text):
    text=unicodedata.normalize('NFKD',text.casefold())
    return re.findall(r'[a-z0-9]+',''.join(x for x in text if not unicodedata.combining(x)))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--name');args=parser.parse_args()
    out=ROOT/'output/chatterbox-test'
    records=json.loads((out/'speech-check.json').read_text(encoding='utf-8')) if (out/'speech-check.json').exists() else []
    model=WhisperModel(str(ROOT/'assets/qa/whisper-small'),device='cpu',compute_type='int8',cpu_threads=2,num_workers=1)
    for benchmark in sorted(out.glob(f'benchmark_{args.name or "*"}.json')):
        for sample in json.loads(benchmark.read_text(encoding='utf-8'))['samples']:
            with av.open(sample['file']) as container:
                decoded=sum(frame.samples for frame in container.decode(audio=0))
            segments,info=model.transcribe(sample['file'],beam_size=3,vad_filter=True,condition_on_previous_text=False)
            transcript=' '.join(s.text.strip() for s in segments)
            similarity=difflib.SequenceMatcher(None,words(sample['text']),words(transcript),autojunk=False).ratio()
            item=dict(file=sample['file'],expected_language=sample['language'],detected_language=info.language,
                language_probability=info.language_probability,reference=sample['text'],transcript=transcript,
                word_sequence_similarity=similarity,decoded_samples=decoded,decode_passed=decoded>0,
                sha256=hashlib.sha256(Path(sample['file']).read_bytes()).hexdigest(),
                note='ASR is an independent check; it does not rate naturalness or certify voice identity.')
            records=[r for r in records if r['file']!=item['file']]+[item];write_json(out/'speech-check.json',records)
            print(json.dumps(item,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
