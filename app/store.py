import json, sqlite3, secrets, threading, datetime, ctypes, base64, os, hashlib, shutil, time
from pathlib import Path
from .paths import DATA, JOBS, DEFAULT_PIPELINE
from .models import Settings

LOCK=threading.RLock()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8");tmp.replace(path)
def read_json(path): return json.loads(Path(path).read_text(encoding="utf-8"))

def connect():
    c=sqlite3.connect(DATA/"studio.db",timeout=30);c.row_factory=sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL");return c
def init():
    with connect() as c:
        c.executescript("""CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY, topic TEXT, minutes INTEGER, notes TEXT, source_urls TEXT,
        status TEXT, stage TEXT, progress REAL DEFAULT 0, created TEXT, updated TEXT,
        error TEXT DEFAULT '', result TEXT DEFAULT '{}');
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT, at TEXT, level TEXT, message TEXT);""")
        if "documentary_type" not in {r[1] for r in c.execute("PRAGMA table_info(projects)")}:
            c.execute("ALTER TABLE projects ADD COLUMN documentary_type TEXT DEFAULT 'battle'")
        if "use_media" not in {r[1] for r in c.execute("PRAGMA table_info(projects)")}:
            c.execute("ALTER TABLE projects ADD COLUMN use_media INTEGER DEFAULT 0")
        if "tts_engine" not in {r[1] for r in c.execute("PRAGMA table_info(projects)")}:
            c.execute("ALTER TABLE projects ADD COLUMN tts_engine TEXT DEFAULT 'kokoro'")
        if "tts_reference_id" not in {r[1] for r in c.execute("PRAGMA table_info(projects)")}:
            c.execute("ALTER TABLE projects ADD COLUMN tts_reference_id TEXT DEFAULT ''")
        if "tts_profile_id" not in {r[1] for r in c.execute("PRAGMA table_info(projects)")}:
            c.execute("ALTER TABLE projects ADD COLUMN tts_profile_id TEXT DEFAULT ''")
        if "tts_config" not in {r[1] for r in c.execute("PRAGMA table_info(projects)")}:
            c.execute("ALTER TABLE projects ADD COLUMN tts_config TEXT DEFAULT '{}'")
        if "use_documents" not in {r[1] for r in c.execute("PRAGMA table_info(projects)")}:
            c.execute("ALTER TABLE projects ADD COLUMN use_documents INTEGER DEFAULT 0")
        if "document_ids" not in {r[1] for r in c.execute("PRAGMA table_info(projects)")}:
            c.execute("ALTER TABLE projects ADD COLUMN document_ids TEXT DEFAULT '[]'")
        columns={r[1] for r in c.execute("PRAGMA table_info(projects)")}
        if "family_id" not in columns:c.execute("ALTER TABLE projects ADD COLUMN family_id TEXT DEFAULT ''")
        if "version" not in columns:c.execute("ALTER TABLE projects ADD COLUMN version INTEGER DEFAULT 1")
        if "parent_id" not in columns:c.execute("ALTER TABLE projects ADD COLUMN parent_id TEXT DEFAULT ''")
        if "processing_started" not in columns:c.execute("ALTER TABLE projects ADD COLUMN processing_started TEXT DEFAULT ''")
        if "processing_seconds" not in columns:c.execute("ALTER TABLE projects ADD COLUMN processing_seconds REAL DEFAULT 0")
        c.execute("UPDATE projects SET family_id=id WHERE family_id IS NULL OR family_id=''")
        c.execute("UPDATE projects SET version=1 WHERE version IS NULL OR version<1")
        # Releases before 1.7.1 did not retain production timing. Recover a useful
        # total from the project diary so existing completed films gain the same UI.
        c.execute("""UPDATE projects SET processing_started=(
          SELECT MIN(at) FROM events WHERE project_id=projects.id
        ) WHERE (processing_started IS NULL OR processing_started='')
          AND status NOT IN ('draft') AND EXISTS(SELECT 1 FROM events WHERE project_id=projects.id)""")
        c.execute("""UPDATE projects SET processing_seconds=MAX(0,
          (julianday(COALESCE((SELECT MAX(at) FROM events WHERE project_id=projects.id),updated))
           -julianday(processing_started))*86400),processing_started=''
          WHERE status IN ('completed','failed','cancelled','interrupted','review')
            AND processing_started IS NOT NULL AND processing_started!=''
            AND COALESCE(processing_seconds,0)=0""")
        # If the app closed during a live production, retain the elapsed segment
        # before changing its state to interrupted.
        c.execute("""UPDATE projects SET processing_seconds=COALESCE(processing_seconds,0)+MAX(0,
          (julianday(?) - julianday(processing_started))*86400),processing_started=''
          WHERE status IN ('running','queued','cancelling')
            AND processing_started IS NOT NULL AND processing_started!=''""",(now(),))
        c.execute("UPDATE projects SET status='interrupted',error='L’app si è chiusa durante la produzione. Puoi riprendere dai passaggi salvati.' WHERE status IN ('running','queued','cancelling')")
    trash=DATA/'project-trash'
    if trash.is_dir():
        trash_root=trash.resolve()
        for item in trash.iterdir():
            if item.is_dir() and not item.is_symlink() and item.resolve().parent==trash_root:
                shutil.rmtree(item,ignore_errors=True)
def project(pid):
    with connect() as c: row=c.execute("SELECT * FROM projects WHERE id=?",(pid,)).fetchone()
    if not row: raise KeyError(pid)
    obj=dict(row);obj["source_urls"]=json.loads(obj["source_urls"]);obj["result"]=json.loads(obj["result"])
    obj["document_ids"]=json.loads(obj.get("document_ids") or "[]")
    obj["tts_config"]=json.loads(obj.get("tts_config") or "{}")
    return obj
def projects():
    with connect() as c: ids=[r["id"] for r in c.execute("SELECT id FROM projects ORDER BY created DESC")]
    return [project(i) for i in ids]
def create(req,*,family_id='',version=1,parent_id=''):
    pid=secrets.token_hex(8);ts=now()
    cfg=settings();engine=cfg['tts_engine'] if req.tts_engine=='default' else req.tts_engine
    profile=req.tts_profile_id or (cfg.get('tts_profile_id','') if req.tts_engine=='default' and engine=='api' else '')
    tts_config={}
    if engine=='api':
        from .tts_api import snapshot
        if not profile:raise ValueError('Seleziona un server TTS salvato.')
        tts_config=snapshot(profile)
    reference=req.tts_reference_id or (cfg.get('tts_reference_id','') if req.tts_engine=='default' and engine in ('chatterbox','api') else '')
    with connect() as c:
        c.execute("INSERT INTO projects(id,topic,minutes,notes,source_urls,status,stage,created,updated) VALUES (?,?,?,?,?,'draft','Pronto per iniziare',?,?)",
          (pid,req.topic,req.minutes,req.notes,json.dumps(req.source_urls),ts,ts))
        c.execute("UPDATE projects SET documentary_type=? WHERE id=?",(req.documentary_type,pid))
        c.execute("UPDATE projects SET use_media=? WHERE id=?",(req.use_media,pid))
        c.execute("UPDATE projects SET use_documents=?,document_ids=? WHERE id=?",(req.use_documents,json.dumps(req.document_ids),pid))
        c.execute("UPDATE projects SET tts_engine=?,tts_reference_id=?,tts_profile_id=?,tts_config=? WHERE id=?",(engine,reference,profile,json.dumps(tts_config,ensure_ascii=False),pid))
        c.execute("UPDATE projects SET family_id=?,version=?,parent_id=? WHERE id=?",(family_id or pid,max(1,int(version)),parent_id,pid))
    (JOBS/pid).mkdir();return project(pid)
def update(pid,**fields):
    allowed={"status","stage","progress","error","result","notes","source_urls","use_media","use_documents","document_ids","tts_engine","tts_reference_id","tts_profile_id","tts_config","processing_started","processing_seconds"}
    if not fields.keys()<=allowed: raise ValueError("Campi non consentiti")
    fields["updated"]=now()
    fields={k:json.dumps(v,ensure_ascii=False) if k in ("result","source_urls","document_ids","tts_config") else v for k,v in fields.items()}
    with connect() as c:c.execute("UPDATE projects SET "+",".join(k+"=?" for k in fields)+" WHERE id=?",(*fields.values(),pid))

def begin_processing(pid,at=None):
    """Start one active production segment without losing earlier resume time."""
    stamp=at or now()
    with connect() as c:
        row=c.execute("SELECT processing_started FROM projects WHERE id=?",(pid,)).fetchone()
        if not row:raise KeyError(pid)
        if not row["processing_started"]:
            c.execute("UPDATE projects SET processing_started=?,updated=? WHERE id=?",(stamp,stamp,pid))
    return stamp

def pause_processing(pid,at=None):
    """Close the active segment and return accumulated processing seconds."""
    stamp=at or now()
    with connect() as c:
        row=c.execute("SELECT processing_started,processing_seconds FROM projects WHERE id=?",(pid,)).fetchone()
        if not row:raise KeyError(pid)
        total=float(row["processing_seconds"] or 0)
        if row["processing_started"]:
            try:
                started=datetime.datetime.fromisoformat(row["processing_started"])
                finished=datetime.datetime.fromisoformat(stamp)
                total+=max(0.0,(finished-started).total_seconds())
            except (TypeError,ValueError):
                pass
        c.execute("UPDATE projects SET processing_started='',processing_seconds=?,updated=? WHERE id=?",(total,stamp,pid))
    return total
def event(pid,message,level="info"):
    message=str(message)[-3000:]
    with connect() as c:c.execute("INSERT INTO events(project_id,at,level,message) VALUES (?,?,?,?)",(pid,now(),level,message))
def events(pid,after=0):
    with connect() as c:return [dict(r) for r in c.execute("SELECT * FROM events WHERE project_id=? AND id>? ORDER BY id LIMIT 500",(pid,after))]

def clone_completed(pid):
    """Create a new version from user inputs while retaining the completed project."""
    from .models import ProjectRequest
    with LOCK:
        old=project(pid)
        if old['status']!='completed':raise ValueError('Solo un progetto completato crea una nuova versione.')
        family=old.get('family_id') or old['id']
        with connect() as c:
            version=int(c.execute('SELECT COALESCE(MAX(version),0)+1 FROM projects WHERE family_id=?',(family,)).fetchone()[0])
        request=ProjectRequest(topic=old['topic'],minutes=old['minutes'],notes=old['notes'],source_urls=old['source_urls'],start=False,
            use_media=bool(old.get('use_media')),use_documents=bool(old.get('use_documents')),document_ids=old.get('document_ids',[]),
            documentary_type=old.get('documentary_type') or 'auto',tts_engine='default')
        new=create(request,family_id=family,version=version,parent_id=old['id'])
        event(pid,f'Creata la versione V{version}: {new["id"]}.')
        event(new['id'],f'Nuova versione V{version} del progetto {old["id"]}.')
        return new

def restart_project(pid):
    """Archive the failed attempt and reset the same project to an empty run."""
    with LOCK:
        old=project(pid)
        if old['status']=='completed':raise ValueError('Un progetto completato deve creare una nuova versione.')
        if old['status'] in ('running','queued','cancelling'):raise ValueError('Interrompi la produzione prima di rigenerarla.')
        folder=(JOBS/pid).resolve();root=JOBS.resolve()
        if folder.parent!=root or folder.name!=pid:raise ValueError('Cartella del progetto non valida.')
        stamp=str(time.time_ns());attempt=folder/'attempts'/stamp;attempt.mkdir(parents=True,exist_ok=False)
        with connect() as c:old_events=[dict(row) for row in c.execute('SELECT * FROM events WHERE project_id=? ORDER BY id',(pid,))]
        if old_events:write_json(attempt/'events.json',old_events)
        moved=[]
        try:
            for name in ('checkpoints','workspace','research','model-audit','last-error.txt','project-export.zip'):
                source=folder/name
                if source.exists():
                    target=attempt/name;source.rename(target);moved.append((source,target))
            with connect() as c:
                c.execute('DELETE FROM events WHERE project_id=?',(pid,))
                c.execute("UPDATE projects SET status='draft',stage='Pronto per rigenerare',progress=0,error='',result='{}',processing_started='',processing_seconds=0,updated=? WHERE id=?",(now(),pid))
        except Exception:
            for source,target in reversed(moved):
                if target.exists() and not source.exists():target.rename(source)
            raise
        event(pid,'Rigenerazione da zero richiesta. Il tentativo precedente è stato archiviato.')
        return project(pid)

def delete_project(pid):
    """Remove one inactive project and its private files from the local studio."""
    with LOCK:
        old=project(pid)
        if old['status'] in ('running','queued','cancelling'):raise ValueError('Interrompi la produzione prima di eliminare il progetto.')
        folder=(JOBS/pid).resolve();root=JOBS.resolve()
        if folder.parent!=root or folder.name!=pid:raise ValueError('Cartella del progetto non valida.')
        trash_root=DATA/'project-trash';trash_root.mkdir(exist_ok=True)
        staged=trash_root/(pid+'-'+str(time.time_ns()))
        if folder.exists():folder.rename(staged)
        try:
            with connect() as c:
                c.execute('DELETE FROM events WHERE project_id=?',(pid,))
                c.execute('DELETE FROM projects WHERE id=?',(pid,))
        except Exception:
            if staged.exists() and not folder.exists():staged.rename(folder)
            raise
        if staged.exists():
            try:shutil.rmtree(staged)
            except OSError:pass
        return old

class Blob(ctypes.Structure):
    _fields_=[("size",ctypes.c_ulong),("data",ctypes.POINTER(ctypes.c_ubyte))]
def protect(text,decrypt=False):
    if os.name!="nt": raise ValueError("Il salvataggio cifrato delle chiavi richiede Windows; usa DOCUMENTARIAI_API_KEY su altri sistemi.")
    raw=base64.b64decode(text) if decrypt else text.encode()
    buf=ctypes.create_string_buffer(raw);src=Blob(len(raw),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)));dst=Blob()
    fn=ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    ok=fn(ctypes.byref(src),None,None,None,None,1,ctypes.byref(dst))
    if not ok: raise OSError("Impossibile proteggere la chiave con il profilo Windows.")
    try:
        result=ctypes.string_at(dst.data,dst.size)
        return result.decode() if decrypt else base64.b64encode(result).decode()
    finally:ctypes.windll.kernel32.LocalFree(dst.data)

SERVER_FIELDS=('provider','base_url','model','timeout','max_tokens','temperature','token_parameter','reasoning_mode','json_mode','vision','request_limit')

def profile_id(provider,base_url):
    """Stable opaque ID; neither credentials nor model prompts are part of it."""
    return hashlib.sha256((str(provider)+'\0'+str(base_url)).encode()).hexdigest()[:20]

def server_profiles(raw):
    """Read saved servers and migrate the previous single-server format in memory."""
    profiles={}
    rows=raw.get('server_profiles',{})
    if isinstance(rows,dict):
        for row in rows.values():
            if not isinstance(row,dict):continue
            try:cfg=Settings(**row).model_dump()
            except ValueError:continue
            pid=profile_id(cfg['provider'],cfg['base_url'])
            profiles[pid]={k:cfg[k] for k in SERVER_FIELDS}|{'encrypted_key':row.get('encrypted_key',''),'updated':row.get('updated','')}
    if raw:
        try:legacy=Settings(**raw).model_dump()
        except ValueError:legacy=None
        if legacy:
            pid=profile_id(legacy['provider'],legacy['base_url'])
            row=profiles.setdefault(pid,{k:legacy[k] for k in SERVER_FIELDS}|{'encrypted_key':'','updated':''})
            if not row.get('encrypted_key') and raw.get('encrypted_key'):row['encrypted_key']=raw['encrypted_key']
    return profiles

def connection_key(value):
    """Return only the key belonging to the requested provider and normalized URL."""
    data=value.model_dump() if hasattr(value,'model_dump') else value
    path=DATA/'settings.json';raw=read_json(path) if path.exists() else {}
    pid=profile_id(data['provider'],data['base_url']);profiles=server_profiles(raw)
    encrypted=profiles.get(pid,{}).get('encrypted_key','')
    if not encrypted and raw:
        current=Settings(**raw).model_dump()
        if pid==profile_id(current['provider'],current['base_url']):encrypted=raw.get('encrypted_key','')
    environment=os.environ.get('DOCUMENTARIAI_API_KEY','')
    if environment and raw:
        current=Settings(**raw).model_dump()
        if pid==profile_id(current['provider'],current['base_url']):return environment
    return protect(encrypted,True) if encrypted else ''

def settings(secret=False):
    path=DATA/"settings.json"
    raw=read_json(path) if path.exists() else {}
    obj=Settings(**raw).model_dump()
    obj["pipeline_path"]=obj["pipeline_path"] or DEFAULT_PIPELINE
    obj.pop("api_key",None);obj.pop("clear_api_key",None)
    profiles=server_profiles(raw);active=profile_id(obj['provider'],obj['base_url'])
    encrypted=profiles.get(active,{}).get('encrypted_key','') or raw.get('encrypted_key','')
    environment=os.environ.get("DOCUMENTARIAI_API_KEY","")
    obj["has_api_key"]=bool(encrypted or environment)
    rows=[]
    for pid,row in profiles.items():
        public={k:row[k] for k in SERVER_FIELDS};public.update(id=pid,has_api_key=bool(row.get('encrypted_key') or (environment if pid==active else '')),updated=row.get('updated',''))
        rows.append(public)
    rows.sort(key=lambda row:row.get('updated',''),reverse=True);rows.sort(key=lambda row:row['id']!=active)
    obj['active_profile']=active;obj['saved_servers']=rows
    if secret:obj["api_key"]=environment or (protect(encrypted,True) if encrypted else "")
    return obj
def save_settings(value):
    with LOCK:
        path=DATA/"settings.json";old=read_json(path) if path.exists() else {}
        profiles=server_profiles(old)
        data=value.model_dump();key=data.pop("api_key",None);clear=data.pop("clear_api_key",False)
        if data['pipeline_path'] and Path(data['pipeline_path']).resolve()==Path(DEFAULT_PIPELINE).resolve():
            data['pipeline_path']=''
        pid=profile_id(data['provider'],data['base_url']);previous=profiles.get(pid,{})
        encrypted="" if clear else (protect(key) if key else previous.get('encrypted_key',''))
        profiles[pid]={k:data[k] for k in SERVER_FIELDS}|{'encrypted_key':encrypted,'updated':now()}
        data['active_profile']=pid;data['server_profiles']=profiles
        # Retained for readers from releases before profiles were introduced.
        data["encrypted_key"]=encrypted
        write_json(path,data)
    return settings()
