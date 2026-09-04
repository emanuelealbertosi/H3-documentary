"""Real 1080p directed journey frames. No LLM, TTS or historical claims."""
import argparse,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def worker(work):
    sys.path.insert(0,str(work))
    from engine.common import read_json,write_json,validate_pack
    from engine.history_schema import estimate_timeline
    from engine.visuals import Visuals
    doc=read_json(work/'documentaries/journey/documentary.json');validate_pack(doc)
    timeline=estimate_timeline(doc);write_json(work/'timeline.json',timeline);visual=Visuals(timeline)
    out=work/'output/previews';out.mkdir(parents=True,exist_ok=True);paths=[];changed=[]
    for scene in timeline['scenes']:
        times=[scene['duration']*.18,scene['duration']*.78] if scene.get('schematic_journey') else [scene['duration']*.55]
        frames=[]
        for n,t in enumerate(times):
            im=visual.frame(scene,t);assert im.size==(1920,1080);assert im.tobytes()==visual.frame(scene,t).tobytes()
            path=out/f'{scene["id"]}-{n}.jpg';im.save(path,quality=92);paths.append(str(path));frames.append(im)
        if len(frames)==2:changed.append(frames[0].tobytes()!=frames[1].tobytes())
    assert all(changed)
    print(json.dumps({'previews':paths,'same_time_frames_identical':True,'journey_advances':True}))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base-work',type=Path);parser.add_argument('--portrait',type=Path);parser.add_argument('--worker',type=Path)
    args=parser.parse_args()
    if args.worker:return worker(args.worker.resolve())
    if not args.base_work:parser.error('--base-work is required')
    os.environ['DOCUMENTARIAI_DATA']=str(ROOT/'tests/output/visual-direction')
    sys.path.insert(0,str(ROOT));from app.pipeline import isolate
    from app.store import read_json,write_json
    from app.research import assessment
    work,python=isolate('journey',ROOT/'pipeline');base=args.base_work.resolve()
    atlas=read_json(base/'assets/geography/atlas-film/atlas.json')
    for layer in atlas['layers']:
        layer['levels']=[str(base/p) for p in layer['levels']]
        if layer.get('alpha'):layer['alpha']=str(base/layer['alpha'])
    write_json(work/'assets/geography/atlas-film/atlas.json',atlas)
    shutil.copy2(base/'assets/geography/rivers.geojson',work/'assets/geography/rivers.geojson')
    portrait=''
    if args.portrait:
        target=work/'assets/portraits/journey/odisseo.jpg';target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(args.portrait,target);portrait=target.relative_to(work).as_posix()
    common={'date':'Tradizione epica','historical_range':[-1200,-1100],'sources':[],
            'lines':['Questa è una prova tecnica dichiarata della regia visuale.','Non costituisce una ricostruzione geografica del viaggio.'],
            'facts':['Prova tecnica · sequenza narrativa, non rotta storica'],'kicker':'Regia di viaggio','person_ids':['odisseo'],'event_ids':[],'asset_ids':[],'territory_ids':[],'movements':[]}
    scenes=[{**common,'id':'01','title':'Partenza e destinazione','scene_type':'map_overview','location_ids':['troia','itaca']},
            {**common,'id':'02','title':'Tappe non localizzate','scene_type':'animated_route','location_ids':['troia','itaca'],
             'schematic_journey':{'stops':['Troia','Tempesta','Racconto','Itaca'],'note':'Sequenza letteraria; le tappe intermedie non sono collocate sulla carta.'}},
            {**common,'id':'03','title':'Arrivo','scene_type':'map_overview','location_ids':['itaca']}]
    direction={'version':1,'journey':True,'map_led':True,'timeline_mode':'sequence','auto_persons':True}
    pack={'schema_version':2,'documentary_type':'exploration','slug':'journey','title':'Prova della regia di viaggio','short_title':'Regia di viaggio',
          'historical_period':{'start':-1200,'end':-1100},'target_minutes':1,'fps':24,'locations':[{'id':'troia','name':'Troia','pos':[26.24,39.96]},{'id':'itaca','name':'Itaca','pos':[20.67,38.4]}],
          'persons':[{'id':'odisseo','name':'Odisseo','role':'Protagonista della tradizione epica','period':'Tradizione epica','portrait':portrait}],
          'entities':[],'events':[],'visual_layers':[],'visual_assets':[],'scenes':scenes,'sources':[],
          'overview':[23.45,39.2,13],'atlas':'assets/geography/atlas-film/atlas.json','visual_direction':direction,'metadata':{'visual_direction':direction}}
    sys.path.insert(0,str(ROOT/'pipeline'))
    from engine.research_provenance import apply_context
    apply_context(pack,assessment([]));write_json(work/'documentaries/journey/documentary.json',pack)
    result=subprocess.run([str(python),'-B','-X','utf8',str(Path(__file__).resolve()),'--worker',str(work)],cwd=work,text=True,encoding='utf-8',capture_output=True)
    assert result.returncode==0,result.stderr;report={'scope':'Real deterministic 1080p maps, animated literary sequence and automatic portrait. No LLM/TTS/full video.',**json.loads(result.stdout)}
    write_json(work.parent/'verification.json',report);print(json.dumps({'report':str(work.parent/'verification.json'),**report},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
