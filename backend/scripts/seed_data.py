"""Seed content: practices, therapists, clients. All people and organisations are fictional."""
from __future__ import annotations

LOGINS = [  # (email, password, role, name)
    ("admin@example.com", "admin123", "admin", "Ananya Iyer"),
    ("owner@example.com", "owner123", "practice_owner", "Sunita Rao"),
    ("owner2@example.com", "owner123", "practice_owner", "Prakash Gowda"),
    ("owner3@example.com", "owner123", "practice_owner", "Imran Qureshi"),
    ("therapist@example.com", "therapist123", "therapist", "Dr Meera Krishnan"),
    ("therapist2@example.com", "therapist123", "therapist", "Arjun Nair"),
    ("therapist4@example.com", "therapist123", "therapist", "Dr Kavya Shetty"),
    ("therapist3@example.com", "therapist123", "therapist", "Rohan Hegde"),
    ("therapist5@example.com", "therapist123", "therapist", "Sneha Gowda"),
    ("therapist6@example.com", "therapist123", "therapist", "Dr Anand Murthy"),
    ("therapist7@example.com", "therapist123", "therapist", "Dr Farah Siddiqui"),
    ("therapist8@example.com", "therapist123", "therapist", "Pranav Reddy"),
    ("therapist9@example.com", "therapist123", "therapist", "Lakshmi Varma"),
    ("client@example.com", "client123", "client", "Ananya Rao"),
    ("client2@example.com", "client123", "client", "Rohan Mehta"),
    ("client3@example.com", "client123", "client", "Ishaan Verma"),
    ("client4@example.com", "client123", "client", "Nandini Rao"),
    ("client5@example.com", "client123", "client", "Aditi Menon"),
    ("client6@example.com", "client123", "client", "Karthik Subramanian"),
    ("client7@example.com", "client123", "client", "Pooja Hegde"),
    ("client8@example.com", "client123", "client", "Mohammed Faizan"),
    ("client9@example.com", "client123", "client", "Sanjana Reddy"),
    ("client10@example.com", "client123", "client", "Rahul Bhat"),
    ("client11@example.com", "client123", "client", "Divya Kulkarni"),
    ("client12@example.com", "client123", "client", "Tarun Joshi"),
]

PRACTICES = [  # slug, name, owner email, legacy slug (renamed in place on existing databases), page
    {"slug": "calm-minds-bengaluru", "legacy": "demo-calm-minds", "name": "Calm Minds Counselling",
     "owner": "owner@example.com",
     "page": {"tagline": "Calm, practical support for sleep, stress and exam pressure in Bengaluru.",
              "about": "Calm Minds Counselling is a small team of clinical and counselling psychologists offering warm, "
                       "structured, skill-building sessions informed by CBT.",
              "location": "Bengaluru", "languages": ["en", "hi", "kn"], "specialties": ["sleep", "stress", "anxiety"],
              "approaches": ["CBT", "CBT-I", "ACT"], "fee_range": "INR 1500-2200"}},
    {"slug": "harbour-counselling-mysuru", "legacy": "demo-harbour-counselling", "name": "Harbour Counselling",
     "owner": "owner2@example.com",
     "page": {"tagline": "Unhurried, family-aware counselling in Mysuru, in English and Kannada.",
              "about": "Harbour Counselling supports students, young professionals and families with practical, "
                       "step-by-step skill-building.",
              "location": "Mysuru", "languages": ["en", "kn"], "specialties": ["family", "low mood", "life transitions"],
              "approaches": ["CBT", "behavioural activation"], "fee_range": "INR 1000-1600"}},
    {"slug": "lakeview-wellness-hyderabad", "legacy": None, "name": "Lakeview Wellness Clinic",
     "owner": "owner3@example.com",
     "page": {"tagline": "Evidence-informed counselling for work stress and relationships in Hyderabad.",
              "about": "Lakeview Wellness Clinic brings together counsellors who help clients build everyday coping "
                       "skills, online or in person.",
              "location": "Hyderabad", "languages": ["en", "hi"], "specialties": ["work stress", "relationships", "anxiety"],
              "approaches": ["CBT", "ACT", "mindfulness-based"], "fee_range": "INR 1600-2600"}},
]
PRACTICE_SLUGS = [p["slug"] for p in PRACTICES] + [p["legacy"] for p in PRACTICES if p["legacy"]]
COMMON_PAGE = {
    "services": [{"title": "Initial consultation", "description": "A first conversation to understand your needs."},
                 {"title": "Supportive sessions", "description": "Structured sessions informed by CBT."}],
    "faq": [{"question": "Is this online?", "answer": "Sessions are held online; some clinics also offer in-person visits."},
            {"question": "Is this a replacement for therapy?",
             "answer": "Between-session exercises are skill-building support, not a replacement for therapy."}],
    "what_to_expect": ["Clear goals and a collaborative plan", "Simple next steps between sessions"],
    "session_type": "online",
}

THERAPISTS = [  # email, practice slug, credentials, years, rating, reviews, fee, languages, approaches, specialisations, bio
    ("therapist@example.com", "calm-minds-bengaluru", "M.Phil Clinical Psychology, RCI-registered", 11, 4.9, 128, 1800,
     ["en", "hi"], ["CBT", "CBT-I"], ["insomnia", "stress", "burnout"],
     "Meera helps people whose busy minds keep them up at night. Her sessions are structured, practical and paced "
     "to what you can manage that week. She works with working professionals and students."),
    ("therapist2@example.com", "calm-minds-bengaluru", "M.Sc Counselling Psychology", 6, 4.7, 74, 1500,
     ["en", "kn"], ["CBT"], ["exam stress", "self-criticism", "work pressure"],
     "Arjun works with students and early-career professionals on stress and self-critical thinking. "
     "He offers sessions in English and Kannada."),
    ("therapist4@example.com", "calm-minds-bengaluru", "Ph.D Clinical Psychology", 14, 4.8, 156, 2200,
     ["en", "hi", "kn"], ["CBT", "ACT"], ["anxiety", "panic", "trauma-informed care"],
     "Kavya has worked with anxiety and panic for over a decade. She blends CBT skills with acceptance-based "
     "practices and keeps a steady, unhurried pace."),
    ("therapist3@example.com", "harbour-counselling-mysuru", "M.A Counselling Psychology", 5, 4.6, 52, 1100,
     ["en", "kn"], ["CBT", "behavioural activation"], ["low mood", "motivation", "life transitions"],
     "Rohan supports clients who feel flat or stuck, using small scheduled steps to rebuild routine and interest. "
     "He sees clients in English and Kannada."),
    ("therapist5@example.com", "harbour-counselling-mysuru", "M.Phil Clinical Psychology, RCI-registered", 9, 4.8, 97, 1600,
     ["en", "kn"], ["CBT", "family-focused"], ["perinatal wellbeing", "family stress", "parenting"],
     "Sneha works with new parents and families under strain. Her approach is warm and practical, with clear "
     "between-session steps."),
    ("therapist6@example.com", "harbour-counselling-mysuru", "Ph.D Counselling Psychology", 16, 4.9, 143, 1400,
     ["en", "kn"], ["CBT", "problem-solving therapy"], ["adjustment", "grief", "caregiver stress"],
     "Anand has spent sixteen years supporting people through change and loss. He is known for calm, "
     "plain-spoken sessions."),
    ("therapist7@example.com", "lakeview-wellness-hyderabad", "M.Phil Clinical Psychology, RCI-registered", 12, 4.8, 119, 2600,
     ["en", "hi"], ["CBT", "ACT"], ["anxiety", "relationships", "work stress"],
     "Farah helps clients untangle worry and relationship strain. Sessions are collaborative and focus on skills "
     "you can use the same day."),
    ("therapist8@example.com", "lakeview-wellness-hyderabad", "M.Sc Clinical Psychology", 4, 4.5, 38, 1600,
     ["en", "hi"], ["CBT", "mindfulness-based"], ["work stress", "sleep", "young adults"],
     "Pranav works with young adults on stress, sleep and the pressures of early careers, using short, "
     "manageable exercises."),
    ("therapist9@example.com", "lakeview-wellness-hyderabad", "M.A Psychology, PG Diploma in CBT", 8, 4.7, 83, 2000,
     ["en", "hi"], ["CBT"], ["perfectionism", "anxiety", "career transitions"],
     "Lakshmi supports perfectionistic and anxious clients, helping them test unhelpful rules and build "
     "kinder, workable routines."),
]

INTAKE_FIELDS = [{"id": "main_concern", "label": "What brings you here?", "required": True},
                 {"id": "sleep_hours", "label": "Typical hours of sleep"},
                 {"id": "goals", "label": "What would you like to change?"}]


def _intake(concern: str, sleep: str, goals: str) -> dict:
    return {"main_concern": concern, "sleep_hours": sleep, "goals": goals}


def _plateau(first: int, latest: int, slope: float, measure: str) -> list[dict]:
    return [{"measure": measure, "readings": 3, "first": first, "latest": latest, "slope_per_week": slope}]


# days_ago values are relative to "now". Notes/assessments are chronological (oldest first).
CASES = {
    "client@example.com": {  # plateau, low homework, one goal untouched; racing thoughts at night
        "therapist": "therapist@example.com", "approach": "CBT-I", "future_hours": 3,
        "phq9": [(180, 21), (150, 19), (120, 17), (90, 15), (60, 14), (35, 14), (20, 14), (13, 15), (6, 14), (0, 15)],
        "gad7": [(180, 17), (150, 16), (120, 15), (90, 14), (60, 13), (35, 13), (20, 13), (13, 13), (6, 14), (0, 13)],
        "goals": [{"id": "g1", "text": "Reduce racing thoughts at bedtime"},
                  {"id": "g2", "text": "Reconnect with weekend football friends"}],
        "formulation": "Evening worry and a busy mind keep the client alert at bedtime, which shortens sleep and lowers "
                       "daytime energy. Working hypothesis, to be reviewed each session.",
        "intake": _intake("My thoughts race at night and I am exhausted during the day.", "About 5 hours a night",
                          "Fall asleep faster and feel less tired"),
        "notes": [
            (150, "First sessions focused on understanding the sleep pattern and what the client wants from therapy. "
                  "Sleep is short and broken. Agreed on a regular wake time and a short wind-down routine."),
            (105, "Wake time is steadier and the client falls asleep a little earlier on some nights. Football with "
                  "friends has dropped off since a busy period at work. Introduced the idea of a worry list."),
            (60, "Mood and sleep improved a little over the past month. Client still lies awake with plans for the next "
                 "day. Practised a slow breathing routine and reviewed the sleep diary."),
            (21, "Client described racing thoughts at night that begin as soon as the lights are off. The mind replays "
                 "the day's conversations and plans tomorrow's tasks. It takes about two hours to fall asleep on most "
                 "nights. Sleeps around five hours and feels foggy in the afternoon. Agreed to keep a simple sleep diary."),
            (14, "Sleep diary shows bedtime between eleven and one. Client lies awake with thoughts going round and round "
                 "about work deadlines and checks the phone in bed. We discussed a worry time earlier in the evening and "
                 "writing worries down before bed. Homework: one thought record this week."),
            (7, "Only one thought record completed. Client says evenings are busy and thoughts still race at night. "
                "Talked about a wind-down hour without screens. Client feels discouraged about slow progress. Plan to try "
                "a ten minute worry postponement slot at seven in the evening."),
            (2, "Racing thoughts continue most nights; last night's thoughts were about an upcoming presentation. Client "
                "skipped the worry slot on four evenings. Energy is low and mood is flat. Agreed to simplify homework to "
                "one short exercise and to look at what makes the evening routine hard to keep."),
        ],
        "assignments": [(140, "thought_record", True), (110, "worry_postponement", True), (75, "thought_record", True),
                        (50, "worry_postponement", False), (12, "thought_record", False),
                        (9, "worry_postponement", True), (6, "thought_record", False),
                        (3, "worry_postponement", False)],
    },
    "client2@example.com": {  # improving; homework done
        "therapist": "therapist@example.com", "approach": "CBT", "future_hours": 5,
        "phq9": [(175, 22), (145, 21), (115, 19), (85, 18), (50, 17), (20, 16), (13, 13), (6, 10), (0, 8)],
        "gad7": [(175, 17), (145, 16), (115, 14), (85, 13), (50, 13), (20, 12), (13, 10), (6, 8), (0, 7)],
        "goals": [{"id": "g1", "text": "Use breathing exercise before exams"},
                  {"id": "g2", "text": "Plan one social activity each week"}],
        "formulation": "Exam pressure raises tension; avoiding social plans reduces support. Working hypothesis.",
        "intake": _intake("Exam stress and feeling tense before tests.", "About 7 hours a night",
                          "Feel calmer before exams"),
        "notes": [(140, "Client feels tense before tests and has stopped meeting classmates. Agreed on goals for the term."),
                  (95, "Practised slow breathing. Client tried it before a class test and noticed less tension."),
                  (50, "Study routine is steadier. Client plans to spend more time with classmates."),
                  (14, "Client feels tense before exams. Practised slow breathing together and planned a social activity."),
                  (7, "Breathing exercise helped before the mock exams. Client met a classmate for a social activity."),
                  (1, "Exams went better than expected. Client keeps using breathing and planned another social activity.")],
        "assignments": [(130, "thought_record", True), (90, "worry_postponement", True), (45, "thought_record", True),
                        (10, "thought_record", True), (4, "worry_postponement", True)],
    },
    "client3@example.com": {
        "therapist": "therapist2@example.com", "approach": "CBT", "future_hours": 8,
        "phq9": [(175, 15), (145, 14), (115, 13), (85, 12), (50, 11), (20, 11), (13, 9), (6, 7), (0, 5)],
        "gad7": [(175, 12), (145, 11), (115, 10), (85, 9), (50, 8), (20, 8), (13, 6), (6, 5), (0, 4)],
        "goals": [{"id": "g1", "text": "Notice and name unhelpful thoughts"},
                  {"id": "g2", "text": "Spend time on valued activities"}],
        "formulation": "Work pressure and self-critical thoughts reduce time for valued activities. Working hypothesis.",
        "intake": _intake("Work pressure and a harsh inner critic.", "About 6 hours a night", "Feel more settled at work"),
        "notes": [(110, "Client described long hours and a harsh inner critic after a difficult review at work."),
                  (60, "Started a simple record of critical thoughts. Client noticed they spike on Sunday evenings."),
                  (14, "Client is learning to notice unhelpful thoughts about work performance."),
                  (7, "Named several unhelpful thoughts this week. Client booked time for a valued activity, painting."),
                  (1, "Client noticed fewer unhelpful thoughts and spent two evenings on valued activities.")],
        "assignments": [(100, "thought_record", True), (55, "thought_record", True), (30, "worry_postponement", True)],
    },
    "client4@example.com": {
        "therapist": "therapist3@example.com", "approach": "CBT", "future_hours": 10,
        "phq9": [(20, 9), (13, 8), (6, 6), (0, 4)], "gad7": [(20, 7), (13, 6), (6, 4), (0, 3)],
        "goals": [{"id": "g1", "text": "Schedule one pleasant activity daily"},
                  {"id": "g2", "text": "Walk outside three times weekly"}],
        "formulation": "Fewer enjoyable plans over recent weeks; small scheduled steps help rebuild a daily rhythm. Working hypothesis.",
        "intake": _intake("Low energy and less interest in usual hobbies.", "About 8 hours a night",
                          "Return to my usual hobbies and weekly plans"),
        "notes": [(14, "Client scheduled one pleasant activity most days and walked outside twice."),
                  (7, "Pleasant activity each day is going well. Walk outside three times this week."),
                  (1, "Energy is better. Client keeps a pleasant activity plan and walks outside regularly.")],
        "assignments": [],
    },
    "client5@example.com": {  # six-month history with a dip; two open homework items
        "therapist": "therapist4@example.com", "approach": "ACT", "future_hours": 52,
        "phq9": [(170, 17), (140, 15), (110, 16), (80, 12), (50, 11), (20, 9), (0, 8)],
        "gad7": [(170, 16), (140, 15), (110, 15), (80, 12), (50, 10), (20, 9), (0, 7)],
        "goals": [{"id": "g1", "text": "Practise a grounding routine when worry builds"},
                  {"id": "g2", "text": "Say yes to one social plan each week"}],
        "formulation": "Worry about performance builds through the day and is eased by avoidance, which narrows social "
                       "plans. Working hypothesis.",
        "intake": _intake("Constant worry at work and trouble switching off.", "About 6 hours a night",
                          "Feel calmer through the day"),
        "notes": [(160, "Client described constant worry about work and tight shoulders by evening. Agreed on a grounding routine."),
                  (115, "Worry rose again after a team change. Reviewed what helps and what makes it worse."),
                  (70, "Grounding routine is used most days. Client declined two social plans this month."),
                  (30, "Client said yes to a friend's plan and enjoyed it. Worry about work is lower on most days."),
                  (10, "Steady progress. Client keeps the grounding routine and plans one social activity each week.")],
        "assignments": [(150, "worry_postponement", True), (100, "thought_record", True), (60, "worry_postponement", True),
                        (25, "thought_record", True), (8, "worry_postponement", False), (3, "thought_record", False)],
        "alerts": [("homework", 2, "under 50% of recent exercises completed", {"assigned": 3, "completed": 1, "rate": 0.33})],
    },
    "client6@example.com": {
        "therapist": "therapist4@example.com", "approach": "CBT", "future_hours": 76,
        "phq9": [(12, 14), (0, 14)], "gad7": [(12, 12), (0, 12)],
        "goals": [{"id": "g1", "text": "Slow down racing worry before presentations"}],
        "formulation": "Fear of judgement before presentations drives avoidance and late-night preparation. Working hypothesis.",
        "intake": _intake("Worry before presentations and poor sleep.", "About 6 hours a night", "Speak up in meetings"),
        "notes": [(12, "First session. Client described worry before team presentations and poor sleep the night before.")],
        "assignments": [],
        "alerts": [("plateau", 1, "no meaningful PHQ-9/GAD-7 improvement over 14 days", _plateau(14, 14, 0.0, "PHQ9"))],
        "pending": [("release_exercise", {"exercise": "thought_record"})],
    },
    "client7@example.com": {
        "therapist": "therapist5@example.com", "approach": "CBT", "future_hours": 100,
        "phq9": [(10, 10), (0, 9)], "gad7": [(10, 9), (0, 8)],
        "goals": [{"id": "g1", "text": "Protect one hour of rest each day"}],
        "formulation": "Broken sleep and little time to rest since the baby arrived. Working hypothesis.",
        "intake": _intake("Exhausted and overwhelmed since the baby arrived.", "About 4 hours a night, broken",
                          "Find time to rest"),
        "notes": [(10, "First session. Client is tired and worried about coping with night feeds. Agreed to plan short rest periods.")],
        "assignments": [],
        "alerts": [("risk", 9, None, {"source": "checkin", "source_id": None, "match": "unable to cope",
                                      "text": "Said they feel overwhelmed and unable to cope this week."}, True)],
        "pending": [("release_exercise", {"exercise": "worry_postponement"})],
    },
    "client8@example.com": {
        "therapist": "therapist7@example.com", "approach": "ACT", "future_hours": 130,
        "phq9": [(11, 16), (0, 17)], "gad7": [(11, 13), (0, 14)],
        "goals": [{"id": "g1", "text": "Keep a steady weekly routine"}],
        "formulation": "Pressure at work and strain at home have reduced routine and rest. Working hypothesis.",
        "intake": _intake("Work pressure and arguments at home.", "About 5 hours a night", "Feel less overwhelmed"),
        "notes": [(11, "First session. Client described a heavy workload and tension at home. Agreed on one small routine change.")],
        "assignments": [],
        "alerts": [("risk", 1, None, {"source": "checkin", "source_id": None, "match": "overwhelmed",
                                      "text": "Wrote that everything feels too much right now."}, False)],
    },
    "client9@example.com": {
        "therapist": "therapist8@example.com", "approach": "CBT", "future_hours": 160,
        "phq9": [(2, 8)], "gad7": [(2, 10)],
        "goals": [{"id": "g1", "text": "Wind down before bed"}],
        "formulation": "Late-night work and screen use delay sleep. Working hypothesis.",
        "intake": _intake("Trouble falling asleep during a busy project.", "About 5 hours a night", "Sleep earlier"),
        "notes": [], "assignments": [],
        "pending": [("release_exercise", {"exercise": "worry_postponement"})],
    },
    "client10@example.com": {
        "therapist": "therapist6@example.com", "approach": "CBT", "future_hours": 190,
        "phq9": [(3, 11)], "gad7": [(3, 8)],
        "goals": [{"id": "g1", "text": "Take one short break for myself each day"}],
        "formulation": "Caring for a parent leaves little time for rest. Working hypothesis.",
        "intake": _intake("Caring for my father and feeling worn out.", "About 6 hours a night", "Set aside a short break each day"),
        "notes": [], "assignments": [],
    },
    "client11@example.com": {
        "therapist": "therapist9@example.com", "approach": "CBT", "future_hours": 240,
        "phq9": [(1, 7)], "gad7": [(1, 12)],
        "goals": [{"id": "g1", "text": "Finish tasks without rechecking"}],
        "formulation": "High standards and rechecking slow work and raise worry. Working hypothesis.",
        "intake": _intake("I recheck my work many times and worry about mistakes.", "About 7 hours a night",
                          "Feel comfortable finishing tasks"),
        "notes": [], "assignments": [],
    },
    "client12@example.com": None,  # signed up, has not booked yet
}
