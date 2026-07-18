import os
import json
import sys
import random
from datetime import datetime
import zoneinfo
from google import genai

# Setup Gemini API client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

HISTORY_FILE = "history.json"
DATA_FILE = "data.json"

FALLBACK_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-lite-latest",
    "gemini-1.5-flash",
    "gemini-2.5-pro",
    "gemini-3.1-flash-lite"
]

def load_history():
    default_structure = {"used_countries": [], "used_questions": [], "past_trivia": []}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, dict):
                    for key in default_structure:
                        content.setdefault(key, [])
                    return content
        except Exception:
            pass
    return default_structure

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def fetch_gemini_trivia(history):
    recent_countries = ", ".join(history.get("used_countries", [])[-30:])
    prompt = f"""
    Generate a fascinating geography trivia question.
    1. No countries from: [{recent_countries}]
    2. Focus on statistics, landforms, or landmarks.
    3. 'fun_fact' must be under 180 characters.
    4. Return ONLY valid JSON.
    """
    for model_name in FALLBACK_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception:
            continue
    return {"question": "Which country has the most natural lakes?", "answer": "Canada", "stat_category": "Landforms", "fun_fact": "Canada has over 60% of Earth's lakes."}

def generate_geo_loop_data():
    tz = zoneinfo.ZoneInfo("America/New_York")
    now = datetime.now(tz)
    today_str = now.strftime("%B %d, %Y")
    is_evening = now.hour >= 18
    
    history = load_history()
    trivia = fetch_gemini_trivia(history)
    
    # Removed image generation logic entirely
    payload = {
        "date": today_str,
        "question": trivia["question"],
        "answer": trivia["answer"],
        "stat_category": trivia["stat_category"],
        "fun_fact": trivia["fun_fact"],
        "show_answer": is_evening
    }
    
    if trivia.get("country") and trivia["country"] not in history["used_countries"]:
        history["used_countries"].append(trivia["country"])
    history["past_trivia"].append(trivia)
    save_history(history)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    generate_geo_loop_data()
