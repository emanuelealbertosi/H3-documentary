from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from . import media, store

router=APIRouter()

@router.get('/api/media')
def listing(): return media.catalog()

@router.post('/api/media',status_code=201)
async def upload(request:Request, filename:str='Immagine'):
    raw=bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw)>media.MAX_BYTES:raise HTTPException(413,'Usa un’immagine fino a 20 MB.')
    return await run_in_threadpool(media.upload,bytes(raw),filename)

@router.put('/api/media/{mid}')
def edit(mid:str,value:media.MediaEdit):return media.save(mid,value)

@router.get('/api/media/{mid}/{kind}')
def image(mid:str,kind:str):
    media.get(mid)
    if kind not in ('image','thumb'):raise HTTPException(404)
    return FileResponse(media.folder(mid)/('image.png' if kind=='image' else 'thumb.jpg'))

@router.get('/api/projects/{pid}/media')
def project_media(pid:str):
    p=store.project(pid);path=store.JOBS/pid/'checkpoints/media-selection.json'
    return {'enabled':bool(p.get('use_media')),'frozen':path.exists() or p['status']!='draft','editable':p['status']=='draft' and not path.exists(),'targets':media.targets(pid)}

@router.put('/api/projects/{pid}/media')
def project_media_edit(pid:str, value:dict):
    p=store.project(pid)
    if p['status']!='draft' or (store.JOBS/pid/'checkpoints/media-selection.json').exists():
        raise HTTPException(409,'Le immagini di questa produzione sono già fissate. Le modifiche alla libreria valgono per le nuove produzioni.')
    if type(value.get('enabled')) is not bool:raise HTTPException(422,'Indica se usare le immagini.')
    store.update(pid,use_media=value['enabled'])
    return project_media(pid)
