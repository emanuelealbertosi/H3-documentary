"""Check local components; no remote LLM, system Python, FFmpeg or eSpeak required."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

def signature():
    return hashlib.sha256(b''.join((ROOT/p).read_bytes() for p in ['requirements-lock.txt','pipeline/requirements-lock.txt','scripts/assets-lock.json'])).hexdigest()

def check(quick=False,write=False):
    python=ROOT/'pipeline/.venv/Scripts/python.exe'
    paths=[python,ROOT/'.venv/Scripts/python.exe',ROOT/'pipeline/documentary.py',ROOT/'pipeline/engine/atlas.py',ROOT/'data/models/rag/ready.json']
    records=json.loads((ROOT/'scripts/assets-lock.json').read_text(encoding='utf-8'))
    paths.extend(ROOT/'pipeline'/r['path'] for r in records)
    if any(not p.is_file() for p in paths):raise RuntimeError('Installazione incompleta: riapri INSTALLA.bat.')
    if quick:
        saved=json.loads((ROOT/'data/installation.json').read_text())
        if saved.get('requirements')!=signature():raise RuntimeError('Dipendenze aggiornate: installazione richiesta.')
        return
    import fastapi,uvicorn,httpx,bs4,fastembed,pypdf,docx,imageio_ffmpeg,google.auth
    from app.documents import ensure_model
    ensure_model(False)
    code="""import json,sys,subprocess
from pathlib import Path
import av,numpy,scipy,PIL,cv2,imageio_ffmpeg,piper,reportlab
from kokoro_onnx import Kokoro
from misaki.espeak import EspeakG2P
root=Path.cwd()
model=Kokoro(str(root/'assets/voice/kokoro/kokoro-v1.0.onnx'),str(root/'assets/voice/kokoro/voices-v1.0.bin'))
assert EspeakG2P(language='it')('La storia incontra le immagini.')
ffmpeg=Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
assert ffmpeg.is_relative_to(root.parent), 'FFmpeg esterno al pacchetto'
assert Path(sys.base_prefix).resolve().is_relative_to(root.parent/'.runtimes'), 'Python non autonomo'
subprocess.run([str(ffmpeg),'-version'],check=True,stdout=subprocess.DEVNULL)
print(json.dumps({'python':sys.version.split()[0],'ffmpeg':ffmpeg.name,'voice':'Kokoro if_sara','italian_phonemizer':True}))
"""
    subprocess.run([str(python),'-X','utf8','-c',code],cwd=ROOT/'pipeline',check=True)
    if write:
        state={'root':str(ROOT),'version':(ROOT/'VERSION').read_text().strip(),'requirements':signature()}
        (ROOT/'data/installation.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
    print('Componenti locali pronti.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--write-state',action='store_true');args=p.parse_args()
    try:check(args.quick,args.write_state)
    except Exception as error:print(str(error),file=sys.stderr);sys.exit(1)
