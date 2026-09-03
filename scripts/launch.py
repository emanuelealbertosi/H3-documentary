"""Detached local server with readiness checks, instance-aware relaunch and logs."""
import argparse,json,os,subprocess,sys,time,webbrowser
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]

def health(client,url):
    try:
        response=client.get(url+'/api/health');response.raise_for_status()
    except httpx.ConnectError:return None
    except httpx.HTTPError as error:raise RuntimeError('La porta risponde ma non offre un servizio H3 valido.') from error
    payload=response.json()
    if payload.get('service')!='h3-documentary' or Path(payload.get('instance','')).resolve()!=ROOT:
        raise RuntimeError('La porta è occupata da un’altra applicazione o copia di H3. Usa AVVIA.bat -Port 8776.')
    return payload

def launch(port=8775,open_browser=True):
    if not 1024<=port<=65535:raise ValueError('Porta non valida (1024–65535).')
    url=f'http://127.0.0.1:{port}';data=ROOT/'data';data.mkdir(exist_ok=True)
    with httpx.Client(timeout=3,trust_env=False) as client:
        if not health(client,url):
            with (data/'server.stdout.log').open('ab') as out,(data/'server.stderr.log').open('ab') as err:
                flags=(subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else 0
                child=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),'-X','utf8',str(ROOT/'run.py'),'--port',str(port)],cwd=ROOT,stdout=out,stderr=err,stdin=subprocess.DEVNULL,creationflags=flags)
            for _ in range(60):
                if child.poll() is not None:raise RuntimeError('Il server si è fermato: consulta data/server.stderr.log.')
                if health(client,url):break
                time.sleep(.5)
            else:raise RuntimeError('Il server non è pronto. Consulta data/server.stderr.log.')
            (data/'server.json').write_text(json.dumps({'pid':child.pid,'url':url,'root':str(ROOT)}),encoding='utf-8')
    if open_browser:webbrowser.open(url)
    print('H3-documentary pronto: '+url,flush=True)
    return url

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8775);p.add_argument('--no-browser',action='store_true');a=p.parse_args()
    try:launch(a.port,not a.no_browser)
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
