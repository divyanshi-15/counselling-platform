"""make kb: load kb/*.md into kb_documents/kb_chunks with local embeddings."""
from __future__ import annotations

import sys

from backend.app.config import settings
from backend.app.db import SessionLocal
from backend.app.rag import load_kb


def main() -> None:
    kb_dir = sys.argv[1] if len(sys.argv) > 1 else settings.kb_dir
    with SessionLocal() as db:
        print(load_kb(db, kb_dir))


if __name__ == "__main__":
    main()
