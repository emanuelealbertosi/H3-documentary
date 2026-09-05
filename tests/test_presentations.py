import hashlib,inspect,json,subprocess,threading
from concurrent.futures import Future
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from app import presentations,store,runner
from app.models import ProjectRequest
from app.server import app


@pytest.fixture
def job(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);monkeypatch.setattr(store,'JOBS',tmp_path/'jobs')
    (tmp_path/'jobs').mkdir();store.init()
    p=store.create(ProjectRequest(topic='Prova presentazione',start=False))
    store.update(p['id'],status='completed')
    work=store.JOBS/p['id']/'workspace';work.mkdir()
    (work/'timeline.json').write_text('{"title":"Dati conservati"}')
    monkeypatch.setattr(presentations,'FUTURES',{})
    monkeypatch.setattr(presentations,'PROCESSES',{})
    monkeypatch.setattr(presentations,'STOPPING',False)
    monkeypatch.setattr(runner,'FUTURES',{})
    return p['id'],work


def test_export_is_separate_preserves_previous_files_and_reports_progress(job,monkeypatch):
    pid,work=job
    original=hashlib.sha256((work/'timeline.json').read_bytes()).hexdigest()
    class Process:
        def __init__(self,args,**kwargs):
            assert args[3].endswith('export_presentation.py')
            assert '--variant' in args and '--narration' in args
            target=Path(args[args.index('--output')+1])
            writer=PdfWriter();writer.add_blank_page(width=960,height=540)
            with target.open('wb') as f:writer.write(f)
            self.stdout=iter(['PDF_PROGRESS '+json.dumps({'done':1,'total':1,'message':'Pagina pronta'})+'\n'])
        def wait(self):return 0
    monkeypatch.setattr(presentations.subprocess,'Popen',Process)
    for variant in ['compact','teaching']:
        presentations._produce(pid,presentations.PresentationRequest(variant=variant))
    result=presentations.status(pid)
    assert result['status']=='completed' and result['progress']==100
    assert len(result['exports'])==2 and all(x['pages']==1 for x in result['exports'])
    assert store.project(pid)['status']=='completed'
    assert hashlib.sha256((work/'timeline.json').read_bytes()).hexdigest()==original
    assert all((store.JOBS/pid/item['path']).is_file() for item in result['exports'])


def test_export_failure_does_not_fail_completed_video(job,monkeypatch):
    pid,_=job
    def broken(*args,**kwargs):raise OSError('test exporter failure')
    monkeypatch.setattr(presentations.subprocess,'Popen',broken)
    presentations._produce(pid,presentations.PresentationRequest())
    assert presentations.status(pid)['status']=='failed'
    assert store.project(pid)['status']=='completed'


def test_export_waits_for_timeline_and_inactive_production(job):
    pid,work=job
    store.update(pid,status='running')
    with pytest.raises(ValueError,match='Attendi'):presentations.start(pid,presentations.PresentationRequest())
    store.update(pid,status='completed');(work/'timeline.json').unlink()
    assert not presentations.status(pid)['available']


def test_live_export_blocks_destructive_project_actions_and_ignores_external_paths(job):
    pid,_=job
    future=Future();presentations.FUTURES[pid]=future
    client=TestClient(app);client.headers['X-DocumentariAI']='studio'
    response=client.delete('/api/projects/'+pid)
    assert response.status_code==409
    assert store.project(pid)['status']=='completed'
    future.set_result(None)
    presentations._save(pid,status='running',exports=[{'path':'../private.pdf'}])
    state=presentations.status(pid)
    assert state['status']=='interrupted' and not state['exports']


def test_failed_setup_is_reported_and_does_not_change_video(job,monkeypatch):
    pid,work=job
    (work/'output').write_text('File in place of output directory')
    monkeypatch.setattr(presentations.subprocess,'Popen',lambda *a,**k:pytest.fail('Worker must not start after setup failure'))
    presentations._produce(pid,presentations.PresentationRequest())
    state=presentations.status(pid)
    assert state['status']=='failed' and state['error']
    assert store.project(pid)['status']=='completed' and not presentations.PROCESSES


def test_unavailable_project_does_not_reappear_after_worker_failure(job,monkeypatch):
    pid,_=job
    store.delete_project(pid)
    monkeypatch.setattr(presentations.subprocess,'Popen',lambda *a,**k:pytest.fail('Deleted project cannot start a worker'))
    presentations._produce(pid,presentations.PresentationRequest())
    assert not (store.JOBS/pid).exists() and not presentations.PROCESSES


def test_restart_hides_missing_old_exports_without_claiming_ready(job):
    pid,work=job
    output=work/'output/presentations/previous.pdf';output.parent.mkdir(parents=True);output.write_bytes(b'%PDF previous')
    presentations._save(pid,status='completed',progress=100,message='Presentazione pronta.',exports=[{'path':output.relative_to(store.JOBS/pid).as_posix()}])
    assert presentations.status(pid)['exports']
    store.update(pid,status='failed');store.restart_project(pid)
    state=presentations.status(pid)
    assert state['status']=='unavailable' and state['progress']==0 and not state['exports'] and not state['available']
    assert 'precedente non è disponibile' in state['message']
    assert list((store.JOBS/pid/'attempts').glob('*/workspace/output/presentations/previous.pdf'))


def test_bad_export_entries_are_not_returned_or_crash_status(job):
    pid,work=job
    status_path=store.JOBS/pid/'presentation-status.json'
    for value in ([],{'exports':None},{'exports':['bad',None,{'path':None},{'path':'../private.pdf'}]}):
        status_path.write_text(json.dumps(value),encoding='utf-8')
        assert presentations.status(pid)['exports']==[]


class WaitingPool:
    def __init__(self):self.future=Future();self.calls=[];self.closed=False
    def submit(self,*args):self.calls.append(args);return self.future
    def shutdown(self,**kwargs):self.closed=kwargs


def test_guard_keeps_signature_and_blocks_mutation_after_export_is_queued(job,monkeypatch):
    pid,work=job;pool=WaitingPool();monkeypatch.setattr(presentations,'POOL',pool)
    changed=[]
    @presentations.project_mutation
    def change(pid:str,value:int=3):
        changed.append(pid);return value
    assert str(inspect.signature(change))=="(pid: str, value: int = 3)" and change.__name__=='change'
    presentations.start(pid,presentations.PresentationRequest())
    with pytest.raises(ValueError,match='esportazione PDF'):change(pid)
    assert not changed and (work/'timeline.json').exists()
    pool.future.set_result(None)
    assert change(pid,7)==7 and changed==[pid]
    async def async_change(pid):pass
    with pytest.raises(TypeError,match='sincrona'):presentations.project_mutation(async_change)


def test_export_start_waits_until_mutation_has_finished(job,monkeypatch):
    pid,work=job;pool=WaitingPool();monkeypatch.setattr(presentations,'POOL',pool)
    entered=threading.Event();release=threading.Event();starting=threading.Event();finished=threading.Event();errors=[]
    @presentations.project_mutation
    def invalidate(pid):
        entered.set()
        if not release.wait(3):raise TimeoutError('Test gate timed out')
        (work/'timeline.json').unlink()
    def mutate():
        try:invalidate(pid)
        except Exception as error:errors.append(error)
    def export():
        starting.set()
        try:presentations.start(pid,presentations.PresentationRequest())
        except Exception as error:errors.append(error)
        finally:finished.set()
    mutation=threading.Thread(target=mutate);exporter=threading.Thread(target=export)
    mutation.start()
    try:
        assert entered.wait(2);exporter.start();assert starting.wait(2)
        assert not finished.wait(.05)
    finally:
        release.set();mutation.join(3)
        if exporter.ident is not None:exporter.join(3)
    assert not mutation.is_alive() and not exporter.is_alive() and not pool.calls
    assert len(errors)==1 and isinstance(errors[0],ValueError) and 'timeline' in str(errors[0])


def test_shutdown_cannot_miss_process_between_creation_and_registration(job,monkeypatch):
    pid,_=job;pool=WaitingPool();monkeypatch.setattr(presentations,'POOL',pool)
    creating=threading.Event();created=threading.Event();terminated=threading.Event();stopping=threading.Event();stopped=threading.Event()
    actions=[];errors=[]
    class Process:
        def __init__(self,*args,**kwargs):
            creating.set()
            if not created.wait(3):raise TimeoutError('Test creation gate timed out')
            self.stdout=self.lines()
        def lines(self):
            if not terminated.wait(3):raise TimeoutError('Test termination gate timed out')
            yield from ()
        def poll(self):return -15 if terminated.is_set() else None
        def terminate(self):actions.append('terminate');terminated.set()
        def kill(self):actions.append('kill');terminated.set()
        def wait(self,timeout=None):
            if not terminated.wait(timeout or 3):raise subprocess.TimeoutExpired('fake',timeout)
            return -15
    monkeypatch.setattr(presentations.subprocess,'Popen',Process)
    def stop():
        stopping.set()
        try:presentations.shutdown()
        except Exception as error:errors.append(error)
        finally:stopped.set()
    producer=threading.Thread(target=presentations._produce,args=(pid,presentations.PresentationRequest()))
    stopper=threading.Thread(target=stop);producer.start()
    try:
        assert creating.wait(2);stopper.start();assert stopping.wait(2)
        assert not stopped.wait(.05)
    finally:
        created.set();producer.join(4)
        if stopper.ident is not None:stopper.join(4)
        terminated.set()
    assert not producer.is_alive() and not stopper.is_alive() and not errors
    assert actions==['terminate'] and not presentations.PROCESSES and pool.closed
    assert presentations.status(pid)['status']=='interrupted'


def test_shutdown_escalates_to_kill_and_rejects_new_work(job,monkeypatch):
    pid,_=job;pool=WaitingPool();monkeypatch.setattr(presentations,'POOL',pool)
    actions=[]
    class Stubborn:
        def poll(self):return None
        def terminate(self):actions.append('terminate')
        def kill(self):actions.append('kill')
        def wait(self,timeout):
            actions.append(('wait',timeout))
            if 'kill' not in actions:raise subprocess.TimeoutExpired('fake',timeout)
            return -9
    presentations.PROCESSES[pid]=Stubborn();presentations.FUTURES[pid]=pool.future
    presentations.shutdown()
    assert actions==['terminate',('wait',5),'kill',('wait',5)]
    assert pool.future.cancelled() and pool.closed=={'wait':False,'cancel_futures':True}
    assert not presentations.FUTURES and not presentations.PROCESSES
    with pytest.raises(ValueError,match='chiudendo'):presentations.start(pid,presentations.PresentationRequest())
    monkeypatch.setattr(presentations.subprocess,'Popen',lambda *a,**k:pytest.fail('Cannot start worker during shutdown'))
    presentations._produce(pid,presentations.PresentationRequest())
    assert presentations.status(pid)['status']=='interrupted'
