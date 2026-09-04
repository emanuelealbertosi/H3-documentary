from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import ValidationError
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

@router.delete('/api/media/{mid}')
def delete(mid:str):
    try:return media.remove(mid)
    except KeyError:raise HTTPException(404,'Immagine non disponibile.')

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
    visual['editable']=p['status'] in ('review','completed')
    visual['project_status']=p['status']
    for slot in visual['slots']:
        target={'kind':slot['kind'],'label':slot['label'],'visual_slot_id':slot['id'],'visual_state':slot['state'],'scene_ids':slot['scene_ids'],'source_type':slot.get('source_type',''),
                'optional':bool(slot.get('optional')),'required':bool(slot.get('required')),'enabled':bool(slot.get('enabled')),'pending_option':bool(slot.get('pending_option')),
                'visual_has_preview':bool(slot.get('has_preview'))}
        target['visual_editable']=p['status'] in ('review','completed')
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

@router.put('/api/projects/{pid}/visual-slots/{slot_id}')
def visual_slot_edit(pid:str,slot_id:str,value:dict):
    if 'enabled' not in value and 'layout' not in value:raise HTTPException(422,'Indica la modifica visuale richiesta.')
    from .visual_slots import set_enabled,set_layout,status
    try:
        if 'enabled' in value:
            if type(value['enabled']) is not bool:raise HTTPException(422,'Indica se mostrare questo riferimento nel film.')
            set_enabled(pid,slot_id,value['enabled'])
        if 'layout' in value:set_layout(pid,slot_id,value['layout'])
        return status(pid)
    except KeyError:raise HTTPException(404,'Riferimento visuale non disponibile.')
    except ValidationError:raise HTTPException(422,'Inquadratura visuale non valida.')
    except ValueError as error:raise HTTPException(409,str(error))

@router.post('/api/projects/{pid}/visual-refresh',status_code=202)
def visual_refresh(pid:str):
    from .runner import enqueue_visual_refresh
    project=enqueue_visual_refresh(pid)
    return {'mode':'new_version','project':project}

@router.post('/api/projects/{pid}/visual-approve',status_code=202)
def visual_approve(pid:str):
    from .runner import approve_visual_review
    return {'mode':'resume','project':approve_visual_review(pid)}
