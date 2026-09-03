"""Produce editorial deliverables and deterministic representative previews."""
import sys,math,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image,ImageDraw
from engine.common import ROOT,read_json,write_json,validate_pack
from engine.history_schema import estimate_timeline
from engine.history_export import export_estimate
from engine.visuals import Visuals

def preview(path,measured=False):
    authored=read_json(path)
    pack=read_json(ROOT/'build'/authored['slug']/'timeline.json') if measured else estimate_timeline(authored)
    validate_pack(pack)
    if measured:
        if pack.get('timing_status')!='measured_tts':raise ValueError('Timeline vocale misurata non disponibile')
        if [(s['id'],s['lines']) for s in pack['scenes']]!=[(s['id'],s['lines']) for s in authored['scenes']]:raise ValueError('La voce appartiene a una sceneggiatura diversa')
    else:export_estimate(pack)
    out=ROOT/'build'/pack['slug']/'layout';out.mkdir(parents=True,exist_ok=True)
    v=Visuals(pack);sheet=Image.new('RGB',(1600,245*math.ceil(len(pack['scenes'])/4)),(13,31,42));d=ImageDraw.Draw(sheet)
    for i,s in enumerate(pack['scenes']):
        for f in [.15,.63,.90]:
            im=v.frame(s,s['duration']*f);im.save(out/f'{s["id"]}-{f:.2f}.jpg',quality=94)
            if f==.63:
                x=i%4*400;y=i//4*245;sheet.paste(im.resize((400,225)),(x,y+20));d.text((x+8,y+3),s['id']+' '+s['scene_type'],fill='white')
    sheet.save(out/'contact.jpg',quality=95)
    write_json(out/'report.json',{'status':'rendered','timing':pack['timing_status'],'scene_types':sorted({s['scene_type'] for s in pack['scenes']}),'images':len(pack['scenes'])*3})
    print(out,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('path',nargs='?');parser.add_argument('--measured',action='store_true');args=parser.parse_args()
    paths=[ROOT/args.path] if args.path else list((ROOT/'documentaries').glob('*/documentary.json'))
    for p in paths:preview(p,args.measured)
