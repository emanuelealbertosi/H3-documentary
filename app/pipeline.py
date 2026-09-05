"""Isolated workspaces. The existing production project is only ever read."""
from pathlib import Path
import os,shutil,subprocess,time,json,threading,copy
from .paths import ROOT,JOBS
from .store import read_json,write_json
class Cancelled(Exception):pass
PROCESSES={};LOCK=threading.Lock()
def verify_pipeline(path):
    p=Path(path).resolve()
    for f in ["documentary.py","engine/common.py","engine/atlas.py",".venv/Scripts/python.exe",
              "assets/voice/kokoro/kokoro-v1.0.onnx","assets/voice/kokoro/voices-v1.0.bin"]:
        if not(p/f).is_file():raise ValueError("Pipeline incompleta: manca "+f)
    return p
def isolate(pid,source):
    source=verify_pipeline(source);work=JOBS/pid/"workspace"
    if work.resolve().is_relative_to(source):raise ValueError("Il progetto dell’app deve essere separato dalla pipeline originale.")
    work.mkdir(exist_ok=True,parents=True)
    for folder in ["engine","tools"]:
        if not(work/folder).exists():
            shutil.copytree(source/folder,work/folder,ignore=shutil.ignore_patterns("__pycache__"))
    if not(work/"documentary.py").exists():shutil.copy2(source/"documentary.py",work/"documentary.py")
    (work/"assets").mkdir(exist_ok=True)
    # Hard links only for immutable input files. Outputs and mutable manifests are separate.
    for folder in ["fonts","voice/kokoro","geography/naturalearth","geography/terrain"]:
        source_dir=source/"assets"/folder
        if not source_dir.exists():continue
        for file in source_dir.rglob("*"):
            if not file.is_file():continue
            dest=work/"assets"/file.relative_to(source/"assets")
            dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():
                try:os.link(file,dest)
                except OSError:shutil.copy2(file,dest)
    for name in ["NE2_HR_LC_SR_W.zip","rivers.geojson","land.geojson","lakes.geojson","terrain-attribution.md"]:
        original=source/"assets/geography"/name;dest=work/"assets/geography"/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if original.exists() and not dest.exists():
            try:os.link(original,dest)
            except OSError:shutil.copy2(original,dest)
    return work,source/".venv/Scripts/python.exe"

def prepare_hybrid_engine(work,source,checkpoints):
    """Upgrade only a bundled workspace stopped before authoring; preserve its old engine."""
    work=Path(work).resolve();source=Path(source).resolve();checkpoints=Path(checkpoints)
    if (work/'engine/research_provenance.py').is_file():return
    if source!=(ROOT/'pipeline').resolve() or not (source/'engine/research_provenance.py').is_file():
        raise ValueError('Il motore esterno non supporta la ricerca ibrida. Seleziona il motore incluso in Amministrazione e crea una nuova revisione.')
    if (checkpoints/'outline.json').exists() or any((work/'battles').glob('*/battle.json')):
        raise ValueError('Questo progetto contiene già scene del motore precedente. Crea una nuova revisione per usare la ricerca ibrida.')
    if not work.is_relative_to(JOBS.resolve()) or work.name!='workspace':
        raise ValueError('Aggiornamento consentito soltanto nello spazio isolato del progetto.')
    engine=(work/'engine').resolve()
    if engine.parent!=work:raise ValueError('Cartella del motore non valida.')
    backup=work/('engine-before-hybrid-'+str(time.time_ns()))
    if engine.exists():shutil.copytree(engine,backup)
    shutil.copytree(source/'engine',engine,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))

def prepare_history_asset_engine(work,source):
    """Apply the licensed-image fallback to resumable bundled workspaces."""
    work=Path(work).resolve();source=Path(source).resolve()
    if source!=(ROOT/'pipeline').resolve():return False
    if not work.is_relative_to(JOBS.resolve()) or work.name!='workspace':raise ValueError('Cartella del progetto non valida.')
    names=('acquire.py','history_assets.py');changed=[]
    for name in names:
        src=source/'engine'/name;dst=work/'engine'/name
        if not dst.exists() or src.read_bytes()!=dst.read_bytes():changed.append((src,dst))
    if not changed:return False
    backup=work/'engine-compat-backups'/('asset-'+str(time.time_ns()));backup.mkdir(parents=True)
    for src,dst in changed:
        if dst.exists():shutil.copy2(dst,backup/dst.name)
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
    return True

def prepare_bundled_runtime_engine(work,source):
    """Bring resumable bundled jobs onto compatible voice and visual fixes."""
    work=Path(work).resolve();source=Path(source).resolve()
    if source!=(ROOT/'pipeline').resolve():return False
    if not work.is_relative_to(JOBS.resolve()) or work.name!='workspace':raise ValueError('Cartella del progetto non valida.')
    relative_names=(
        Path('engine/narration.py'),Path('engine/atlas.py'),Path('engine/history_visuals.py'),
        Path('engine/history_territories.py'),Path('engine/history_schema.py'),
        Path('engine/acquire.py'),Path('engine/history_assets.py'),Path('engine/image_insets.py'),Path('engine/render.py'),
        Path('engine/image_rights.py'),Path('engine/image_search.py'),Path('engine/export.py'),
        Path('documentary.py'),
        Path('tools/chatterbox/synthesize_documentary.py'),
    )
    changed=[]
    for name in relative_names:
        src=source/name;dst=work/name
        if src.is_file() and (not dst.exists() or src.read_bytes()!=dst.read_bytes()):changed.append((src,dst,name))
    if not changed:return False
    backup=work/'engine-compat-backups'/('runtime-'+str(time.time_ns()));backup.mkdir(parents=True)
    for src,dst,name in changed:
        if dst.exists():
            saved=backup/name;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dst,saved)
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    return True


def reuse_atlas(work,source,geo):
    """Reuse existing Europe rasters by absolute read-only paths when they cover the view."""
    candidate=source/"assets/geography/atlas-v2/atlas.json"
    if not candidate.exists():return False
    atlas=read_json(candidate);base=atlas["layers"][0]
    import struct
    # Bounds are recorded with the source acquisition manifest.
    manifest=source/"assets/geography/manifest.json"
    if not manifest.exists():return False
    old=read_json(manifest).get("bounds");new=geo["bounds"]
    if not old or not(old[0]<=new[0] and old[1]<=new[1] and old[2]>=new[2] and old[3]>=new[3]):return False
    # Only reuse if every requested detailed patch also has coverage in the existing map.
    old_manifest=read_json(manifest);existing=old_manifest.get("patches",{})
    def area(bounds):return max(1e-9,(bounds[2]-bounds[0])*(bounds[3]-bounds[1]))
    def spec(value,default_zoom):
        return (value.get('bounds',[]),int(value.get('zoom',default_zoom))) if isinstance(value,dict) else (value,int(default_zoom))
    # Coverage alone is insufficient: a very broad old patch becomes blurred
    # when a later production asks for a close tactical view.
    old_default=old_manifest.get('terrain_zoom',8);new_default=geo.get('terrain_zoom',8)
    requested=[spec(v,new_default) for v in geo['patches'].values()]
    available=[spec(v,old_default) for v in existing.values()]
    if any(not any(o[0]<=b[0] and o[1]<=b[1] and o[2]>=b[2] and o[3]>=b[3] and oz>=bz and area(o)<=area(b)*8
                       for o,oz in available) for b,bz in requested):return False
    for layer in atlas["layers"]:
        layer["levels"]=[str(source/p) for p in layer["levels"]]
        if "alpha" in layer:layer["alpha"]=str(source/layer["alpha"])
    write_json(work/geo["output"]/"atlas.json",atlas);return True

def cache_geographic_inputs(work,source):
    """Keep downloaded immutable inputs for later jobs in the bundled engine only."""
    if Path(source).resolve()!=(ROOT/'pipeline').resolve():return
    original=Path(work)/'assets/geography';destination=Path(source)/'assets/geography'
    files=[original/name for name in ['NE2_HR_LC_SR_W.zip','rivers.geojson','land.geojson','lakes.geojson','terrain-attribution.md']]
    for folder in ['naturalearth','terrain']:
        if (original/folder).exists():files.extend((original/folder).rglob('*'))
    for file in files:
        if not file.is_file() or file.name.endswith('.part'):continue
        target=destination/file.relative_to(original)
        if target.exists():continue
        target.parent.mkdir(parents=True,exist_ok=True)
        try:os.link(file,target)
        except FileExistsError:pass
        except OSError:
            temp=target.with_name(target.name+'.part')
            shutil.copy2(file,temp);os.replace(temp,target)

def stop_process(pid):
    with LOCK:proc=PROCESSES.get(pid)
    if proc and proc.poll() is None:
        if os.name=="nt":subprocess.run(["taskkill","/PID",str(proc.pid),"/T","/F"],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        else:proc.terminate()
def run(pid,python,work,args,cancel,log,max_hours=10):
    cancel()
    command=[str(python),"-X","utf8",*args]
    env={**os.environ,"PYTHONUNBUFFERED":"1","PYTHONUTF8":"1"}
    flags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
    proc=subprocess.Popen(command,cwd=work,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
         encoding="utf-8",errors="replace",env=env,creationflags=flags)
    with LOCK:PROCESSES[pid]=proc
    tail=[];start=time.monotonic()
    # A reader thread allows cancellation even while the subprocess prints nothing.
    import queue
    q=queue.Queue()
    def reader():
        for line in proc.stdout:q.put(line.rstrip())
        q.put(None)
    threading.Thread(target=reader,daemon=True).start()
    try:
        while True:
            cancel()
            if time.monotonic()-start>max_hours*3600:raise RuntimeError("Tempo massimo della fase superato.")
            try:line=q.get(timeout=.4)
            except queue.Empty:continue
            if line is None:break
            if line:tail.append(line);tail=tail[-15:];log(line)
        code=proc.wait()
        if code:raise RuntimeError("Fase della pipeline non completata. "+"\n".join(tail)[-1800:])
    except BaseException:
        stop_process(pid)
        try:proc.wait(timeout=15)
        except subprocess.TimeoutExpired:pass
        raise
    finally:
        with LOCK:PROCESSES.pop(pid,None)
    cancel()
