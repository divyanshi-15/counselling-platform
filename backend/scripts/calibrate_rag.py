"""Print top-1 cosine similarity (real e5 model, loaded KB) for in-domain vs out-of-domain queries."""
from __future__ import annotations

from sqlalchemy import text

from backend.app.db import SessionLocal
from backend.app.embeddings import get_embedder
from backend.app.rag import _or_tsquery

IN_DOMAIN = [
    "anxiety at night", "can't stop worrying", "low motivation", "breathing for panic",
    "trouble falling asleep", "feeling overwhelmed and stressed", "grounding when I feel panicky",
    "how to challenge negative thoughts", "I feel lonely and want support", "managing intense emotions",
    "mind racing at night", "no energy to do anything", "can't switch off before bed",
    "Client reports lying awake for hours with worries about exams. Sleep has been around five hours. "
    "She tries to scroll on her phone in bed.",
    "Client describes withdrawing from friends and staying in most days. Mood is low and he says nothing feels worth doing. "
    "Homework on activity scheduling was not attempted.",
    "Client had a panic episode on the bus this week, heart racing and tight chest. Wants something to use in the moment.",
    "Client feels intense anger after arguments and acts rashly. Struggles to name what she is feeling.",
    "Client faces several work and money problems at once and feels stuck. Does not know where to begin.",
    "Client has little contact with family and says there is no one to talk to. Feels like a burden. Scores unchanged over two weeks.",
    "Client repeatedly thinks 'I will fail everything' before presentations and spirals. Wants to examine these thoughts.",
]
OUT_OF_DOMAIN = [
    "best pizza recipe", "football score", "how to change a car tyre", "weather in Paris tomorrow",
    "stock market news", "cheap flights to Goa", "python list comprehension", "latest smartphone reviews",
    "how to bake sourdough bread", "cricket world cup schedule",
    "sleep tracker app reviews", "gym workout plan", "how to file taxes", "best mattress to buy online",
    "how to learn guitar chords", "meditation app subscription price", "yoga mat sale near me",
    "Summarise the quarterly sales report and list the top three regions by revenue. Include a chart of monthly growth.",
    "Write a cover letter for a software engineer job at a bank. Mention five years of Java experience.",
    "Plan a three-day trip to Jaipur with hotels and restaurants. Budget is around twenty thousand rupees.",
]


def top1(db, query: str) -> tuple[float, str, bool]:
    vec = "[" + ",".join(f"{x:.7f}" for x in get_embedder().embed_query(query)) + "]"
    row = db.execute(text(
        "SELECT 1 - (c.embedding <=> CAST(:v AS vector)) AS sim, d.title, "
        "(:q <> '' AND c.tsv @@ to_tsquery('english', :q)) AS lex FROM kb_chunks c "
        "JOIN kb_documents d ON d.id = c.document_id ORDER BY c.embedding <=> CAST(:v AS vector) LIMIT 1"), {"v": vec, "q": _or_tsquery(query)}).one()
    return float(row.sim), row.title, bool(row.lex)


def report_threshold(inn: list[float], out: list[float]) -> None:
    """Threshold = midpoint of the widest gap in the sorted pooled scores that best separates the sets."""
    pooled = sorted(inn + out)
    best = None
    for lo, hi in zip(pooled, pooled[1:]):
        t = (lo + hi) / 2
        bal = (sum(x >= t for x in inn) / len(inn) + sum(x < t for x in out) / len(out)) / 2
        key = (round(bal, 6), hi - lo)
        if best is None or key > best[0]:
            best = (key, t, hi - lo)
    _, t, gap = best
    margin = min(inn) - max(out)
    print(f"\nmargin (min in-domain - max out-of-domain) = {margin:+.3f}"
          + (" (separable)" if margin > 0 else " (overlap)"))
    print(f"suggested threshold = {t:.3f} (gap around it {gap:.3f}); "
          f"in-domain pass {sum(x >= t for x in inn)}/{len(inn)}, out-of-domain pass {sum(x >= t for x in out)}/{len(out)}")


def main() -> None:
    scores: dict[str, list[float]] = {}
    with SessionLocal() as db:
        for label, queries in (("in-domain", IN_DOMAIN), ("out-of-domain", OUT_OF_DOMAIN)):
            print(f"\n{label}\n| query | top-1 sim | full-text hit | top-1 entry |\n|---|---|---|---|")
            sims = []
            for q in queries:
                sim, title, lex = top1(db, q)
                sims.append(sim)
                print(f"| {q} | {sim:.3f} | {"yes" if lex else "no"} | {title} |")
            print(f"{label}: min={min(sims):.3f} max={max(sims):.3f}")
            scores[label] = sims
        report_threshold(scores["in-domain"], scores["out-of-domain"])


if __name__ == "__main__":
    main()
