import os
import json
import re
import base64
from datetime import datetime
import pytz
import requests
from google import genai
from google.genai import types

HISTORY_FILE = "history.json"

def clean_json_string(text: str) -> str:
    """Removes markdown code blocks if present."""
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text

def load_history():
    """Loads historical questions and countries from JSON file."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load history ({e}). Starting fresh.")
    return {"used_countries": [], "used_questions": []}

def save_history(history_data):
    """Saves updated history back to JSON file."""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_data, f, indent=2)
        print("Updated history.json successfully.")
    except Exception as e:
        print(f"Error saving history: {e}")

def generate_trivia_image(client, country: str, stat_category: str) -> str:
    """Generates a black-and-white e-ink illustration and returns a base64 Data URL."""
    prompt = (
        f"A minimalist, high-contrast black and white vintage line-art woodcut engraving "
        f"representing a landmark or symbol of {country} related to {stat_category}. "
        f"Clean solid line art, white background, no color, no shading, e-ink screen style."
    )
    try:
        result = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="image/png"
            )
        )
        
        for part in result.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                image_bytes = part.inline_data.data
                b64_str = base64.b64encode(image_bytes).decode('utf-8')
                print("Image generated successfully!")
                return f"data:image/png;base64,{b64_str}"
    except Exception as e:
        print(f"Warning: Image generation skipped ({e}). Continuing without image.")
    
    return ""

def main():
    # 1. Determine local time state for New York (EST/EDT)
    local_tz = pytz.timezone("America/New_York")
    now_local = datetime.now(local_tz)
    current_hour = now_local.hour

    show_answer = current_hour >= 18 or current_hour < 6

    # 2. Retrieve secrets
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    webhook_url = os.getenv("TRMNL_WEBHOOK_URL")

    if not api_key:
        raise ValueError("CRITICAL ERROR: GEMINI_API_KEY secret is missing.")
    if not webhook_url:
        raise ValueError("CRITICAL ERROR: TRMNL_WEBHOOK_URL secret is missing.")

    # 3. Load past history
    history = load_history()
    recent_countries = history.get("used_countries", [])[-30:] # Keep last 30
    recent_questions = history.get("used_questions", [])[-30:]

    client = genai.Client(api_key=api_key)

    # 4. Prompt with strict anti-repetition instructions
    prompt = (
        "Generate a unique fun geography trivia question based on an interesting or unusual statistic.\n"
        f"STRICT REQUIREMENT: Do NOT use any of these previously covered subjects/countries: {json.dumps(recent_countries)}.\n"
        f"STRICT REQUIREMENT: Do NOT repeat any similar questions from this list: {json.dumps(recent_questions)}.\n\n"
        "Return ONLY a raw, valid JSON object with no markdown formatting or backticks. Schema:\n"
        "{\n"
        '  "country": "Name of Country or City",\n'
        '  "stat_category": "Short Category Label",\n'
        '  "question": "The question text",\n'
        '  "answer": "The concise answer",\n'
        '  "fun_fact": "A 1-sentence follow-up fun fact"\n'
        "}"
    )

    models_to_try = ["gemini-3.5-flash", "gemini-3.1-flash-lite"]
    interaction = None

    for model_name in models_to_try:
        try:
            print(f"Attempting trivia generation with {model_name}...")
            interaction = client.interactions.create(
                model=model_name,
                input=prompt
            )
            print(f"Successfully generated trivia with {model_name}!")
            break
        except Exception as e:
            print(f"Warning: {model_name} hit an error ({e}). Trying fallback...")

    if not interaction:
        raise RuntimeError("CRITICAL ERROR: All Gemini models failed to respond.")

    raw_text = interaction.output_text
    json_str = clean_json_string(raw_text)
    trivia_data = json.loads(json_str)

    country = trivia_data.get("country", "Geography Trivia")
    stat_category = trivia_data.get("stat_category", "Fun Stat")
    question = trivia_data.get("question", "Question unavailable")

    # 5. Update and Save History
    if country not in history["used_countries"]:
        history["used_countries"].append(country)
    history["used_questions"].append(question)
    save_history(history)

    # 6. Generate B&W Illustration
    image_data_url = generate_trivia_image(client, country, stat_category)

    # 7. Construct payload for TRMNL
    payload = {
        "merge_variables": {
            "date": now_local.strftime("%B %d, %Y"),
            "country": country,
            "stat_category": stat_category,
            "question": question,
            "answer": trivia_data.get("answer", "Answer unavailable"),
            "fun_fact": trivia_data.get("fun_fact", ""),
            "image_url": image_data_url,
            "show_answer": show_answer
        }
    }

    # 8. Push payload to TRMNL Webhook
    res = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    print(f"TRMNL Response Code: {res.status_code}")
    print(f"TRMNL Response Body: {res.text}")

if __name__ == "__main__":
    main()
