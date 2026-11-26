"""fill Hindi exercise templates; remove Kannada support

Revision ID: 20261117_013
Revises: 20261117_012
Create Date: 2026-11-17 12:00:00.000000
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "20261117_013"
down_revision = "20261117_012"
branch_labels = None
depends_on = None

HI = {
    "thought_record": ("विचार रिकॉर्ड", {
        "intro": "एक तेज़ भावना को धीमा करके उसके पीछे के विचार को देखिए। हर खाने में कुछ शब्द लिखिए।",
        "fields": [
            {"id": "situation", "label": "क्या हो रहा था?", "type": "text", "required": True},
            {"id": "thought", "label": "आपके मन में कौन सा विचार आया?", "type": "text", "required": True},
            {"id": "feeling_before", "label": "भावना कितनी तेज़ थी? (0 = बिल्कुल नहीं, 10 = बहुत तेज़)", "type": "scale", "required": True},
            {"id": "evidence_for", "label": "इस विचार के पक्ष में क्या है?", "type": "text", "required": False},
            {"id": "evidence_against", "label": "कौन सी बातें इस विचार से मेल नहीं खातीं?", "type": "text", "required": False},
            {"id": "balanced_thought", "label": "इसे देखने का एक संतुलित तरीका", "type": "text", "required": False},
            {"id": "feeling_after", "label": "अब भावना कितनी तेज़ है? (0-10)", "type": "scale", "required": False},
        ]}),
    "worry_postponement": ("चिंता को बाद के लिए टालना (मन की बातें लिखना)", {
        "intro": "अभी सारी चिंताएँ लिख डालिए, फिर आज के लिए चिंता का एक तय समय चुनिए जब आप उन पर वापस आएँगे।",
        "fields": [
            {"id": "worries", "label": "मन की बातें लिखिए: जो चिंताएँ आपके मन में हैं", "type": "text", "required": True},
            {"id": "can_act_now", "label": "क्या कोई एक छोटा कदम है जो आप अभी उठा सकते हैं?", "type": "text", "required": False},
            {"id": "worry_time", "label": "आपका चिंता का समय कब होगा? (जैसे शाम 6:30 बजे, 15 मिनट)", "type": "text", "required": True},
            {"id": "feeling_after", "label": "अब चिंताएँ कितनी भारी लग रही हैं? (0 = हल्की, 10 = बहुत भारी)", "type": "scale", "required": False},
        ]}),
}


def upgrade() -> None:
    bind = op.get_bind()
    exercises = sa.table("exercises", sa.column("slug", sa.String), sa.column("title_hi", sa.String),
                         sa.column("template_hi", sa.JSON))
    for slug, (title, template) in HI.items():
        bind.execute(exercises.update().where(exercises.c.slug == slug).values(title_hi=title, template_hi=template))

    op.drop_column("exercises", "template_kn")
    op.drop_column("exercises", "title_kn")

    # Existing rows: Kannada is no longer a supported language.
    bind.execute(sa.text("UPDATE users SET language = 'en' WHERE language = 'kn'"))
    rows = bind.execute(sa.text("SELECT id, languages FROM therapist_profiles")).fetchall()
    for pid, langs in rows:
        langs = json.loads(langs) if isinstance(langs, str) else (langs or [])
        if any(str(x).lower() == "kn" for x in langs):
            new = [x for x in langs if str(x).lower() != "kn"] or ["en"]
            bind.execute(sa.text("UPDATE therapist_profiles SET languages = CAST(:v AS JSON) WHERE id = :i"),
                         {"v": json.dumps(new), "i": pid})
    pages = bind.execute(sa.text("SELECT id, page_json FROM practices WHERE page_json IS NOT NULL")).fetchall()
    for prid, raw in pages:
        try:
            page = json.loads(raw) if isinstance(raw, str) else raw
        except ValueError:
            continue
        if isinstance(page, dict) and any(str(x).lower() == "kn" for x in page.get("languages", [])):
            page["languages"] = [x for x in page["languages"] if str(x).lower() != "kn"] or ["en"]
            bind.execute(sa.text("UPDATE practices SET page_json = :v WHERE id = :i"),
                         {"v": json.dumps(page, ensure_ascii=False), "i": prid})


def downgrade() -> None:
    op.add_column("exercises", sa.Column("title_kn", sa.String(length=255), nullable=True))
    op.add_column("exercises", sa.Column("template_kn", sa.JSON(), nullable=True))
    op.get_bind().execute(sa.text("UPDATE exercises SET title_hi = NULL, template_hi = NULL"))
