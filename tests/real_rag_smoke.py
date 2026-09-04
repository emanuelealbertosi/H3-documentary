"""Optional real-model smoke test. The ordinary suite uses deterministic fake vectors."""
from pathlib import Path
import gc
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import documents, store
from app.models import ProjectRequest


def main():
    model_cache = (store.DATA / documents.MODEL_CACHE).resolve()
    temporary = ROOT / ".real-rag-smoke"
    if temporary.exists():
        shutil.rmtree(temporary)
    try:
        (temporary / "jobs").mkdir(parents=True)
        store.DATA = temporary
        store.JOBS = temporary / "jobs"
        documents.MODEL_CACHE = str(model_cache)
        documents._MODEL = None
        store.init()
        austerlitz = ("Austerlitz, Pratzen e Napoleone sono il tema di questa fonte storica. " * 45).encode()
        renaissance = ("Firenze, arte e Rinascimento sono il tema di un documento differente. " * 45).encode()
        first = documents.upload(austerlitz, "austerlitz.txt")
        second = documents.upload(renaissance, "rinascimento.txt")
        project = store.create(ProjectRequest(topic="Battaglia di Austerlitz", start=False,
                                              document_ids=[second["id"], first["id"]]))
        documents.freeze(project["id"], project["document_ids"])
        sources = documents.retrieve(project["id"], "attacco di Napoleone sulle alture di Pratzen", limit=1)
        assert first["status"] == second["status"] == "indexed"
        assert len(sources) == 1 and sources[0]["title"] == "austerlitz"
        print(f"RAG reale pronto: {len(sources)} fonti recuperate; prima fonte: {sources[0]['title']}.")
    finally:
        documents._MODEL = None
        gc.collect()
        if temporary.exists():
            for attempt in range(8):
                try:
                    shutil.rmtree(temporary)
                    break
                except PermissionError:
                    if attempt == 7:
                        raise
                    gc.collect()
                    time.sleep(.25)


if __name__ == "__main__":
    main()
