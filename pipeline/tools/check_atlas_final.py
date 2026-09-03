"""Measure actual encoded-frame brightness continuity, including every chapter join."""
import sys,subprocess
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.common import ROOT,read_json,write_json,FFMPEG

def main():
    slug=sys.argv[1] if len(sys.argv)>1 else 'annibale';p=read_json(ROOT/'build'/slug/'timeline.json')
    command=[FFMPEG,'-hide_banner','-loglevel','error','-i',str(ROOT/p['output']),'-an','-sn','-vf','scale=96:54:flags=area,format=gray','-f','rawvideo','-pix_fmt','gray','pipe:1']
    process=subprocess.Popen(command,stdout=subprocess.PIPE);means=[];changes=[];previous=None
    size=96*54
    while True:
        raw=process.stdout.read(size)
        if not raw:break
        if len(raw)!=size:raise RuntimeError('Partial decoded frame')
        frame=np.frombuffer(raw,dtype=np.uint8).astype(np.float32);means.append(float(frame.mean()))
        if previous is not None:changes.append(float(np.abs(frame-previous).mean()))
        previous=frame
    assert process.wait()==0
    expected=sum(s['frames'] for s in p['scenes']);assert len(means)==expected
    diffs=np.abs(np.diff(means));joins=[]
    for scene in p['scenes'][1:]:
        i=round(scene['start']*p['fps']);joins.append({'scene':scene['id'],'time':scene['start'],'brightness_step':float(diffs[i-1]),'pixel_change':changes[i-1]})
    report={'frames_measured':len(means),'max_adjacent_mean_brightness_change':float(diffs.max()),'max_adjacent_pixel_change':max(changes),'min_mean_brightness':min(means),'chapter_joins':joins,'status':'passed' if diffs.max()<4 else 'review_required','method':'All encoded video frames decoded to 96x54 grayscale. Detects global flashes and chapter brightness discontinuities; does not certify absence of all local or perceptual aliasing.'}
    write_json(ROOT/'output'/p['verification_dir']/'motion.json',report)
    print(report['status'],report['frames_measured'],'frames; maximum brightness step',round(report['max_adjacent_mean_brightness_change'],4),flush=True)
    if report['status']!='passed':raise RuntimeError('Inspect detected brightness discontinuities')

if __name__=='__main__':main()
