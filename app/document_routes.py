from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from . import documents, store

router = APIRouter()


@router.get("/api/documents")
def listing():
    return documents.catalog()


@router.post("/api/documents/file", status_code=201)
async def upload_file(request: Request, filename: str = "Documento"):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > documents.MAX_BYTES:
            raise HTTPException(413, "Usa un documento fino a 50 MB.")
    return await run_in_threadpool(documents.upload, bytes(raw), filename)


@router.post("/api/documents/text", status_code=201)
async def paste_text(value: documents.PastedDocument):
    return await run_in_threadpool(documents.paste, value)


@router.put("/api/documents/{did}")
def edit(did: str, value: documents.DocumentEdit):
    return documents.save(did, value)


@router.get("/api/documents/{did}/file")
def original(did: str):
    record = documents.get(did)
    return FileResponse(documents.folder(did) / record["original"], filename=record["filename"])


@router.get("/api/projects/{pid}/documents")
def project_documents(pid: str):
    project = store.project(pid)
    checkpoint = store.JOBS / pid / "checkpoints" / "document-selection.json"
    if checkpoint.is_file():
        selected = [x["id"] for x in store.read_json(checkpoint)["documents"]]
    else:
        selected = project.get("document_ids", [])
    return {"enabled": bool(project.get("use_documents")), "selected_ids": selected,
            "frozen": checkpoint.exists() or project["status"] != "draft",
            "editable": project["status"] == "draft" and not checkpoint.exists(),
            "documents": documents.catalog()}


@router.put("/api/projects/{pid}/documents")
def project_documents_edit(pid: str, value: dict):
    project = store.project(pid)
    checkpoint = store.JOBS / pid / "checkpoints" / "document-selection.json"
    if project["status"] != "draft" or checkpoint.exists():
        raise HTTPException(409, "Le fonti di questa produzione sono già fissate. Le modifiche valgono per le nuove produzioni.")
    if type(value.get("enabled")) is not bool or not isinstance(value.get("document_ids"), list):
        raise HTTPException(422, "Selezione dei documenti non valida.")
    ids = list(dict.fromkeys(value["document_ids"]))
    if len(ids) > 24 or any(not isinstance(x, str) for x in ids):
        raise HTTPException(422, "Puoi scegliere fino a 24 documenti.")
    documents.validate_selection(ids, value["enabled"])
    store.update(pid, use_documents=value["enabled"], document_ids=ids)
    return project_documents(pid)
