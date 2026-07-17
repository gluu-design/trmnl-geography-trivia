import os
import json
import sys
from datetime import datetime
from PIL import Image, ImageDraw
from google import genai

# Setup Gemini API client using official google-genai SDK
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

HISTORY_FILE = "history.json"
DATA_FILE = "data.json"
IMAGE_FILE = "image.png"

# UPDATE THIS URL to match your GitHub Pages endpoint!
GITHUB_PAGES_BASE_URL = "https://gluu-design.github.io/trmnl-geography-trivia"

def generate_eink_image(text_label="GEO LOOP"):
    """Generates a 1-bit monochrome black & white image for TRMNL."""
    width, height = 300, 300
    # Create 1-bit monochrome image (mode '1': 0=black, 255=white)
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

    # Save 1-bit PNG
    img.save(IMAGE_FILE)
    print(f"Generated 1-bit e-ink image saved to {IMAGE_FILE}", flush=True)
    return f"{GITHUB_PAGES_BASE_URL}/{IMAGE_FILE}"

def load_history():
    """Loads past questions/countries to avoid repetitions."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Notice: Could not load {HISTORY_FILE}: {e}", flush=True)
            return {"used_countries": [], "used_questions": []}
    return {"used_countries": [], "used_questions": []}

def save_history(history):
    """Saves updated history to history.json."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def fetch_gemini_trivia(history):
    """Prompts Gemini to generate a unique geography trivia item."""
    recent_countries = ", ".join(history.get("used_countries", [])[-30:])
    
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
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)

def generate_geo_loop_data():
    now = datetime.now()
    today_str = now.strftime("%B %d, %Y")
    is_evening = now.hour >= 18
    
    print(f"Starting GEO LOOP generation for {today_str}...", flush=True)
    
    existing_data = None
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"Notice: Could not parse {DATA_FILE}: {e}", flush=True)

    if existing_data and existing_data.get("date") == today_str:
        print(f"Using existing trivia for {today_str}. Setting show_answer={is_evening}", flush=True)
        payload = existing_data
        payload["show_answer"] = is_evening
    else:
        print("Calling Gemini API for new trivia...", flush=True)
        history = load_history()
        trivia = fetch_gemini_trivia(history)
        
        # Generate the black and white image file
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
        
        history.setdefault("used_countries", []).append(trivia["country"])
        history.setdefault("used_questions", []).append(trivia["question"])
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
