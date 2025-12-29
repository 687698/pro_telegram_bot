"""
Message handlers for processing group messages (Persian/Farsi)
Anti-spam filter with URL detection and banned words checking
"""

import logging
import re
from telegram import Update, ChatMember
from telegram.ext import ContextTypes
from src.database import db

logger = logging.getLogger(__name__)


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


def contains_url(text: str) -> bool:
    """
    Check if text contains URLs
    
    Args:
        text: Text to check
        
    Returns:
        True if URL found
    """
    # Check for common URL patterns
    if re.search(URL_PATTERN, text):
        return True
    
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
    """
    Handle incoming messages - Check for banned words and URLs
    Professional anti-spam filter for Persian groups
    """
    if not update.message or not update.message.text or not update.effective_user:
        return
    
    user = update.effective_user
    message = update.message
    message_text = message.text
    message_text_lower = message_text.lower()
    
    # Initialize user in database if new
    db.initialize_user(user.id, user.username or "Unknown")
    
    # Skip checking for admins
    if await is_admin(update, context):
        return
    
    # ==================== URL/LINK DETECTION ====================
    
    if contains_url(message_text):
        try:
            # 1. Delete Bad Message
            await message.delete()
            
            # 2. Send Warning (Tagging User)
            user_mention = user.mention_html()
            warning_msg = f"🚫 {user_mention} عزیز، ارسال لینک ممنوع است."
            
            warning = await context.bot.send_message(
                chat_id=message.chat_id,
                text=warning_msg,
                parse_mode="HTML"
            )
            
            # 3. Delete Warning after 5 SECONDS
            context.job_queue.run_once(
                lambda ctx: ctx.bot.delete_message(message.chat_id, warning.message_id),
                when=5, # <--- Short time
                name=f"delete_link_{warning.message_id}"
            )
            
            await log_spam_event(user.id, user.username or "Unknown", "link", message_text[:100], message.chat_id)
            return
        except Exception as e:
            logger.error(f"Error: {e}")
            return
    
    # ==================== BANNED WORDS DETECTION ====================
    
    # Get banned words from cache
    banned_words = db.get_banned_words()
    
    if banned_words:
        found_banned_words = []
        
        # Create the "Smart Cleaned" version of the message
        cleaned_message = normalize_text(message_text_lower)
        
        for banned_word in banned_words:
            # Check 1: Does it exist normally?
            check_1 = banned_word in message_text_lower
            
            # Check 2: Does it exist in the cleaned version? (Hidden words)
            check_2 = banned_word in cleaned_message
            
            if check_1 or check_2:
                found_banned_words.append(banned_word)
        
        if found_banned_words:
            try:
                # 1. Delete Bad Message
                await message.delete()
                
                # 2. Send Warning
                user_mention = user.mention_html()
                warning_msg = f"🚫 {user_mention} عزیز، لطفاً از کلمات مناسب استفاده کنید."
                
                warning = await context.bot.send_message(
                    chat_id=message.chat_id,
                    text=warning_msg,
                    parse_mode="HTML"
                )
                
                # 3. Delete Warning after 5 SECONDS
                context.job_queue.run_once(
                    lambda ctx: ctx.bot.delete_message(message.chat_id, warning.message_id),
                    when=5, # <--- Short time
                    name=f"delete_word_{warning.message_id}"
                )
                
                await log_spam_event(user.id, user.username or "Unknown", "banned_word", message_text[:100], message.chat_id)
                return
            except Exception as e:
                logger.error(f"Error: {e}")