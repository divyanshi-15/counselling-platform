"""make kb: load kb/*.md into kb_documents/kb_chunks with local embeddings."""
from __future__ import annotations

import sys

from backend.app.config import settings
from backend.app.db import SessionLocal
from backend.app.rag import load_kb


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--force"]
    kb_dir = args[0] if args else settings.kb_dir
    with SessionLocal() as db:
        print(load_kb(db, kb_dir, force="--force" in sys.argv))


if __name__ == "__main__":
    main()
