def load_history():
    """Loads past questions/countries to avoid repetitions."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"used_countries": [], "used_questions": []}
    return {"used_countries": [], "used_questions": []}

def save_history(history):
    """Saves updated history to history.json."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def fetch_gemini_trivia(history):
    """Prompts Gemini to generate a unique geography trivia item."""
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # Reads from your "used_countries" key
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
    
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    
    trivia_data = json.loads(response.text)
    return trivia_data
