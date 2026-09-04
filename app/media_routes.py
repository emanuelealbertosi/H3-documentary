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
    from .visual_slots import status
    visual=status(pid);targets=media.targets(pid)
    for slot in visual['slots']:
        target={'kind':slot['kind'],'label':slot['label'],'visual_slot_id':slot['id'],'visual_state':slot['state'],'scene_ids':slot['scene_ids']}
        current=next((x for x in targets if x['kind']==target['kind'] and media.normalized(x['label'])==media.normalized(target['label'])),None)
        if current:current.update({k:v for k,v in target.items() if k not in ('kind','label')})
        else:targets.append(target)
    return {'enabled':bool(p.get('use_media')),'frozen':path.exists() or p['status']!='draft','editable':p['status']=='draft' and not path.exists(),'targets':targets,'visual':visual}

@router.put('/api/projects/{pid}/media')
def project_media_edit(pid:str, value:dict):
    p=store.project(pid)
    if p['status']!='draft' or (store.JOBS/pid/'checkpoints/media-selection.json').exists():
        raise HTTPException(409,'Le immagini di questa produzione sono già fissate. Le modifiche alla libreria valgono per le nuove produzioni.')
    if type(value.get('enabled')) is not bool:raise HTTPException(422,'Indica se usare le immagini.')
    store.update(pid,use_media=value['enabled'])
    return project_media(pid)

@router.get('/api/projects/{pid}/visual-slots')
def visual_slots(pid:str):
    from .visual_slots import status
    return status(pid)

@router.get('/api/projects/{pid}/visual-slots/{slot_id}/image')
def visual_slot_image(pid:str,slot_id:str):
    from .visual_slots import slot_file
    try:path=slot_file(pid,slot_id)
    except KeyError:raise HTTPException(404,'Immagine non disponibile.')
    return FileResponse(path)

@router.post('/api/projects/{pid}/visual-refresh',status_code=202)
def visual_refresh(pid:str):
    from .runner import enqueue_visual_refresh
    project=enqueue_visual_refresh(pid)
    return {'mode':'new_version','project':project}
