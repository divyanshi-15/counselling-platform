"""Report-only: misses on tests/risk_independent.csv (one phrase per row, first column; every row is expected
to be a risk phrase) and layer-2 behaviour on the benign hard negatives. Never fails."""
import csv
from pathlib import Path

from backend.app.embeddings import get_embedder
from backend.app.risk_data import HARD_NEGATIVES_15
from backend.app.safety import _get_classifier, _normalise, risk_check, risk_scan, RISK_THRESHOLD

CSV = Path(__file__).resolve().parents[2] / "tests" / "risk_independent.csv"


def main() -> None:
    if CSV.exists():
        with CSV.open(newline="", encoding="utf-8") as f:
            rows = [r[0].strip() for r in csv.reader(f) if r and r[0].strip()]
        if rows and rows[0].lower() in {"text", "phrase"}:
            rows = rows[1:]
        misses = [t for t in rows if not risk_scan(t)["flagged"]]
        l1_misses = [t for t in rows if not risk_check(t)["flagged"]]
        print(f"independent set: {len(rows)} rows, {len(misses)} missed by layer 1+2, {len(l1_misses)} missed by layer 1 alone")
        for t in misses:
            print(f"  MISS: {t}")
    else:
        print(f"{CSV} not found; skipping independent set")
    emb = get_embedder()
    clf = _get_classifier(emb)
    l1 = [t for t in HARD_NEGATIVES_15 if risk_check(t)["flagged"]]
    scores = {t: float(clf.predict_proba([emb.embed_query(_normalise(t))])[0][1]) for t in HARD_NEGATIVES_15}
    fired = {t: s for t, s in scores.items() if s >= RISK_THRESHOLD}
    print(f"hard negatives: {len(HARD_NEGATIVES_15)}; layer 1 fired on {len(l1)}; layer 2 fired on {len(fired)} (threshold {RISK_THRESHOLD})")
    for t, s in sorted(scores.items(), key=lambda kv: -kv[1]):
        print(f"  {s:.2f} {'FIRES' if s >= RISK_THRESHOLD else 'ok   '} {t}")


main()
