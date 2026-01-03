"""
AI Content Moderation Service using Google Gemini Flash
"""
import os
import json
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Initialize Client
api_key = os.getenv("GEMINI_API_KEY")
client = None

if api_key:
    client = genai.Client(api_key=api_key)
else:
    logger.warning("⚠️ GEMINI_API_KEY is missing. AI moderation will be skipped.")

def scan_media(content_bytes, mime_type, banned_words_list):
    """
    Scans media using Gemini Flash. Returns decision JSON or None on error.
    """
    if not client:
        return None

    # Convert list of words to comma-separated string
    banned_txt = ", ".join(banned_words_list)

    prompt = f"""
    You are a strict Telegram Super Admin Bot.
    Analyze this content (Image, Video, Audio, Sticker, GIF).
    
    STRICT BLOCKING RULES:
    1. Visible URLs, QR Codes, or Telegram Links (t.me).
    2. Text/Audio matching these words: [{banned_txt}].
    3. NSFW, Nudity, Pornography, Gore, Violence.
    
    Return JSON:
    {{
        "action": "BLOCK" or "ALLOW",
        "reason": "Short explanation",
        "violation": "LINK", "WORD", "NSFW", or "NONE"
    }}
    """

    analysis_schema = {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["ALLOW", "BLOCK"]},
            "violation": {"type": "STRING", "enum": ["NONE", "LINK", "WORD", "NSFW"]},
            "reason": {"type": "STRING"},
        },
        "required": ["action", "violation", "reason"]
    }

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp", # Or "gemini-1.5-flash"
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(data=content_bytes, mime_type=mime_type),
                        types.Part.from_text(text=prompt)
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=analysis_schema,
                temperature=0.1
            )
        )
        return json.loads(response.text)

    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        return None # Return None to trigger Manual Fallback