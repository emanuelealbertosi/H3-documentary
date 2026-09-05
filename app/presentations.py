"""Independent, local PDF exports of measured documentary timelines."""
import inspect,json,subprocess,threading,time
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from pathlib import Path
from typing import Literal
from pydantic import BaseModel
from fastapi import APIRouter,HTTPException
from . import store
from .paths import ROOT

POOL=ThreadPoolExecutor(max_workers=1,thread_name_prefix='presentation')
LOCK=threading.RLock()
FUTURES={}
PROCESSES={}
STOPPING=False
router=APIRouter(prefix='/api/projects')


class PresentationRequest(BaseModel):
    variant:Literal['compact','teaching']='compact'
    narration:Literal['full','none']='full'


def active(pid=None):
    with LOCK:
        return any(not f.done() for key,f in FUTURES.items() if pid is None or key==pid)


def _folder(pid):
    store.project(pid)
    root=store.JOBS.resolve();folder=(root/pid).resolve()
    if folder.parent!=root:raise ValueError('Progetto non valido.')
    return folder


def _read(pid):
    path=_folder(pid)/'presentation-status.json'
    try:state=store.read_json(path) if path.is_file() else {}
    except (OSError,ValueError):state={}
    if not isinstance(state,dict):state={}
    exports=state.get('exports',[])
    state['exports']=[item for item in exports if isinstance(item,dict) and isinstance(item.get('path'),str)] if isinstance(exports,list) else []
    return state


def _save(pid,**changes):
    with LOCK:
        state=_read(pid);state.update(changes,updated=store.now())
        store.write_json(_folder(pid)/'presentation-status.json',state)
    return state


def status(pid):
    p=store.project(pid);work=_folder(pid)/'workspace'
    ready=(work/'timeline.json').is_file() or any((work/'build').glob('*/timeline.json'))
    busy=p['status'] in ('running','queued','cancelling')
    state=_read(pid)
    if state.get('status') in ('queued','running') and not active(pid):
        state={**state,'status':'interrupted','message':'Esportazione interrotta dal riavvio. Puoi crearla nuovamente.'}
    exports=[]
    for item in state.get('exports',[]):
        path=(_folder(pid)/item.get('path','')).resolve()
        if path.is_relative_to(work.resolve()/'output/presentations') and path.is_file():exports.append(item)
    state['exports']=exports
    if state.get('status')=='completed' and not exports:
        state={**state,'status':'unavailable','progress':0,
               'message':'La presentazione precedente non è disponibile nel progetto attuale. Puoi crearne una nuova.'}
    return {**state,'available':ready and not busy,'busy':active(pid),
            'reason':'Attendi la fine della produzione.' if busy else '' if ready else 'Disponibile dopo la creazione della voce e della timeline.'}


def ensure_idle(pid):
    with LOCK:
        if STOPPING:raise ValueError('L’app si sta chiudendo. Riaprila prima di modificare il progetto.')
        if active(pid):raise ValueError('Attendi la fine dell’esportazione PDF prima di modificare il progetto.')


def project_mutation(function):
    """Serialize a synchronous project mutation with PDF scheduling.

    Checking in middleware alone leaves a gap before the endpoint executes.
    Async endpoints must parse their request first and use a synchronous guarded
    helper; a thread RLock cannot protect code across coroutine suspension.
    """
    if inspect.iscoroutinefunction(function):raise TypeError('project_mutation richiede una funzione sincrona.')
    @wraps(function)
    def protected(pid,*args,**kwargs):
        from . import runner
        with runner.LOCK,store.LOCK:
            ensure_idle(pid)
            return function(pid,*args,**kwargs)
    return protected


def start(pid,options):
    from . import runner
    with runner.LOCK,store.LOCK,LOCK:
        if STOPPING:raise ValueError('L’app si sta chiudendo. Riaprila prima di esportare la presentazione.')
        current=status(pid)
        if not current['available']:raise ValueError(current['reason'])
        if active(pid):raise ValueError('La presentazione è già in preparazione.')
        _save(pid,status='queued',message='Presentazione PDF in coda.',error='',progress=0,options=options.model_dump())
        FUTURES[pid]=POOL.submit(_produce,pid,options)
    return status(pid)


def _produce(pid,options):
    try:
        with LOCK:
            if STOPPING:raise RuntimeError('Esportazione interrotta dalla chiusura dell’app.')
        folder=_folder(pid);work=folder/'workspace'
        stamp=str(time.time_ns())
        target=work/'output/presentations'/f'presentazione_{options.variant}_{options.narration}_{stamp}.pdf'
        if not target.resolve().is_relative_to(folder):raise ValueError('Percorso di esportazione non valido.')
        target.parent.mkdir(parents=True,exist_ok=True)
        manifest=target.with_suffix('.json')
        log=folder/'presentation-export.log'
        _save(pid,status='running',message='Preparazione delle pagine.',progress=1)
        command=[str(ROOT/'pipeline/.venv/Scripts/python.exe'),'-X','utf8',str(ROOT/'pipeline/tools/export_presentation.py'),
                 '--workspace',str(work),'--output',str(target),'--manifest',str(manifest),
                 '--variant',options.variant,'--narration',options.narration]
        with log.open('w',encoding='utf-8') as record:
            with LOCK:
                if STOPPING:raise RuntimeError('Esportazione interrotta dalla chiusura dell’app.')
                process=subprocess.Popen(command,cwd=work,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
                PROCESSES[pid]=process
            for line in process.stdout:
                record.write(line);record.flush()
                if line.startswith('PDF_PROGRESS '):
                    try:
                        value=json.loads(line[len('PDF_PROGRESS '):])
                        progress=min(98,round(100*float(value['done'])/max(1,float(value['total']))))
                        _save(pid,progress=progress,message=str(value.get('message','Preparazione delle pagine.'))[:250])
                    except (KeyError,TypeError,ValueError):pass
            if process.wait()!=0:raise ValueError('Esportazione PDF non completata. Dettagli nel registro della presentazione.')
        from pypdf import PdfReader
        reader=PdfReader(str(target));pages=len(reader.pages)
        if pages<1:raise ValueError('La presentazione non contiene pagine.')
        item={'path':target.relative_to(folder).as_posix(),'name':target.name,'pages':pages,'bytes':target.stat().st_size,
              **options.model_dump(),'created':store.now()}
        _save(pid,status='completed',progress=100,message=f'Presentazione pronta: {pages} pagine.',error='',
              exports=[*_read(pid).get('exports',[]),item])
    except Exception as error:
        try:
            _save(pid,status='interrupted' if STOPPING else 'failed',error=str(error)[:1200],
                  message='Esportazione interrotta dalla chiusura dell’app.' if STOPPING else 'Esportazione PDF non riuscita. Il video resta disponibile.')
        except Exception:
            # A deleted/unavailable project or unwritable disk must not obscure
            # the original export error or leave the process registry occupied.
            pass
    finally:
        with LOCK:PROCESSES.pop(pid,None)


def shutdown():
    global STOPPING
    with LOCK:
        STOPPING=True
        processes=list(PROCESSES.values());PROCESSES.clear()
        futures=list(FUTURES.values());FUTURES.clear()
    for future in futures:future.cancel()
    for process in processes:
        try:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait(timeout=5)
        except (OSError,subprocess.SubprocessError):pass
    POOL.shutdown(wait=False,cancel_futures=True)


@router.get('/{pid}/presentation')
def get_presentation(pid:str):return status(pid)


@router.post('/{pid}/presentation',status_code=202)
def create_presentation(pid:str,value:PresentationRequest):
    try:return start(pid,value)
    except ValueError as error:raise HTTPException(409,str(error)) from error
