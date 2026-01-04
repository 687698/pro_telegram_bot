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

    # 🟢 SUPER PROMPT: STRICT RULES FOR LINKS, WORDS, AND PORN
    prompt = f"""
    You are a strict Telegram Super Admin Bot.
    Analyze this content (Image, Video, Audio, Sticker, GIF).
    
    STRICT BLOCKING RULES:
    1. 🚫 PORNO/NSFW: Nudity, sexual acts, excessive gore, or violence.
    
    2. 🚫 LINKS (CRITICAL): 
       - Look for ANY website URL, QR Code, or Telegram link (t.me, @username).
       - CATCH HIDDEN LINKS: "w w w . g o o g l e . c o m", "google dot com", "t (dot) me".
       - If you see "www", "http", ".com", ".ir", ".net" -> BLOCK IT.
    
    3. 🚫 BANNED WORDS (CRITICAL):
       - Look for these specific words: [{banned_txt}].
       - CATCH HIDDEN WORDS: "b a d w o r d", "b.a.d.w.o.r.d", "b_a_d".
       - If the text is fuzzy or hard to read but looks like a banned word -> BLOCK IT.
    
    OUTPUT FORMAT (JSON ONLY):
    {{
        "action": "BLOCK" or "ALLOW",
        "violation": "LINK", "WORD", "NSFW", or "NONE",
        "reason": "Short explanation of what was found"
    }}
    """

    # Disable safety filters so the AI can actually SEE the bad content to judge it
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    try:
       # Try specific stable version
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
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