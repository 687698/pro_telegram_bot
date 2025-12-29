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
            # Delete the message
            await message.delete()
            
            # Send Persian warning
            warning_msg = """🚫 <b>اخطار:</b>

ارسال لینک در این گروه مجاز نیست!

⛔ لطفاً از ارسال لینک‌ها خودداری کنید."""
            
            warning = await message.reply_text(warning_msg, parse_mode="HTML")
            
            # Log the event
            await log_spam_event(
                user.id,
                user.username or "Unknown",
                "link",
                message_text[:100],
                message.chat_id
            )
            
            # Delete warning message after 10 seconds
            context.job_queue.run_once(
                lambda ctx: ctx.bot.delete_message(message.chat_id, warning.message_id),
                when=10,
                name=f"delete_link_warning_{warning.message_id}"
            )
            
            logger.warning(
                f"🔗 لینک توسط {user.id} (@{user.username}) حذف شد. "
                f"گروه: {message.chat_id}"
            )
            return
            
        except Exception as e:
            logger.error(f"خطا در حذف پیام حاوی لینک: {e}")
            return
    
    # ==================== BANNED WORDS DETECTION ====================
    
    # Get banned words from cache
    banned_words = db.get_banned_words()
    
    if banned_words:
        found_banned_words = []
        
        for banned_word in banned_words:
            # Check if banned word exists in message (word boundary checking)
            if re.search(r'\b' + re.escape(banned_word) + r'\b', message_text_lower):
                found_banned_words.append(banned_word)
        
        if found_banned_words:
            try:
                # Delete the message
                await message.delete()
                
                # Create warning message
                words_list = "، ".join(found_banned_words)
                warning_msg = f"""🚫 <b>اخطار:</b>

ارسال کلمات ممنوعه در این گروه مجاز نیست!

⛔ کلمات حذف‌شده: <code>{words_list}</code>

⚠️ لطفاً رعایت قوانین گروه کنید."""
                
                warning = await message.reply_text(warning_msg, parse_mode="HTML")
                
                # Log the event
                await log_spam_event(
                    user.id,
                    user.username or "Unknown",
                    "banned_word",
                    message_text[:100],
                    message.chat_id
                )
                
                # Delete warning message after 10 seconds
                context.job_queue.run_once(
                    lambda ctx: ctx.bot.delete_message(message.chat_id, warning.message_id),
                    when=10,
                    name=f"delete_banned_word_warning_{warning.message_id}"
                )
                
                logger.warning(
                    f"⛔ کلمات ممنوعه توسط {user.id} (@{user.username}) حذف شد: {found_banned_words}. "
                    f"گروه: {message.chat_id}"
                )
                return
                
            except Exception as e:
                logger.error(f"خطا در حذف پیام حاوی کلمات ممنوعه: {e}")
