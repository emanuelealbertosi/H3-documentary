"""A short local voice audition using the production synthesizer and mixer."""
import argparse,copy,json,re,shutil,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--request',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    request=args.request.resolve();output=args.output.resolve()
    if not output.is_relative_to(request.parent):raise ValueError('La prova deve rimanere nella cartella temporanea.')
    data=json.loads(request.read_text(encoding='utf-8'))
    text=str(data.get('text','')).strip()
    if not 1<=len(text)<=800:raise ValueError('Usa un testo di prova fino a 800 caratteri.')
    pack=copy.deepcopy(data['pack'])
    engine=pack.get('voice_engine','kokoro')
    if engine not in ('kokoro','chatterbox'):raise ValueError('Motore locale non supportato per la prova.')
    work=request.parent/'local-preview';work.mkdir(exist_ok=True)
    lines=[line.strip() for line in re.split(r'(?<=[.!?])\s+|\n+',text) if line.strip()]
    if len(lines)>8:lines=lines[:7]+[' '.join(lines[7:])]
    pack.update(slug='voice-preview',title='Prova della voce',target_minutes=1,min_minutes=0,max_minutes=30,
                fps=24,pronunciation={},_voice_preview=True,
                scenes=[{'id':'01','title':'Prova della voce','lines':lines}])
    if data.get('delivery'):pack['voice_delivery']=data['delivery']
    if engine=='kokoro':
        pack.setdefault('voice','assets/voice/kokoro/kokoro-v1.0.onnx')
        pack.setdefault('voice_styles','assets/voice/kokoro/voices-v1.0.bin')
        pack.setdefault('voice_speaker','if_sara');pack['voice_engine']='kokoro'
        for key in ('voice','voice_styles'):pack[key]=str((ROOT/pack[key]).resolve())
    if pack.get('voice_reference'):
        reference=(request.parent/pack['voice_reference']).resolve()
        if not reference.is_file():raise ValueError('Campione vocale non disponibile.')
        target=work/'reference.wav';shutil.copyfile(reference,target)
        pack['voice_reference']='reference.wav'
    if engine=='chatterbox':
        pack_file=work/'preview.json';pack_file.write_text(json.dumps(pack,ensure_ascii=False),encoding='utf-8')
        subprocess.run([str(ROOT/'.venv-chatterbox/Scripts/python.exe'),'-X','utf8',
                        str(ROOT/'tools/chatterbox/synthesize_documentary.py'),'--workspace',str(work),
                        '--pack','preview.json','--model',str(ROOT/'assets/tts/chatterbox-v3')],
                       check=True,timeout=840)
    sys.path.insert(0,str(ROOT))
    from engine import narration
    narration.ROOT=work
    timeline=narration.synthesize(pack)
    narration.run_ff(['-i',work/timeline['scenes'][0]['audio'],'-ar',24000,'-ac',1,'-c:a','pcm_s16le',output])
    print('Prova vocale pronta.',flush=True)


if __name__=='__main__':main()
