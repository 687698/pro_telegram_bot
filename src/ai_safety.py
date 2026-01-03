"""
AI Content Moderation Service using Google Gemini Flash (Stable Version)
"""
import os
import json
import logging
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

logger = logging.getLogger(__name__)

# Initialize Client
api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)
else:
    logger.warning("⚠️ GEMINI_API_KEY is missing. AI moderation will be skipped.")

def scan_media(content_bytes, mime_type, banned_words_list):
    """
    Scans media using Gemini Flash. Returns decision JSON or None on error.
    """
    if not api_key:
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
    
    Return ONLY a JSON object with this format (no markdown):
    {{
        "action": "BLOCK" or "ALLOW",
        "violation": "LINK", "WORD", "NSFW", or "NONE",
        "reason": "Short explanation"
    }}
    """

    # Safety settings to allow the model to see bad things so it can judge them
    # (We don't want the model to block itself from seeing the porn)
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Prepare content blob
        content_blob = {
            'mime_type': mime_type,
            'data': content_bytes
        }

        response = model.generate_content(
            [prompt, content_blob],
            safety_settings=safety_settings
        )
        
        # Clean response (sometimes it wraps in ```json ... ```)
        text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(text)

    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        return None # Return None to trigger Manual Fallback