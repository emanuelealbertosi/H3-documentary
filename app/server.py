from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
import os,time,json,zipfile
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from .paths import ROOT,DATA,JOBS
from . import store
from .models import Settings,ProjectRequest,VoiceChoice
from .llm import LLM,ModelError
from .library import library
from .media_routes import router as media_router
from .document_routes import router as document_router
from .tts_routes import router as tts_router

@asynccontextmanager
async def lifespan(app):
    store.init()
    yield
    from .runner import shutdown
    shutdown()
app=FastAPI(title="H3-documentary",docs_url=None,redoc_url=None,lifespan=lifespan)
app.include_router(media_router)
app.include_router(document_router)
app.include_router(tts_router)

@app.middleware("http")
async def local_boundary(request:Request,call_next):
    host=request.url.hostname
    if host not in ("127.0.0.1","localhost","::1","testserver"):
        return JSONResponse({"detail":"L’app è disponibile soltanto sul computer locale."},status_code=403)
    if request.method in ("POST","PUT","PATCH","DELETE"):
        origin=request.headers.get("origin")
        if request.headers.get("x-documentariai")!="studio" or (origin and urlsplit(origin).netloc!=request.headers.get("host")):
            return JSONResponse({"detail":"Richiesta non autorizzata da questa interfaccia."},status_code=403)
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Content-Security-Policy"]="default-src 'self'; img-src 'self' data:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"]="no-store"
    elif request.url.path.startswith("/static/") or request.url.path in ("/","/admin","/library","/media","/documents") or request.url.path.startswith("/projects/"):
        # This is a local application that is upgraded in place. Revalidate its
        # shell and assets so the browser never keeps an older Admin interface.
        response.headers["Cache-Control"]="no-cache"
    return response

@app.exception_handler(KeyError)
async def missing(request,error):return JSONResponse({"detail":"Progetto o file non trovato."},status_code=404)
@app.exception_handler(ModelError)
async def model_error(request,error):return JSONResponse({"detail":str(error)},status_code=502)
@app.exception_handler(ValueError)
async def value_error(request,error):return JSONResponse({"detail":str(error)},status_code=400)

@app.get("/api/health")
def health():
    cfg=store.settings();root=Path(cfg["pipeline_path"])
    from .pipeline import verify_pipeline
    try:verify_pipeline(root);ready=True
    except ValueError:ready=False
    return {"ok":True,"service":"h3-documentary","instance":str(ROOT),"configured":bool(cfg["model"]),"pipeline_ready":ready,"local":True,"version":(ROOT/'VERSION').read_text().strip()}

@app.get("/api/settings")
def get_settings():return store.settings()
@app.put("/api/settings")
def put_settings(value:Settings):
    from .runner import active
    if active():raise HTTPException(409,"Attendi o interrompi la produzione prima di cambiare le impostazioni.")
    if value.tts_engine=='api':
        from .tts_api import profile
        if not value.tts_profile_id:raise ValueError('Seleziona un server TTS salvato.')
        try:profile(value.tts_profile_id)
        except KeyError:raise ValueError('Il server TTS selezionato non esiste più.')
    return store.save_settings(value)

def connection(value):
    new=value.model_dump()
    if not new.get("api_key"):
        new["api_key"]=store.connection_key(new) if not new.get("clear_api_key") else ""
    return new
@app.post("/api/provider/models")
def models(value:Settings):return {"models":LLM(connection(value)).models()}
@app.post("/api/provider/test")
def test_connection(value:Settings):
    c=connection(value)
    if not c["model"]:raise ValueError("Seleziona o scrivi il nome del modello.")
    start=time.monotonic()
    schema={'title':'ConnectionTest','type':'object','properties':{'ok':{'type':'boolean'},'lingua':{'type':'string'}},'required':['ok','lingua'],'additionalProperties':False}
    result=LLM(c).structured('Rispondi con un solo oggetto JSON.','Restituisci esattamente {"ok":true,"lingua":"italiano"}.',schema)
    if not isinstance(result,dict) or result.get("ok") is not True:raise ModelError("Il server risponde, ma il test di risposta strutturata non è riuscito.")
    return {"ok":True,"seconds":round(time.monotonic()-start,2),"message":"Connessione e risposta JSON verificate."}

@app.get('/api/tts')
def tts_status():
    from . import tts
    return tts.status(store.settings())

@app.post('/api/tts/references',status_code=201)
async def tts_reference(request:Request,filename:str='Voce.wav',reference_text:str=''):
    from . import tts
    raw=bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw)>tts.MAX_REFERENCE_BYTES:raise HTTPException(413,'Usa un WAV PCM fino a 20 MB.')
    return tts.upload_reference(bytes(raw),filename,reference_text)

@app.get("/api/projects")
def list_projects():return store.projects()
@app.post("/api/projects",status_code=201)
def new_project(value:ProjectRequest):
    from .documents import validate_selection
    validate_selection(value.document_ids,value.use_documents)
    p=store.create(value)
    if value.start and store.settings()["model"]:
        from .runner import enqueue
        enqueue(p["id"])
    return store.project(p["id"])
@app.get("/api/projects/{pid}")
def get_project(pid:str):return store.project(pid)
@app.get("/api/projects/{pid}/events")
def get_events(pid:str,after:int=0):
    store.project(pid);return store.events(pid,after)
@app.post("/api/projects/{pid}/start")
def start_project(pid:str):
    from .runner import enqueue
    enqueue(pid);return store.project(pid)
@app.post("/api/projects/{pid}/cancel")
def cancel_project(pid:str):
    from .runner import cancel
    cancel(pid);return store.project(pid)
@app.post('/api/projects/{pid}/regenerate')
def regenerate_project(pid:str):
    from .runner import active
    current=store.project(pid)
    if active(pid) or current['status'] in ('running','queued','cancelling'):
        raise HTTPException(409,'Interrompi la produzione prima di rigenerarla.')
    if current['status']=='completed':
        from .documents import validate_selection
        validate_selection(current.get('document_ids',[]),bool(current.get('use_documents')))
        project=store.clone_completed(pid);mode='new_version'
    else:
        project=store.restart_project(pid);mode='restart'
    if store.settings()['model']:
        from .runner import enqueue
        enqueue(project['id'])
    return {'mode':mode,'project':store.project(project['id'])}
@app.delete('/api/projects/{pid}')
def delete_project(pid:str):
    from .runner import active
    project=store.project(pid)
    if active(pid) or project['status'] in ('running','queued','cancelling'):
        raise HTTPException(409,'Interrompi la produzione prima di eliminare il progetto.')
    store.delete_project(pid)
    return {'deleted':True,'id':pid}
@app.put('/api/projects/{pid}/voice')
def project_voice(pid:str,value:VoiceChoice):
    from .tts import change_project_voice
    return change_project_voice(pid,value)
@app.patch("/api/projects/{pid}")
async def revise_project(pid:str,request:Request):
    p=store.project(pid)
    if p["status"] in ("running","queued","cancelling","completed"):raise HTTPException(409,"Questo progetto non è modificabile mentre è in corso o completato.")
    data=await request.json()
    validated=ProjectRequest(topic=p["topic"],minutes=p["minutes"],notes=data.get("notes",p["notes"]),source_urls=data.get("source_urls",p["source_urls"]),
                             use_documents=p.get("use_documents",False),document_ids=p.get("document_ids",[]))
    store.update(pid,notes=validated.notes,source_urls=validated.source_urls)
    # New editorial input invalidates derived checkpoints, preserving all previous versions.
    checkpoint=JOBS/pid/"checkpoints"
    revision=str(time.time_ns())
    if checkpoint.exists():checkpoint.rename(JOBS/pid/("checkpoints-previous-"+revision))
    workspace=JOBS/pid/"workspace"
    if workspace.exists():
        assert workspace.resolve().is_relative_to(JOBS.resolve())
        workspace.rename(JOBS/pid/("workspace-previous-"+revision))
    store.update(pid,status="draft",progress=0,stage="Pronto per ripartire",error="",result={})
    return store.project(pid)

@app.get("/api/library")
def get_library():
    return [{k:v for k,v in x.items() if k not in ("movie","thumbnail")} | {"has_thumbnail":bool(x["thumbnail"])} for x in library()]
@app.get("/api/library/{slug}/{kind}")
def library_file(slug:str,kind:str):
    item=next((x for x in library() if x["id"]==slug),None)
    if not item or kind not in ("movie","thumbnail") or not item[kind]:raise HTTPException(404,"File non disponibile.")
    return FileResponse(item[kind],media_type="video/mp4" if kind=="movie" else "image/jpeg")

PUBLIC_EXT={".mp4",".jpg",".png",".srt",".md",".json",".txt",".pdf",".docx"}
def output_files(pid):
    store.project(pid);work=JOBS/pid/"workspace";items=[]
    roots=[work/"output",work/"battles",work/"documentaries",work/"assets/user",work/"assets/documents",JOBS/pid/"checkpoints"]
    for root in roots:
        if not root.exists():continue
        for f in sorted(root.rglob("*")):
            if not f.is_file() or f.suffix not in (PUBLIC_EXT|({'.webp'} if root==work/'assets/user' else set())):continue
            if not f.resolve().is_relative_to((JOBS/pid).resolve()):continue
            if root.name=="checkpoints" and f.name not in ("sources.json","outline.json","review.json","research.json"):continue
            rel=f.relative_to(JOBS/pid).as_posix()
            items.append({"path":rel,"name":f.name,"bytes":f.stat().st_size})
    return items
@app.get("/api/projects/{pid}/files")
def files(pid:str):return output_files(pid)
@app.get("/api/projects/{pid}/file")
def project_file(pid:str,path:str,download:bool=False):
    valid={x["path"] for x in output_files(pid)}
    if path not in valid:raise HTTPException(404,"File non disponibile.")
    target=(JOBS/pid/path).resolve()
    if not target.is_relative_to((JOBS/pid).resolve()):raise HTTPException(403)
    return FileResponse(target,filename=target.name if download else None)
@app.get("/api/projects/{pid}/previews")
def previews(pid:str):
    store.project(pid);work=JOBS/pid/"workspace";out=[]
    for f in sorted((work/"build").glob("*/previews/*.jpg")):
        out.append({"name":f.name,"path":f.relative_to(JOBS/pid).as_posix()})
    return out
@app.get("/api/projects/{pid}/preview")
def preview(pid:str,path:str):
    valid={x["path"] for x in previews(pid)}
    if path not in valid:raise HTTPException(404)
    return FileResponse(JOBS/pid/path,media_type="image/jpeg")
@app.get("/api/projects/{pid}/export")
def export(pid:str):
    p=store.project(pid);target=JOBS/pid/"project-export.zip"
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.json",json.dumps({k:v for k,v in p.items() if k!="result"},ensure_ascii=False,indent=2))
        for item in output_files(pid):
            if item["path"].endswith(".mp4"):continue
            z.write(JOBS/pid/item["path"],item["path"])
    return FileResponse(target,filename="documentario-"+pid+".zip")

app.mount("/static",StaticFiles(directory=ROOT/"static"),name="static")
@app.get("/")
@app.get("/admin")
@app.get("/projects/{pid}")
@app.get("/library")
@app.get("/media")
@app.get("/projects/{pid}/media")
@app.get("/documents")
@app.get("/projects/{pid}/documents")
def shell(pid:str=""):return FileResponse(ROOT/"static/index.html",media_type="text/html")
