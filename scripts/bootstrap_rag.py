"""Download and verify the small multilingual CPU retrieval model."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import documents


if __name__ == "__main__":
    print("Preparo l’indice semantico multilingue locale…", flush=True)
    documents.ensure_model(download=True)
    updated = 0
    for record in documents.catalog():
        if record.get("status") == "text_ready":
            documents.index_document(record["id"])
            updated += 1
    print(f"Modello RAG locale pronto. Documenti reindicizzati: {updated}.", flush=True)
