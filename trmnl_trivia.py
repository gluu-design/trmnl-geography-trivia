import os
import json
from datetime import datetime
import google.generativeai as genai

# Setup Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

HISTORY_FILE = "history.json"
DATA_FILE = "data.json"

def load_history():
    """Loads past questions/countries to avoid repetitions."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"countries": [], "questions": []}
    return {"countries": [], "questions": []}

def save_history(history):
    """Saves updated history to history.json."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def fetch_gemini_trivia(history):
    """Prompts Gemini to generate a unique geography trivia item."""
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    recent_countries = ", ".join(history.get("countries", [])[-30:])  # Exclude last 30 countries
    
    prompt = f"""
    You are the geography trivia engine for GEO LOOP, a daily smart display trivia app.
    Generate a fascinating, accurate, and engaging geography trivia question.

    RULES:
    1. Do NOT feature any of these recently used countries: [{recent_countries}]
    2. Focus on unique geographic statistics, demography, landforms, extreme points, or cultural/natural landmarks.
    3. Return ONLY a valid JSON object matching the requested schema with no surrounding text or markdown formatting.

    JSON SCHEMA:
    {{
      "question": "Clear, concise geography trivia question",
      "answer": "Primary concise answer name",
      "country": "Country associated with the trivia",
      "stat_category": "Short 2-3 word category (e.g. Demographics, Landforms, Boundaries, Climate)",
      "fun_fact": "A fascinating 2-3 sentence explanation expanding on the trivia.",
      "image_url": ""
    }}
    """
    
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    
    trivia_data = json.loads(response.text)
    return trivia_data

def generate_geo_loop_data():
    now = datetime.now()
    today_str = now.strftime("%B %d, %Y")
    is_evening = now.hour >= 18  # True after 6:00 PM local runner time
    
    # Check if we already generated a question for today
    existing_data = None
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            existing_data = None

    # If today's question already exists, keep it and just update the answer state
    if existing_data and existing_data.get("date") == today_str:
        print(f"Using existing question for {today_str}. Setting show_answer={is_evening}")
        payload = existing_data
        payload["show_answer"] = is_evening
    else:
        # Generate brand new trivia for today
        print(f"Generating new GEO LOOP trivia for {today_str}...")
        history = load_history()
        trivia = fetch_gemini_trivia(history)
        
        payload = {
            "date": today_str,
            "question": trivia["question"],
            "answer": trivia["answer"],
            "stat_category": trivia["stat_category"],
            "country": trivia["country"],
            "fun_fact": trivia["fun_fact"],
            "image_url": trivia.get("image_url", ""),
            "show_answer": is_evening
        }
        
        # Update history
        history.setdefault("countries", []).append(trivia["country"])
        history.setdefault("questions", []).append(trivia["question"])
        save_history(history)

    # Write final output to data.json
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully updated {DATA_FILE}!")

if __name__ == "__main__":
    generate_geo_loop_data()
