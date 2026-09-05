"""Check reproducible slide composition; full MP4 decoding is performed by verify."""
import hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.common import ROOT,read_json,write_json
from engine.visuals import Visuals

def main():
    slug=sys.argv[1];timeline=read_json(ROOT/'build'/slug/'timeline.json')
    if timeline.get('presentation_mode')!='slides':raise ValueError('Modalità slide richiesta.')
    visual=Visuals(timeline);samples=[]
    for scene in timeline['scenes']:
        for fraction in (.1,.5,.9):
            t=scene['duration']*fraction
            first=visual.frame(scene,t);again=visual.frame(scene,t)
            a=hashlib.sha256(first.tobytes()).hexdigest();b=hashlib.sha256(again.tobytes()).hexdigest()
            if first.size!=(1920,1080) or a!=b:raise ValueError('Composizione delle slide non deterministica.')
            samples.append({'scene_id':scene['id'],'time':t,'sha256':a})
    report={'passed':True,'samples':samples,'scope':'Composizione deterministica. Fade e movimento sono intenzionali; non è una valutazione estetica. Decodifica integrale nel report video.'}
    write_json(ROOT/'output'/timeline['verification_dir']/'slide-effects.json',report)
    print('Slide: dimensioni e composizione deterministica verificate.',flush=True)

if __name__=='__main__':main()
