import json, sqlite3, secrets, threading, datetime, ctypes, base64, os, hashlib
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
        c.execute("UPDATE projects SET status='interrupted',error='L’app si è chiusa durante la produzione. Puoi riprendere dai passaggi salvati.' WHERE status IN ('running','queued','cancelling')")
        if "use_media" not in {r[1] for r in c.execute("PRAGMA table_info(projects)")}:
            c.execute("ALTER TABLE projects ADD COLUMN use_media INTEGER DEFAULT 0")
def project(pid):
    with connect() as c: row=c.execute("SELECT * FROM projects WHERE id=?",(pid,)).fetchone()
    if not row: raise KeyError(pid)
    obj=dict(row);obj["source_urls"]=json.loads(obj["source_urls"]);obj["result"]=json.loads(obj["result"]);return obj
def projects():
    with connect() as c: ids=[r["id"] for r in c.execute("SELECT id FROM projects ORDER BY created DESC")]
    return [project(i) for i in ids]
def create(req):
    pid=secrets.token_hex(8);ts=now()
    with connect() as c:
        c.execute("INSERT INTO projects(id,topic,minutes,notes,source_urls,status,stage,created,updated) VALUES (?,?,?,?,?,'draft','Pronto per iniziare',?,?)",
          (pid,req.topic,req.minutes,req.notes,json.dumps(req.source_urls),ts,ts))
        c.execute("UPDATE projects SET documentary_type=? WHERE id=?",(req.documentary_type,pid))
        c.execute("UPDATE projects SET use_media=? WHERE id=?",(req.use_media,pid))
    (JOBS/pid).mkdir();return project(pid)
def update(pid,**fields):
    allowed={"status","stage","progress","error","result","notes","source_urls","use_media"}
    if not fields.keys()<=allowed: raise ValueError("Campi non consentiti")
    fields["updated"]=now()
    fields={k:json.dumps(v,ensure_ascii=False) if k in ("result","source_urls") else v for k,v in fields.items()}
    with connect() as c:c.execute("UPDATE projects SET "+",".join(k+"=?" for k in fields)+" WHERE id=?",(*fields.values(),pid))
def event(pid,message,level="info"):
    message=str(message)[-3000:]
    with connect() as c:c.execute("INSERT INTO events(project_id,at,level,message) VALUES (?,?,?,?)",(pid,now(),level,message))
def events(pid,after=0):
    with connect() as c:return [dict(r) for r in c.execute("SELECT * FROM events WHERE project_id=? AND id>? ORDER BY id LIMIT 500",(pid,after))]

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

SERVER_FIELDS=('provider','base_url','model','timeout','max_tokens','temperature','token_parameter','json_mode','vision','request_limit')

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
