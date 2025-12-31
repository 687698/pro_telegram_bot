"""
Message handlers for processing group messages (Persian/Farsi)
"""

import logging
import re
import asyncio
from telegram import Update, ChatMember, ChatPermissions, MessageEntity
from telegram.ext import ContextTypes
from src.database import db

logger = logging.getLogger(__name__)

# ==================== HELPER FUNCTIONS (Shared by both handlers) ====================

async def delete_later(bot, chat_id, message_id, delay):
    """Wait for 'delay' seconds, then delete the message"""
    try:
        await asyncio.sleep(delay)
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user is a group administrator"""
    if not update.message or not update.effective_user:
        return False
    try:
        user_status = await update.message.chat.get_member(update.effective_user.id)
        admin_statuses = [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        if hasattr(ChatMember, 'CREATOR'):
            admin_statuses.append(ChatMember.CREATOR)
        return user_status.status in admin_statuses
    except Exception:
        return False

async def handle_punishment(update: Update, context: ContextTypes.DEFAULT_TYPE, user, reason: str):
    """Helper to add warn, check for ban, and send flash message"""
    new_warn_count = db.add_warn(user.id)
    user_mention = user.mention_html()
    
    if new_warn_count >= 3:
        try:
            await context.bot.ban_chat_member(chat_id=update.message.chat_id, user_id=user.id)
            msg_text = f"🚫 کاربر {user_mention} به دلیل {reason} و دریافت ۳ اخطار **مسدود شد**!"
        except Exception:
            msg_text = f"🚫 اخطار سوم برای {user_mention} (ربات دسترسی بن ندارد)."
    else:
        msg_text = f"🚫 {user_mention} عزیز, {reason} مجاز نیست.\n⚠️ اخطار: {new_warn_count}/3"

    warning = await context.bot.send_message(chat_id=update.message.chat_id, text=msg_text, parse_mode="HTML")
    asyncio.create_task(delete_later(context.bot, update.message.chat_id, warning.message_id, 5))

# ==================== HANDLER 1: MEDIA (Photos & Videos) ====================

async def check_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles ONLY photos and videos, for the media approval system."""
    if not update.message or not update.effective_user:
        return

    if await is_admin(update, context):
        return

    try:
        await update.message.delete()
        OWNER_ID = 2117254740  # Your ID
        
        try:
            await update.message.forward(chat_id=OWNER_ID)
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"📩 <b>مدیا برای تایید</b>\nکاربر: {update.effective_user.mention_html()}\nگروه: {update.message.chat.title}\n\n✅ تایید: فوروارد به گروه.",
                parse_mode="HTML"
            )
        except Exception:
            pass 

        msg_text = f"🔒 {update.effective_user.mention_html()} عزیز، ارسال فایل نیازمند تایید مدیر است."
        warning = await context.bot.send_message(chat_id=update.message.chat_id, text=msg_text, parse_mode="HTML")
        asyncio.create_task(delete_later(context.bot, update.message.chat_id, warning.message_id, 5))
    except Exception as e:
        logger.error(f"Error in check_media: {e}")

# ==================== HANDLER 2: TEXT (Links & Bad Words) ====================

def has_link(message) -> bool:
    """The advanced link detection logic you liked."""
    entities = message.entities or []
    caption_entities = message.caption_entities or []
    all_entities = list(entities) + list(caption_entities)
    
    for entity in all_entities:
        if entity.type in [MessageEntity.URL, MessageEntity.TEXT_LINK]:
            return True

    text_content = message.text or message.caption or ""
    text_lower = text_content.lower()
    url_keywords = ['http://', 'https://', 'www.', '.com', '.ir', '.net', '.org', 't.me', 'bit.ly']
    for keyword in url_keywords:
        if keyword in text_lower:
            return True

    skeleton = re.sub(r'[^a-z]+', '', text_lower)
    skeleton_clean = re.sub(r'(.)\1+', r'\1', skeleton)
    
    common_sites = ['google', 'gogle', 'youtube', 'yotube', 'instagram', 'telegram', 'whatsapp', 'discord']
    extensions = ['com', 'ir', 'net', 'org', 'xyz', 'tk', 'info', 'io', 'me']
    prefixes = ['http', 'https', 'www', 'tme']

    for site in common_sites:
        for ext in extensions:
            if site + ext in skeleton_clean or site + ext in skeleton:
                return True
    
    found_prefix = False
    for p in prefixes:
        if p in skeleton_clean or p in skeleton:
            found_prefix = True; break
            
    if found_prefix:
        for ext in extensions:
            if ext in skeleton_clean or ext in skeleton:
                return True
                
    if 'tme' in skeleton_clean or 'http' in skeleton_clean:
        return True
            
    return False

def normalize_text(text: str) -> str:
    """Creates a 'skeleton' version of the text to catch hidden bad words."""
    if not text: return ""
    clean = re.sub(r'[\s_\.\-\u200c\u200f,،!@#$%^&*()]+', '', text)
    clean = re.sub(r'(.)\1+', r'\1', clean)
    return clean.lower()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles ONLY text and captions, for links and bad words."""
    if not update.message or not update.effective_user:
        return
    
    user = update.effective_user
    message = update.message
    db.initialize_user(user.id, user.username or "Unknown")
    
    if await is_admin(update, context):
        return

    message_text = message.text or message.caption or ""
    if not message_text:
        return
    message_text_lower = message_text.lower()
    
    # 1. LINK DETECTION
    if has_link(message):
        try:
            await message.delete()
            await handle_punishment(update, context, user, "ارسال لینک")
            return
        except Exception as e:
            logger.error(f"Error handling link: {e}")
            return
    
    # 2. BANNED WORDS DETECTION
    banned_words = db.get_banned_words()
    if banned_words:
        found_banned_words = []
        cleaned_message = normalize_text(message_text_lower)
        
        for banned_word in banned_words:
            if banned_word in message_text_lower or banned_word in cleaned_message:
                found_banned_words.append(banned_word)
        
        if found_banned_words:
            try:
                await message.delete()
                await handle_punishment(update, context, user, "ارسال کلمات نامناسب")
                return
            except Exception as e:
                logger.error(f"Error handling bad word: {e}")