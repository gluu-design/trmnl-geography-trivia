import os
import json
import random
import re
import unicodedata
import zoneinfo
from datetime import datetime, timedelta
from google import genai
from google.genai import types

# Setup Gemini API client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

HISTORY_FILE = "history.json"
DATA_FILE = "data.json"

FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash"
]

# A country can't come back until this many questions have passed (~2 months).
RECENT_COUNTRY_WINDOW = 60
# How many times we ask Gemini again if it returns a repeat.
MAX_ATTEMPTS = 5

# Random "angle" for each request, so Gemini doesn't fall back on the same famous facts.
REGIONS = [
    "West Africa", "East Africa", "Southern Africa", "North Africa",
    "Western Europe", "Eastern Europe", "Northern Europe", "Southern Europe",
    "the Middle East", "Central Asia", "South Asia", "Southeast Asia", "East Asia",
    "Central America", "the Caribbean", "South America", "North America",
    "Oceania", "the Pacific Islands",
]
TOPICS = [
    "rivers", "mountains", "islands", "lakes", "deserts", "volcanoes",
    "capital cities", "borders and enclaves", "population statistics",
    "climate records", "national parks", "famous landmarks", "caves",
    "waterfalls", "straits and canals", "glaciers", "reefs and marine life",
    "forests", "plateaus and valleys", "extreme points (highest, lowest, northernmost...)",
]

TRIVIA_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "question": types.Schema(type=types.Type.STRING),
        "answer": types.Schema(type=types.Type.STRING),
        "stat_category": types.Schema(type=types.Type.STRING),
        "fun_fact": types.Schema(type=types.Type.STRING),
        "country": types.Schema(type=types.Type.STRING, description="The primary country this trivia is about"),
    },
    required=["question", "answer", "stat_category", "fun_fact", "country"],
)

FALLBACK_TRIVIA = {
    "question": "Which country has the most natural lakes?",
    "answer": "Canada",
    "stat_category": "Landforms",
    "fun_fact": "Canada has over 60% of Earth's lakes.",
    "country": "Canada",
}


def load_history():
    default_structure = {
        "used_countries": [],
        "past_trivia": [],
        "todays_trivia": None,
        "last_run_date": ""
    }
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, dict):
                    for key in default_structure:
                        content.setdefault(key, default_structure[key])
                    return content
        except Exception:
            pass
    return default_structure


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def normalize(text):
    """'The Salar de Uyuni (Bolivia)' -> 'salar de uyuni' so near-identical answers match."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"\(.*?\)", " ", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"^\s*the\s+", "", text)
    return " ".join(text.split())


def ask_gemini(prompt):
    """Try each model in order. Returns a dict, or None if every model failed."""
    for model_name in FALLBACK_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=TRIVIA_SCHEMA,
                    temperature=1.0,
                ),
            )
            result = json.loads(response.text)
            if isinstance(result, list):
                result = result[0] if result else None
            if isinstance(result, dict):
                return result
        except Exception as e:
            print(f"Model {model_name} failed: {e}")
    return None


def check_trivia(trivia, banned_countries, past_answers):
    """Returns None if the trivia is OK, otherwise the reason it was rejected."""
    for key in ["question", "answer", "stat_category", "fun_fact", "country"]:
        if not str(trivia.get(key, "")).strip():
            return f"missing '{key}'"
    if normalize(trivia["country"]) in banned_countries:
        return f"country '{trivia['country']}' was used recently"
    if normalize(trivia["answer"]) in banned_countries:
        return f"answer '{trivia['answer']}' is a recently used country"
    if normalize(trivia["answer"]) in past_answers:
        return f"answer '{trivia['answer']}' was already used"
    return None


def fetch_gemini_trivia(history):
    past = history.get("past_trivia", [])

    # Countries from the most recent questions (by order of use, duplicates included).
    recent_countries = []
    for t in past[-RECENT_COUNTRY_WINDOW:]:
        c = str(t.get("country", "")).strip()
        if c and c not in recent_countries:
            recent_countries.append(c)
    banned_countries = {normalize(c) for c in recent_countries}

    # Every answer ever given is banned.
    past_answers = {normalize(t.get("answer", "")) for t in past if t.get("answer")}
    answers_for_prompt = []
    for t in reversed(past):
        a = str(t.get("answer", "")).strip()
        if a and a not in answers_for_prompt:
            answers_for_prompt.append(a)
    answers_for_prompt = answers_for_prompt[:150]

    rejected = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        region = random.choice(REGIONS)
        topic = random.choice(TOPICS)
        prompt = f"""
Generate one fascinating, factually accurate geography trivia question.
Rules:
1. The question must be about a country in {region}, on the topic of {topic}.
2. Do NOT use any of these countries: [{", ".join(recent_countries)}]
3. The answer must NOT be any of these (already used): [{", ".join(answers_for_prompt + rejected)}]
4. Avoid the most obvious "world record" facts; prefer surprising, lesser-known ones.
5. 'fun_fact' must be under 180 characters.
6. 'country' is the single country the question is about.
"""
        trivia = ask_gemini(prompt)
        if trivia is None:
            print("All Gemini models failed.")
            return None

        reason = check_trivia(trivia, banned_countries, past_answers)
        if reason is None:
            print(f"Attempt {attempt} accepted ({region} / {topic}): {trivia['answer']}")
            return trivia

        print(f"Attempt {attempt} rejected: {reason}")
        rejected.append(str(trivia.get("answer", "")).strip())

    print("Gemini kept repeating itself.")
    return None


TZ = zoneinfo.ZoneInfo("America/New_York")
# Keep the published schedule small: yesterday, today and tomorrow (New York dates)
# cover every time zone on Earth. Older schedule entries are pruned after this many days.
KEEP_DAYS = 7


def human_date(d):
    return d.strftime("%B %d, %Y")


def migrate_history(history):
    """Older history files only had 'todays_trivia' + 'last_run_date'. Move that into 'schedule'."""
    history.setdefault("schedule", {})
    if not history["schedule"] and history.get("todays_trivia") and history.get("last_run_date"):
        try:
            d = datetime.strptime(history["last_run_date"], "%B %d, %Y").date()
            entry = dict(history["todays_trivia"])
            entry["date"] = human_date(d)
            history["schedule"][d.isoformat()] = entry
            print(f"Migrated existing question to the schedule for {d.isoformat()}.")
        except ValueError:
            pass


def ensure_question(history, day):
    """Make sure the schedule has a question for `day`. Returns True if a new one was added."""
    key = day.isoformat()
    if key in history["schedule"]:
        return False
    print(f"No question yet for {key}. Asking Gemini...")
    trivia = fetch_gemini_trivia(history)
    if not trivia:
        print(f"Could not get a question for {key}; the next run will try again.")
        return False
    trivia["date"] = human_date(day)
    history["schedule"][key] = trivia
    history["past_trivia"].append(trivia)
    if trivia["country"] not in history["used_countries"]:
        history["used_countries"].append(trivia["country"])
    return True


def public_entry(key, t):
    return {
        "date": key,
        "question": t["question"],
        "answer": t["answer"],
        "stat_category": t["stat_category"],
        "fun_fact": t["fun_fact"],
    }


def generate_geo_loop_data():
    override = os.getenv("GEO_NOW")  # for testing only, e.g. 2026-10-31T10:00
    now = datetime.fromisoformat(override).replace(tzinfo=TZ) if override else datetime.now(TZ)
    today = now.date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    history = load_history()
    migrate_history(history)

    # Today's question first (normally already there), then tomorrow's, prepared a day ahead.
    changed = ensure_question(history, today)
    changed = ensure_question(history, tomorrow) or changed

    # Drop old schedule entries (past_trivia keeps the full record for anti-repeat).
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    history["schedule"] = {k: v for k, v in sorted(history["schedule"].items()) if k >= cutoff}

    # Keep the old fields up to date too.
    if today.isoformat() in history["schedule"]:
        history["todays_trivia"] = history["schedule"][today.isoformat()]
        history["last_run_date"] = human_date(today)

    if changed:
        save_history(history)

    # Days published to TRMNL. The screen picks the right one using each user's local time.
    days = [public_entry(k, history["schedule"][k])
            for k in (yesterday.isoformat(), today.isoformat(), tomorrow.isoformat())
            if k in history["schedule"]]

    # Legacy top-level fields (New York time), so older markup keeps working.
    current = next((d for d in reversed(days) if d["date"] <= today.isoformat()), None)
    if current is None:
        current = public_entry(today.isoformat(), FALLBACK_TRIVIA)
    payload = {
        "date": human_date(datetime.fromisoformat(current["date"])),
        "question": current["question"],
        "answer": current["answer"],
        "stat_category": current["stat_category"],
        "fun_fact": current["fun_fact"],
        "show_answer": now.hour >= 18 or current["date"] < today.isoformat(),
        "geo_days": days,
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Published {len(days)} day(s): {', '.join(d['date'] for d in days)}")


if __name__ == "__main__":
    generate_geo_loop_data()
