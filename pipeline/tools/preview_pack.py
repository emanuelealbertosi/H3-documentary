"""Early layout review before voice synthesis finishes; never writes the real timeline."""
from pathlib import Path
import sys,copy,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.common import ROOT,read_json
from engine.visuals import Visuals
from PIL import Image,ImageDraw
pack=copy.deepcopy(read_json(ROOT/sys.argv[1]));cursor=0
for s in pack['scenes']:
 s['cues']=[];offset=.65
 for i,line in enumerate(s['lines']):
  duration=len(line.split())/2.9
  s['cues'].append(dict(index=i,start=offset,end=offset+duration,text=line));offset+=duration+.18
 s.update(start=cursor,end=cursor+offset+1,duration=offset+1);cursor=s['end']
 s['commanders']=[c for c in s['commanders'] if (ROOT/pack['commanders'][c['id']]['portrait']).exists()]
pack['duration']=cursor
v=Visuals(pack);out=ROOT/'build'/pack['slug']/'layout';out.mkdir(exist_ok=True,parents=True)
sheet=Image.new('RGB',(1600,203*math.ceil(len(pack['scenes'])/4)),(15,25,29));d=ImageDraw.Draw(sheet)
for i,s in enumerate(pack['scenes']):
 im=v.frame(s,s['duration']*.63);im.save(out/f'{s["id"]}.jpg',quality=94)
 x=i%4*400;y=i//4*203;sheet.paste(im.resize((352,198)),(x,y));d.text((x+354,y+10),s['id'],fill='white')
sheet.save(out/'contact.jpg',quality=95);print(out)
