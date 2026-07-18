import os
import json
import sys
import random
from datetime import datetime
import zoneinfo  # Built into Python 3.9+
from PIL import Image, ImageDraw
from google import genai

# Setup Gemini API client using official google-genai SDK
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

HISTORY_FILE = "history.json"
DATA_FILE = "data.json"
IMAGE_FILE = "image.png"

GITHUB_PAGES_BASE_URL = "https://gluu-design.github.io/trmnl-geography-trivia"

# Candidate models to try in order of preference
FALLBACK_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-lite-latest",
    "gemini-1.5-flash",
    "gemini-2.5-pro",
    "gemini-3.1-flash-lite"
]

def generate_eink_image(text_label="GEO LOOP"):
    """Generates a 1-bit monochrome black & white image for TRMNL."""
    width, height = 300, 300
    img = Image.new("1", (width, height), 255)
    draw = ImageDraw.Draw(img)

    # Outer border styling
    draw.rectangle([10, 10, width - 10, height - 10], outline=0, width=4)
    draw.rectangle([16, 16, width - 16, height - 16], outline=0, width=1)

    # Center Globe Ring Illustration
    center_x, center_y, radius = width // 2, height // 2 - 10, 70
    draw.ellipse([center_x - radius, center_y - radius, center_x + radius, center_y + radius], outline=0, width=4)
    draw.ellipse([center_x - radius, center_y - 25, center_x + radius, center_y + 25], outline=0, width=2)
    draw.line([center_x, center_y - radius, center_x, center_y + radius], fill=0, width=2)
    draw.line([center_x - radius, center_y, center_x + radius, center_y], fill=0, width=2)

    img.save(IMAGE_FILE)
    print(f"Generated 1-bit e-ink image saved to {IMAGE_FILE}", flush=True)
    return f"{GITHUB_PAGES_BASE_URL}/{IMAGE_FILE}"

def load_history():
    """Loads past questions/countries to avoid repetitions with solid fallbacks."""
    default_structure = {"used_countries": [], "used_questions": [], "past_trivia": []}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, dict):
                    # Ensure all arrays are structurally present
                    for key in default_structure:
                        content.setdefault(key, [])
                    return content
        except Exception as e:
            print(f"Notice: Could not load {HISTORY_FILE}: {e}", flush=True)
    return default_structure

def save_history(history):
    """Saves updated history to history.json."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    print(f"Successfully sync'd records to {HISTORY_FILE}!", flush=True)

def fetch_gemini_trivia(history):
    """Prompts Gemini with automatic model fallback and historical fallback."""
    recent_countries = ", ".join(history.get("used_countries", [])[-30:])
    
    prompt = f"""
    You are the geography trivia engine for GEO LOOP, a daily smart display trivia app.
    Generate a fascinating, accurate, and engaging geography trivia question.

    RULES:
    1. Do NOT feature any of these recently used countries: [{recent_countries}]
    2. Focus on unique geographic statistics, demography, landforms, extreme points, or cultural/natural landmarks.
    3. Keep 'fun_fact' concise: maximum 2 short sentences (under 180 characters total) so it fits smart display layout constraints without truncation.
    4. Return ONLY a valid JSON object matching the requested schema with no surrounding text or markdown formatting.

    JSON SCHEMA:
    {{
      "question": "Clear, concise geography trivia question",
      "answer": "Primary concise answer name",
      "country": "Country associated with the trivia",
      "stat_category": "Short 2-3 word category (e.g. Demographics, Landforms, Boundaries, Climate)",
      "fun_fact": "A fascinating 1-2 sentence explanation expanding on the trivia (max 180 chars).",
      "image_url": ""
    }}
    """

    # Try live AI models first
    for model_name in FALLBACK_MODELS:
        try:
            print(f"Attempting trivia generation with model: {model_name}...", flush=True)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            print(f"Successfully generated trivia using {model_name}!", flush=True)
            return json.loads(response.text)
        except Exception as e:
            print(f"Model {model_name} failed: {e}. Trying next model...", flush=True)

    # FALLBACK: Random choice from history database
    print("All live AI models failed. Checking historical database fallback...", flush=True)
    past_items = history.get("past_trivia", [])
    if past_items:
        selected = random.choice(past_items)
        print(f"Randomly re-using historical trivia item: {selected.get('question')}", flush=True)
        return selected

    # Ultimate backup safety net
    print("No history items found. Using default backup trivia.", flush=True)
    return {
        "question": "Which country has the most natural lakes in the world?",
        "answer": "Canada",
        "country": "Canada",
        "stat_category": "Landforms",
        "fun_fact": "Canada contains over 60% of all natural lakes on Earth, with more than 879,000 lakes spanning its territory.",
        "image_url": ""
    }

def generate_geo_loop_data():
    # Force America/New_York (EDT) time check regardless of server timezone
    tz = zoneinfo.ZoneInfo("America/New_York")
    now = datetime.now(tz)
    
    today_str = now.strftime("%B %d, %Y")
    is_evening = now.hour >= 18  # True starting at 6:00 PM EDT
    
    print(f"Starting GEO LOOP generation for {today_str}...", flush=True)
    print(f"Current EDT Hour: {now.hour} | show_answer: {is_evening}", flush=True)
    
    # Always establish clean baseline state for history arrays
    history = load_history()
    existing_data = None
    
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"Notice: Could not parse {DATA_FILE}: {e}", flush=True)

    if existing_data and existing_data.get("date") == today_str:
        print(f"Using existing trivia for {today_str}. Updating show_answer={is_evening}", flush=True)
        payload = existing_data
        payload["show_answer"] = is_evening
    else:
        print("Calling Gemini API for new trivia...", flush=True)
        trivia = fetch_gemini_trivia(history)
        generated_image_url = generate_eink_image(trivia.get("country", "GEO LOOP"))
        
        payload = {
            "date": today_str,
            "question": trivia["question"],
            "answer": trivia["answer"],
            "stat_category": trivia["stat_category"],
            "country": trivia["country"],
            "fun_fact": trivia["fun_fact"],
            "image_url": generated_image_url,
            "show_answer": is_evening
        }
        
        # Safely update lists to avoid repeating or duplicate items
        if trivia["country"] not in history["used_countries"]:
            history["used_countries"].append(trivia["country"])
        if trivia["question"] not in history["used_questions"]:
            history["used_questions"].append(trivia["question"])
            
        if not any(item.get("question") == trivia["question"] for item in history["past_trivia"]):
            history["past_trivia"].append(trivia)

    # Always ensure history and main file are committed securely in sync
    save_history(history)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully saved {DATA_FILE}!", flush=True)

if __name__ == "__main__":
    try:
        generate_geo_loop_data()
    except Exception as err:
        print(f"FATAL ERROR: {err}", flush=True)
        sys.exit(1)
