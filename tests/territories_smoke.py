"""Render a short geographic demonstration with clearly fictitious areas; no LLM/TTS."""
import argparse,json,sys,subprocess,copy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'pipeline'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base-work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--atlas',default='assets/geography/atlas-film/atlas.json')
    args=parser.parse_args();base=args.base_work.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    from engine.common import read_json,write_json,FFMPEG
    from engine.history_schema import estimate_timeline
    from engine.history_visuals import HistoryVisuals
    from engine import atlas
    from engine.history_territories import area_view
    spec=read_json(base/args.atlas)
    for info in spec['layers']:
        info['levels']=[str(base/p) for p in info['levels']]
        if info.get('alpha'):info['alpha']=str(base/info['alpha'])
    write_json(out/'atlas.json',spec);atlas.ROOT=base
    # Abstract polygons: they deliberately make no national/historical claim.
    small=[[-.5,43],[4,43],[4,46],[-.5,46]]
    large=[[-.5,43],[7,43],[9,46],[5,48],[-.5,46]]
    influence=[[6,40],[15,40],[16,46],[10,48],[6,46]]
    disputed=[[5.5,44],[9,44],[10,46],[7,47],[5.5,46]]
    def layer(ident,label,kind,color,polygons,year=1500):
        return dict(id=ident,label=label,kind=kind,color=color,schematic=True,sources=['T1'],transition_years=2,states=[dict(year=year,polygons=polygons)])
    domain=layer('domain','Dominio · esempio','territory',[235,175,72],[small]);domain['states'] += [dict(year=1505,polygons=[large]),dict(year=1513,polygons=[small])]
    layers=[domain,layer('influence','Sfera d’influenza · esempio','influence',[70,185,220],[influence]),layer('disputed','Zona contesa · esempio','contested',[231,102,91],[disputed],1507)]
    view=area_view(small+large+influence+disputed)
    scene=dict(id='01',title='DOMINI E INFLUENZE',scene_type='territorial_change',date='PROVA GRAFICA',historical_range=[1500,1518],
      lines=['Dimostrazione grafica con aree fittizie.','Non è una ricostruzione di confini storici.'],facts=['Colori, confini, espansioni e perdite'],kicker='Tre significati sulla stessa mappa',
      sources=['T1'],location_ids=[],territory_ids=[l['id'] for l in layers],camera_start=view,camera_end=view,map_note='AREE FITTIZIE · nessun confine nazionale o storico')
    doc=dict(schema_version=2,slug='territories-demo',documentary_type='territorial_expansion',title='Prova grafica di territori e influenze',short_title='Prova grafica',
      target_minutes=.2,historical_period=dict(start=1500,end=1518),sources=[dict(id='T1',title='Dati sintetici di collaudo',url='https://example.org/fixture')],locations=[],persons=[],entities=[],events=[],visual_assets=[],
      visual_layers=layers,visual_direction={'territory_style':2},atlas=str(out/'atlas.json'),overview=view,scenes=[scene])
    write_json(out/'documentary.json',doc);timeline=estimate_timeline(doc);scene=timeline['scenes'][0]
    scene.update(duration=12,start=0,end=12,frames=144);timeline['duration']=12;timeline['fps']=12
    write_json(out/'timeline.json',timeline);v=HistoryVisuals(timeline)
    checkpoints=[2,6,11];frames=[]
    for t in checkpoints:
        im=v.frame(scene,t);im.save(out/f'preview-{t:02}.jpg',quality=92);frames.append(im)
        assert im.tobytes()==v.frame(scene,t).tobytes()
    video=out/'territori-influenze-demo.mp4'
    command=[FFMPEG,'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','12','-i','-','-an','-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-movflags','+faststart',str(video)]
    with (out/'encode.log').open('wb') as log:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log)
        try:
            for n in range(144):process.stdin.write(v.frame(scene,n/12).tobytes())
        finally:process.stdin.close()
        if process.wait()!=0:raise RuntimeError((out/'encode.log').read_text())
    subprocess.run([FFMPEG,'-v','error','-i',str(video),'-f','null','-'],check=True,capture_output=True)
    # Inspect actual encoded frames as well as renderer previews.
    for t in checkpoints:subprocess.run([FFMPEG,'-v','error','-y','-ss',str(t),'-i',str(video),'-frames:v','1',str(out/f'encoded-{t:02}.png')],check=True)
    report={'scope':'Synthetic graphical test, no historical reconstruction or remote services','duration':12,'size':[1920,1080],'frames':144,'full_decode':True,'deterministic':True,'video':str(video)}
    write_json(out/'report.json',report);print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
