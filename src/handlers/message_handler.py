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

async def delete_later(bot, chat_id, message_id, delay):
    """Wait for 'delay' seconds, then delete the message"""
    try:
        await asyncio.sleep(delay)
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


# Regex pattern for detecting URLs
URL_PATTERN = re.compile(
    r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
)


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user is a group administrator"""
    if not update.message or not update.effective_user:
        return False
    
    try:
        # Get user status in the chat
        user_status = await update.message.chat.get_member(update.effective_user.id)
        
        # Check if user is admin or owner (CREATOR is deprecated, use OWNER)
        admin_statuses = [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        
        # Fallback for older versions that might still use CREATOR
        if hasattr(ChatMember, 'CREATOR'):
            admin_statuses.append(ChatMember.CREATOR)
        
        return user_status.status in admin_statuses
    except Exception as e:
        logger.error(f"خطا در بررسی دسترسی ادمین: {e}")
        return False


def has_link(message) -> bool:
    """
    Check if message contains a link using Telegram Entities AND Keywords.
    Checks both Message Text and Caption.
    """
    # 1. Check Telegram Entities (The most accurate way)
    # This detects 'google.com', 'http://...', and text links [Click Here](url)
    entities = message.entities or []
    caption_entities = message.caption_entities or []
    all_entities = list(entities) + list(caption_entities)
    
    for entity in all_entities:
        if entity.type in [MessageEntity.URL, MessageEntity.TEXT_LINK]:
            return True

    # 2. Fallback: Keyword check (for sneaky links Telegram might miss)
    # We check the content of both text and caption
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
        
    # 1. Remove all spaces, dots, underscores, dashes, zero-width joiners, commas, symbols
    clean = re.sub(r'[\s_\.\-\u200c\u200f,،!@#$%^&*()]+', '', text)
    
    # 2. Remove repeating characters (e.g., "کوووونی" -> "کونی")
    clean = re.sub(r'(.)\1+', r'\1', clean)
    
    return clean.lower()
    
    # Check for common URL shortcuts
    url_keywords = ['http://', 'https://', 'www.', '.com', '.ir', '.net', '.org', 't.me', 'bit.ly']
    text_lower = text.lower()
    for keyword in url_keywords:
        if keyword in text_lower:
            return True
    
    return False


async def log_spam_event(user_id: int, username: str, spam_type: str, content: str, chat_id: int):
    """
    Log spam event to database and logger
    
    Args:
        user_id: User's Telegram ID
        username: User's username
        spam_type: Type of spam ('banned_word' or 'link')
        content: The spam content
        chat_id: Chat ID where spam occurred
    """
    try:
        logger.warning(
            f"🚨 رویداد اسپم: {spam_type} | کاربر: {username}({user_id}) | "
            f"محتوا: {content} | گروه: {chat_id}"
        )
        # Could store in database if spam_logs table exists
    except Exception as e:
        logger.error(f"خطا در ثبت رویداد اسپم: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    # Removed "not update.message.text" so we can check photos too!
    if not update.message or not update.effective_user:
        return
    
    user = update.effective_user
    message = update.message
    
    # 🟢 1. Combine Text and Caption
    # We rename 'message_text' to 'message_content' effectively
    message_text = message.text or message.caption or ""
    
    # If just a photo with no words, ignore
    if not message_text:
        return
        
    message_text_lower = message_text.lower()
    
    # Initialize user
    db.initialize_user(user.id, user.username or "Unknown")
    
    # Skip admins
    if await is_admin(update, context):
        return
    
    # ==================== URL/LINK DETECTION ====================
    # 🟢 2. Use the new has_link function (pass the WHOLE message)
    if has_link(message):
        try:
            # 1. Delete Bad Message
            await message.delete()
            
            # 2. Add Warning to Database
            new_warn_count = db.add_warn(user.id)
            user_mention = user.mention_html()
            
            # 3. Check if Ban is needed
            if new_warn_count >= 3:
                try:
                    await context.bot.ban_chat_member(chat_id=message.chat_id, user_id=user.id)
                    warning_msg = f"🚫 کاربر {user_mention} به دلیل ارسال لینک و دریافت ۳ اخطار **مسدود شد**!"
                except Exception:
                    warning_msg = f"🚫 اخطار سوم برای {user_mention} (ربات دسترسی بن ندارد)."
            else:
                warning_msg = f"🚫 {user_mention} عزیز، ارسال لینک ممنوع است.\n⚠️ اخطار: {new_warn_count}/3"
            
            # 4. Send Flash Message
            warning = await context.bot.send_message(
                chat_id=message.chat_id,
                text=warning_msg,
                parse_mode="HTML"
            )
            asyncio.create_task(delete_later(context.bot, message.chat_id, warning.message_id, 5))
            
            await log_spam_event(user.id, user.username or "Unknown", "link", message_text[:100], message.chat_id)
            return
        except Exception as e:
            logger.error(f"Error handling link: {e}")
            return