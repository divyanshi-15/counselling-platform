"""Held-out precision/recall of the risk classifier with the real embedder. SYNTHETIC, demonstration only."""
import json

from backend.app.embeddings import get_embedder
from backend.app.safety import evaluate_classifier

print(json.dumps(evaluate_classifier(get_embedder()), indent=2, ensure_ascii=False))
