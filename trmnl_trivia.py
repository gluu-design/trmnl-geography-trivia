import os
import json
import zoneinfo
from datetime import datetime
from google import genai
from google.genai import types

# Setup Gemini API client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

HISTORY_FILE = "history.json"
DATA_FILE = "data.json"

FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash"
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
    """
    
    # Define a strict schema to guarantee a dictionary is returned with all needed keys
    trivia_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "question": types.Schema(type=types.Type.STRING),
            "answer": types.Schema(type=types.Type.STRING),
            "stat_category": types.Schema(type=types.Type.STRING),
            "fun_fact": types.Schema(type=types.Type.STRING),
            "country": types.Schema(type=types.Type.STRING, description="The primary country this trivia is about")
        },
        required=["question", "answer", "stat_category", "fun_fact", "country"]
    )

    for model_name in FALLBACK_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=trivia_schema,
                    temperature=0.7
                )
            )
            
            # Robust parsing: catch edge cases where the LLM still wraps it in a list
            result = json.loads(response.text)
            if isinstance(result, list) and len(result) > 0:
                result = result[0]
                
            return result
            
        except Exception as e:
            print(f"Model {model_name} failed: {e}")
            continue
            
    # Fallback if all models fail
    return {
        "question": "Which country has the most natural lakes?", 
        "answer": "Canada", 
        "stat_category": "Landforms", 
        "fun_fact": "Canada has over 60% of Earth's lakes.",
        "country": "Canada"
    }

def generate_geo_loop_data():
    tz = zoneinfo.ZoneInfo("America/New_York")
    now = datetime.now(tz)
    today_str = now.strftime("%B %d, %Y")
    is_evening = now.hour >= 18
    
    history = load_history()
    trivia = fetch_gemini_trivia(history)
    
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
