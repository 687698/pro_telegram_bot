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
    Check if message contains a link (Standard, Entities, Obfuscated).
    Catches: "w w w . g o o g l e . c o m" and "gg..oo..gl..e..com"
    """
    # 1. Check Telegram Entities
    entities = message.entities or []
    caption_entities = message.caption_entities or []
    all_entities = list(entities) + list(caption_entities)
    
    for entity in all_entities:
        if entity.type in [MessageEntity.URL, MessageEntity.TEXT_LINK]:
            return True

    # 2. Get content
    text_content = message.text or message.caption or ""
    text_lower = text_content.lower()

    # 3. Check Standard Keywords
    url_keywords = ['http://', 'https://', 'www.', '.com', '.ir', '.net', '.org', 't.me', 'bit.ly']
    for keyword in url_keywords:
        if keyword in text_lower:
            return True

    # 4. ADVANCED: De-obfuscation Check (Skeleton Check)
    
    # Step A: Remove EVERYTHING except letters
    # Example: "g ..o..o..g..l..e" -> "ggooogggleeecooomm"
    skeleton = re.sub(r'[^a-z]+', '', text_lower)
    
    # Step B: Remove Repeating Characters (Deduplication)
    # Example: "ggooogggleeecooomm" -> "goglecom"
    skeleton_clean = re.sub(r'(.)\1+', r'\1', skeleton)
    
    # Lists of dangerous patterns
    common_sites = ['google', 'gogle', 'youtube', 'yotube', 'instagram', 'telegram', 'whatsapp', 'discord']
    extensions = ['com', 'ir', 'net', 'org', 'xyz', 'tk', 'info', 'io', 'me']
    prefixes = ['http', 'https', 'www', 'tme']

    # Logic A: Check for Known Sites + Extension
    for site in common_sites:
        for ext in extensions:
            if site + ext in skeleton_clean:
                return True
            if site + ext in skeleton:
                return True

    # Logic B: Check for Standard Prefixes + Extension
    found_prefix = False
    for p in prefixes:
        if p in skeleton_clean or p in skeleton:
            found_prefix = True
            break
            
    if found_prefix:
        for ext in extensions:
            if ext in skeleton_clean or ext in skeleton:
                return True
                
    if 'tme' in skeleton_clean or 'http' in skeleton_clean:
        return True
            
    return False

async def check_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks for Photos/Videos.
    If found: Deletes, Forwards to Admin, Warns User.
    Returns: True if media was found (so we can stop processing), False otherwise.
    """
    message = update.message
    user = update.effective_user
    
    # Check for Photo or Video
    if message.photo or message.video:
        try:
            # 1. Delete from group immediately
            await message.delete()

            # 2. Forward to Owner (Media Approval)
            # Your ID:
            OWNER_ID = 2117254740
            
            try:
                await message.forward(chat_id=OWNER_ID)
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"📩 <b>مدیا برای تایید</b>\nکاربر: {user.mention_html()}\nگروه: {message.chat.title}\n\n✅ اگر تایید می‌کنید، آن را به گروه فوروارد کنید.",
                    parse_mode="HTML"
                )
            except Exception:
                pass # Owner might have blocked bot

            # 3. Warning to User (Flash Message)
            msg_text = f"🔒 {user.mention_html()} عزیز، ارسال فایل نیازمند تایید مدیر است."
            warning = await context.bot.send_message(
                chat_id=message.chat_id, 
                text=msg_text, 
                parse_mode="HTML"
            )

            # 4. Delete warning after 5 seconds
            asyncio.create_task(delete_later(context.bot, message.chat_id, warning.message_id, 5))

            return True # Stop here, we handled the media
        except Exception as e:
            logger.error(f"Error handling media: {e}")
            return True # Still stop processing
            
    return False # No media found, continue to text checks

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


# 🟢 2. FIXED MAIN HANDLER
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages (Text and Captions)"""
    if not update.message or not update.effective_user:
        return
    
    user = update.effective_user
    message = update.message
    
    # Initialize user in DB
    db.initialize_user(user.id, user.username or "Unknown")
    
    # 🔴 RESTORED: Admin Check
    # This prevents the bot from blocking YOU
    if await is_admin(update, context):
        return

    # 🔴 NEW: Check Media FIRST (Before checking for text)
    # This fixes the bug where photos without captions were allowed
    if await check_media(update, context):
        return

    # Now get text content for links/bad words
    message_text = message.text or message.caption or ""
    
    # If no text (and wasn't a photo/video caught above), stop
    if not message_text:
        return

    message_text_lower = message_text.lower()
    
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
        cleaned_message = normalize_text(message_text_lower)
        
        for banned_word in banned_words:
            if banned_word in message_text_lower or banned_word in cleaned_message:
                found_banned_words.append(banned_word)
        
        if found_banned_words:
            try:
                await message.delete()
                await handle_punishment(update, context, user, "ارسال کلمات نامناسب")
                await log_spam_event(user.id, user.username or "Unknown", "banned_word", message_text[:100], message.chat_id)
                return
            except Exception as e:
                logger.error(f"Error handling bad word: {e}")