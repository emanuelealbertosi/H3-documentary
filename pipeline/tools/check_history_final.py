"""Detect brightness flashes inside shots; legitimate scene cuts are reported separately."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import av,numpy as np
from engine.common import ROOT,read_json,write_json

def main():
    slug=sys.argv[1];t=read_json(ROOT/'build'/slug/'timeline.json');movie=ROOT/t['output']
    with av.open(str(movie)) as c:
        means=[float(np.asarray(f.reformat(width=96,height=54,format='gray').to_ndarray()).mean()) for f in c.decode(video=0)]
    diff=np.abs(np.diff(means));cutframes={round(s['start']*t['fps'])-1 for s in t['scenes'][1:]}
    interior=[float(v) for i,v in enumerate(diff) if all(abs(i-cut)>2 for cut in cutframes)]
    report={'frames':len(means),'max_internal_brightness_step':max(interior,default=0),'intentional_cuts':[{'frame':i+1,'step':float(diff[i])} for i in sorted(cutframes)],'scope':'Global brightness flashes; does not certify local aliasing or visual correctness.'}
    report['passed']=report['max_internal_brightness_step']<4
    write_json(ROOT/'output'/t['verification_dir']/'flicker.json',report)
    if not report['passed']:raise ValueError('Possible intra-shot flash')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
