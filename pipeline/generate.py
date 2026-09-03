"""One entrance: authored documents locally, natural-language production through Studio."""
import argparse,sys,subprocess,time,re,json
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def ensure_geography(pack,path):
    """Rebuild a missing shared atlas with the existing geographic tools."""
    if not pack.get('atlas'):return
    atlas=ROOT/pack['atlas']
    if atlas.exists():return
    candidates=[path.parent/'geography.json',ROOT/'documentaries/geography.json',*ROOT.glob('documentaries/*/geography.json'),*ROOT.glob('battles/*/geography.json')]
    config=next((p for p in candidates if p.exists() and (ROOT/json.loads(p.read_text(encoding='utf-8'))['output']/'atlas.json').resolve()==atlas.resolve()),None)
    if config is None:raise ValueError('Atlante mancante: conserva geography.json insieme al documentario per ricostruirlo automaticamente.')
    for tool in ['acquire_atlas.py','prepare_atlas.py']:
        subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tools'/tool),'--config',str(config)],cwd=ROOT,check=True)

def minutes(value):
    m=re.fullmatch(r'(\d+(?:\.\d+)?)(m|min|s)?',value.strip())
    if not m:raise argparse.ArgumentTypeError('Durata come 12m o 720s')
    value=float(m[1])/(60 if m[2]=='s' else 1)
    if not 2<=value<=60:raise argparse.ArgumentTypeError('Durata supportata: 2–60 minuti')
    return value

def studio(topic,duration,kind,wait=True):
    import requests,os
    endpoint=os.environ.get('H3_STUDIO_URL','http://127.0.0.1:8775');session=requests.Session();session.trust_env=False
    session.headers['X-DocumentariAI']='studio'
    try:r=session.get(endpoint+'/api/health',timeout=3);r.raise_for_status()
    except requests.RequestException:
        app=ROOT.parent;python=app/'.venv/Scripts/python.exe'
        if not python.exists():raise ValueError('H3 non installato. Apri INSTALLA.bat.')
        (app/'data').mkdir(exist_ok=True)
        log=(app/'data/cli-launcher.log').open('ab')
        subprocess.Popen([str(python),'run.py','--port',str(__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(endpoint).port or 8775)],cwd=app,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0);log.close()
        for _ in range(30):
            time.sleep(.5)
            try:
                r=session.get(endpoint+'/api/health',timeout=2)
                if r.ok:break
            except requests.RequestException:pass
        else:raise ValueError('Studio non si avvia; consulta data/cli-launcher.log')
    if r.json().get('service')!='h3-documentary' or Path(r.json().get('instance','')).resolve()!=ROOT.parent:raise ValueError('La porta locale è occupata da un altro servizio o un’altra copia di H3')
    if not r.json().get('configured'):raise ValueError('Collega una volta il tuo modello gratuito in http://127.0.0.1:8775/admin (LM Studio, Ollama, vLLM o API compatibile). Nessun modello esterno è attualmente configurato.')
    if duration!=int(duration):raise ValueError('Per una nuova produzione da argomento usa minuti interi')
    response=session.post(endpoint+'/api/projects',json={'topic':topic,'minutes':int(duration),'documentary_type':kind,'start':True},timeout=30)
    if not response.ok:raise ValueError(response.text)
    project=response.json();pid=project['id'];print(endpoint+'/projects/'+pid,flush=True)
    if not wait:return
    cursor=0
    while True:
        p=session.get(endpoint+'/api/projects/'+pid,timeout=15).json()
        events=session.get(endpoint+f'/api/projects/{pid}/events?after={cursor}',timeout=15).json()
        for e in events:print(e['message'],flush=True);cursor=e['id']
        if p['status']=='completed':
            print('MP4 verificato:',ROOT.parent/'data/jobs'/pid/'workspace/output'/('film-'+pid+'_documentario_1080p.mp4'));return
        if p['status'] in ('failed','cancelled','interrupted','draft'):raise ValueError(p.get('error') or p['stage'])
        time.sleep(3)

def main():
    from engine.history_profiles import PROFILES,detect_type
    p=argparse.ArgumentParser(description='Documentari storici visuali: ricerca, voce italiana, animazioni e MP4')
    p.add_argument('topic',nargs='?');p.add_argument('--duration',type=minutes)
    p.add_argument('--type',choices=['auto',*PROFILES],default='auto')
    p.add_argument('--pack',type=Path,help='Riutilizza un documentario o un battle pack già scritto')
    p.add_argument('--example',choices=['rinascimento','impero-romano','migrazioni-germaniche','via-della-seta','napoleone-biografia','waterloo'])
    p.add_argument('--prepare-only',action='store_true',help='Esporta script, fonti, timeline stimata e anteprime di un pack esistente')
    p.add_argument('--jobs',type=int,default=2,choices=range(1,5));p.add_argument('--no-wait',action='store_true',help='Accoda in Studio e restituisce il collegamento')
    args=p.parse_args();path=args.pack
    if args.example:path=ROOT/('battles/waterloo/battle.json' if args.example=='waterloo' else f'documentaries/{args.example}/documentary.json')
    if path:
        from engine.common import read_json,validate_pack
        path=path.resolve();raw=read_json(path);pack=validate_pack(raw)
        if args.type!='auto' and args.type!=pack.get('documentary_type','battle'):raise ValueError('Il tipo di un pack scritto si modifica nella fase editoriale, non cambiando il solo renderer.')
        if args.duration and abs(args.duration-pack['target_minutes'])>.01:raise ValueError('Il pack ha già una sceneggiatura dimensionata. Per una nuova durata usa la richiesta in linguaggio naturale senza --pack/--example.')
        ensure_geography(pack,path)
        if args.prepare_only:
            subprocess.run([sys.executable,'-X','utf8',str(ROOT/'documentary.py'),'assets','--document',str(path)],cwd=ROOT,check=True)
            if raw.get('schema_version')==2:
                from tools.preview_history import preview
                preview(path)
            else:subprocess.run([sys.executable,'tools/preview_pack.py',str(path)],cwd=ROOT,check=True)
            return
        for command in ['assets','voice','preview','render','finalize','verify']:
            subprocess.run([sys.executable,'-X','utf8',str(ROOT/'documentary.py'),command,'--document',str(path),'--jobs',str(args.jobs)],cwd=ROOT,check=True)
            if pack.get('documentary_schema_version')==2 and command=='voice':
                subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tools/history_layout.py'),str(path)],cwd=ROOT,check=True)
        if pack.get('documentary_schema_version')==2:
            subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tools/check_history_final.py'),pack['slug']],cwd=ROOT,check=True)
        return
    if not args.topic:p.error('Indica un argomento, --pack o --example')
    if args.prepare_only:p.error('--prepare-only si usa con --pack o --example; una nuova richiesta in linguaggio naturale esegue tutta la produzione')
    print('Tipo suggerito:',detect_type(args.topic) if args.type=='auto' else args.type,flush=True)
    studio(args.topic,args.duration or 10,args.type,not args.no_wait)

if __name__=='__main__':
    try:main()
    except (ValueError,FileNotFoundError) as e:print(str(e),file=sys.stderr);sys.exit(2)
