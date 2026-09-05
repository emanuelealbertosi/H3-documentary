"""Two-runtime integration proof with real pinned archives, no LLM or TTS.

Prepare with app Python; render with pipeline Python. Paths are explicit so the
test can reuse an immutable atlas without making the application depend on it.
"""
import argparse,json,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'pipeline')]

def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','render'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--base-work',type=Path)
    p.add_argument('--atlas',default='assets/geography/atlas-v2/atlas.json')
    p.add_argument('--name',default='Germany');p.add_argument('--label',default='Germania')
    p.add_argument('--years',nargs=2,type=int,default=[1918,1920]);p.add_argument('--usage',default='education_nc',choices=['commercial','education_nc'])
    p.add_argument('--cache',type=Path,default=ROOT/'data/cache/boundaries')
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    def write(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    if a.phase=='prepare':
        from app.boundaries import resolve
        from engine.boundary_data import BoundaryStore
        from engine.history_authoring import compile_outline
        from engine.history_schema import estimate_timeline
        outline=dict(documentary_type='territorial_expansion',title='Confini da archivio: '+a.label,short_title=a.label,
            historical_period=a.years,places=[],visual_layers=[dict(id='domain',label=a.label,kind='territory',color=[236,174,77],
            boundary_query={'name':a.name},sources=[],states=[dict(year=a.years[0],polygons=[])])],
            scenes=[dict(title='CONFINI NEL TEMPO',date=' / '.join(str(y) for y in a.years),scene_type='territorial_change',historical_range=a.years,territory_ids=['domain'],
            focus=[],event='Prova della selezione geografica per identità e periodo.',source_ids=[],map_note='PROVA CARTOGRAFICA · dati e licenze nei materiali')])
        resolved,sources,report=resolve(outline,out,a.usage,provider=BoundaryStore(a.cache))
        assert report['sourced']==1,report
        resolved['scenes'][0]['source_ids']=[s['id'] for s in sources]
        narration=[dict(index=0,lines=['Questa prova mostra geometrie selezionate da un archivio geografico datato. I cambiamenti seguono le date registrate nella fonte. Il filmato serve a verificare il motore e non costituisce un documentario storico completo.'],fact='Dati originali conservati nel progetto',kicker='Identità · periodo · provenienza')]
        doc,geo=compile_outline(resolved,narration,sources,dict(id='boundaries-test',topic='Confini territoriali',minutes=.2),dict(fps=12))
        write(out/'documentary.json',doc);write(out/'geography.json',geo);write(out/'timeline.json',estimate_timeline(doc))
        # Export uses the same functions as the final documentary, with isolated outputs.
        import engine.export as export
        export.ROOT=out;(out/'build'/doc['slug']).mkdir(parents=True,exist_ok=True)
        export.export_documents(estimate_timeline(doc))
        print(json.dumps({'phase':'prepare','sourced':report['sourced'],'datasets':report['layers'][0]['datasets'],'states':len(resolved['visual_layers'][0]['states'])}))
        return
    if not a.base_work:p.error('--base-work required for rendering')
    from engine.common import FFMPEG
    from engine.history_visuals import HistoryVisuals
    from engine import atlas
    base=a.base_work.resolve();spec=json.loads((base/a.atlas).read_text(encoding='utf-8'))
    for info in spec['layers']:
        info['levels']=[str(base/v) for v in info['levels']]
        if info.get('alpha'):info['alpha']=str(base/info['alpha'])
    write(out/'atlas.json',spec);atlas.ROOT=base
    timeline=json.loads((out/'timeline.json').read_text(encoding='utf-8'));timeline['atlas']=str(out/'atlas.json')
    scene=timeline['scenes'][0];scene.update(duration=12,start=0,end=12,frames=144)
    timeline.update(duration=12,fps=12);write(out/'timeline.json',timeline)
    v=HistoryVisuals(timeline);samples=[2,9,11]
    for t in samples:
        im=v.frame(scene,t);im.save(out/f'preview-{t:02}.jpg',quality=92)
        assert im.tobytes()==v.frame(scene,t).tobytes()
    video=out/'confini-da-archivio.mp4'
    command=[FFMPEG,'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','12','-i','-','-an','-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-movflags','+faststart',str(video)]
    with (out/'encode.log').open('wb') as log:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log)
        try:
            for n in range(144):process.stdin.write(v.frame(scene,n/12).tobytes())
        finally:process.stdin.close()
        if process.wait()!=0:raise RuntimeError((out/'encode.log').read_text())
    subprocess.run([FFMPEG,'-v','error','-i',str(video),'-f','null','-'],check=True,capture_output=True)
    for t in samples:subprocess.run([FFMPEG,'-v','error','-y','-ss',str(t),'-i',str(video),'-frames:v','1',str(out/f'encoded-{t:02}.png')],check=True)
    report={'scope':'Real pinned geometry and renderer; editorial query is a scripted fixture; no LLM/TTS',
        'duration':12,'size':[1920,1080],'frames':144,'full_decode':True,'deterministic':True,'video':str(video)}
    write(out/'render-report.json',report);print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
