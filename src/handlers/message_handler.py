"""
Message handlers for processing group messages (Persian/Farsi)
Anti-spam filter with URL detection and banned words checking
"""

import logging
import re
import asyncio
from telegram import Update, ChatMember, ChatPermissions, MessageEntity
from telegram.ext import ContextTypes
from src.database import db

logger = logging.getLogger(__name__)

# ==================== HELPER FUNCTIONS ====================

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

def has_link(message) -> bool:
    """
    Check if message contains a link using Telegram Entities AND Keywords.
    Checks both Message Text and Caption.
    """
    # 1. Check Telegram Entities (The most accurate way)
    entities = message.entities or []
    caption_entities = message.caption_entities or []
    all_entities = list(entities) + list(caption_entities)
    
    for entity in all_entities:
        if entity.type in [MessageEntity.URL, MessageEntity.TEXT_LINK]:
            return True

    # 2. Fallback: Keyword check
    text_content = message.text or message.caption or ""
    text_lower = text_content.lower()
    
    url_keywords = ['http://', 'https://', 'www.', '.com', '.ir', '.net', '.org', 't.me', 'bit.ly']
    for keyword in url_keywords:
        if keyword in text_lower:
            return True
            
    return False

def normalize_text(text: str) -> str:
    """
    Creates a 'skeleton' version of the text to catch hidden bad words.
    Example: 'ک___و ن...ی' -> 'کونی'
    """
    if not text:
        return ""
    # Remove symbols and repeating chars
    clean = re.sub(r'[\s_\.\-\u200c\u200f,،!@#$%^&*()]+', '', text)
    clean = re.sub(r'(.)\1+', r'\1', clean)
    return clean.lower()

async def log_spam_event(user_id: int, username: str, spam_type: str, content: str, chat_id: int):
    try:
        logger.warning(f"🚨 Spam: {spam_type} | User: {username}({user_id}) | Content: {content}")
    except Exception:
        pass

async def handle_punishment(update: Update, context: ContextTypes.DEFAULT_TYPE, user, reason: str):
    """
    Helper to add warn, check for ban, and send flash message
    """
    # 1. Add warning to Database
    new_warn_count = db.add_warn(user.id)
    user_mention = user.mention_html()
    
    # 2. Check for Ban (3 Strikes)
    if new_warn_count >= 3:
        try:
            await context.bot.ban_chat_member(chat_id=update.message.chat_id, user_id=user.id)
            msg_text = f"🚫 کاربر {user_mention} به دلیل {reason} و دریافت ۳ اخطار **مسدود شد**!"
        except Exception:
            msg_text = f"🚫 اخطار سوم برای {user_mention} (ربات دسترسی بن ندارد)."
    else:
        # Warning
        msg_text = f"🚫 {user_mention} عزیز، {reason} مجاز نیست.\n⚠️ اخطار: {new_warn_count}/3"

    # 3. Send Flash Message
    warning = await context.bot.send_message(
        chat_id=update.message.chat_id,
        text=msg_text,
        parse_mode="HTML"
    )
    # Delete warning after 5 seconds
    asyncio.create_task(delete_later(context.bot, update.message.chat_id, warning.message_id, 5))


# ==================== MAIN HANDLER ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages (Text and Captions)"""
    # 1. Basic checks (User exists?)
    # Removed "not update.message.text" so we can check photos too!
    if not update.message or not update.effective_user:
        return
    
    user = update.effective_user
    message = update.message
    
    # 2. Get Content (Text OR Caption)
    message_text = message.text or message.caption or ""
    
    # If there is absolutely no content (e.g. just a sticker), ignore
    if not message_text:
        return

    message_text_lower = message_text.lower()
    
    # Initialize user in DB
    db.initialize_user(user.id, user.username or "Unknown")
    
    # 3. Skip Admins (Admins can do whatever they want)
    if await is_admin(update, context):
        return
    
    # ==================== CHECK 1: LINKS ====================
    if has_link(message):
        try:
            await message.delete()
            await handle_punishment(update, context, user, "ارسال لینک")
            await log_spam_event(user.id, user.username or "Unknown", "link", message_text[:100], message.chat_id)
            return
        except Exception as e:
            logger.error(f"Error handling link: {e}")
            return
    
    # ==================== CHECK 2: BANNED WORDS ====================
    banned_words = db.get_banned_words()
    
    if banned_words:
        found_banned_words = []
        # Create normalized version to catch "h i d d e n" words
        cleaned_message = normalize_text(message_text_lower)
        
        for banned_word in banned_words:
            # Check 1: Exact match in raw text
            check_1 = banned_word in message_text_lower
            # Check 2: Match in normalized (clean) text
            check_2 = banned_word in cleaned_message
            
            if check_1 or check_2:
                found_banned_words.append(banned_word)
        
        if found_banned_words:
            try:
                await message.delete()
                await handle_punishment(update, context, user, "ارسال کلمات نامناسب")
                await log_spam_event(user.id, user.username or "Unknown", "banned_word", message_text[:100], message.chat_id)
                return
            except Exception as e:
                logger.error(f"Error handling bad word: {e}")