"""Real renderer previews and document exports without sources. No LLM/TTS/video claim.

Usage: .venv/Scripts/python tests/research_visual_smoke.py --base-work <existing atlas workspace>
Reuses immutable geographic assets and preserves the original production.
"""
import argparse,json,os,shutil,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def worker(work):
    sys.path.insert(0,str(work))
    from engine.common import read_json,write_json,validate_pack
    from engine.history_schema import estimate_timeline
    from engine.export import export_documents
    from engine.visuals import Visuals
    pack=read_json(work/'documentaries/research-preview/documentary.json')
    validate_pack(pack)
    timeline=estimate_timeline(pack)
    write_json(work/'timeline.json',timeline)
    write_json(work/'build/research-preview/timeline.json',timeline)
    export_documents(timeline)
    visual=Visuals(timeline)
    out=work/'output/previews';out.mkdir(parents=True,exist_ok=True)
    for scene in timeline['scenes']:
        a=visual.frame(scene,scene['duration']*.55)
        b=visual.frame(scene,scene['duration']*.55)
        assert a.tobytes()==b.tobytes(),'Non-deterministic same-time frame'
        a.save(out/(scene['id']+'.jpg'),quality=92)
    assert 'Nessuna pagina esterna consultabile' in (work/'sources.md').read_text(encoding='utf-8')
    print(json.dumps({'scope':'Real 1080p map/comparison previews and estimated editorial exports; no TTS, video or remote LLM.',
                      'previews':[str(p) for p in out.glob('*.jpg')],'empty_sources':True,'same_time_frames_identical':True},indent=2))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base-work',type=Path);parser.add_argument('--worker',type=Path)
    args=parser.parse_args()
    if args.worker:return worker(args.worker.resolve())
    if not args.base_work:parser.error('--base-work is required')
    os.environ['DOCUMENTARIAI_DATA']=str(ROOT/'tests/output/research-visual')
    sys.path.insert(0,str(ROOT))
    from app.pipeline import isolate
    from app.research import assessment
    from app.store import write_json,read_json
    work,python=isolate('visual',ROOT/'pipeline')
    base=args.base_work.resolve();atlas=read_json(base/'assets/geography/atlas-film/atlas.json')
    for layer in atlas['layers']:
        layer['levels']=[str(base/p) for p in layer['levels']]
        if layer.get('alpha'):layer['alpha']=str(base/layer['alpha'])
    write_json(work/'assets/geography/atlas-film/atlas.json',atlas)
    shutil.copy2(base/'assets/geography/rivers.geojson',work/'assets/geography/rivers.geojson')
    scenes=[]
    for i,kind in enumerate(['map_overview','comparison']):
        scenes.append(dict(id=f'{i+1:02}',title='Prova senza fonti' if i==0 else 'Due livelli di conoscenza',date='Prova tecnica',
            historical_range=[2026,2026],scene_type=kind,location_ids=['capua','benevento'],sources=[],
            lines=['Questa è una prova tecnica del motore, con riferimenti bibliografici vuoti.',
                   'Le informazioni prive di riscontri sono segnalate nei documenti del progetto.'],
            facts=['Prova tecnica · contenuti da verificare'],kicker='Ricerca ibrida',
            comparison=[dict(title='Pagine consultate',text='I riferimenti rimandano soltanto a pagine effettivamente acquisite.'),
                        dict(title='Conoscenza del modello',text='I contenuti senza riscontri esterni restano da verificare.')]))
    pack=dict(schema_version=2,documentary_type='general_history',slug='research-preview',title='Ricerca ibrida · prova tecnica',
              short_title='Ricerca ibrida',historical_period={'start':2026,'end':2026},target_minutes=1,fps=24,
              locations=[dict(id='capua',name='Capua',pos=[14.214,41.106]),dict(id='benevento',name='Benevento',pos=[14.781,41.13])],
              sources=[],scenes=scenes,atlas='assets/geography/atlas-film/atlas.json')
    sys.path.insert(0,str(ROOT/'pipeline'))
    from engine.research_provenance import apply_context
    apply_context(pack,assessment([]))
    write_json(work/'documentaries/research-preview/documentary.json',pack)
    result=subprocess.run([str(python),'-X','utf8',str(Path(__file__).resolve()),'--worker',str(work)],
                          cwd=work,text=True,encoding='utf-8',capture_output=True,check=True)
    (work.parent/'verification.json').write_text(result.stdout,encoding='utf-8')
    print(result.stdout)


if __name__=='__main__':main()
