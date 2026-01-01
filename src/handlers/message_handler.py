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

# 🟢 MEMORY: Stores {MessageID : Data} for Approval System
PENDING_APPROVALS = {}

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

async def log_spam_event(user_id: int, username: str, spam_type: str, content: str, chat_id: int):
    """Log spam events to the console (Restored!)"""
    try:
        logger.warning(f"🚨 Spam: {spam_type} | User: {username}({user_id}) | Content: {content}")
    except Exception:
        pass

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
        msg_text = f"🚫 {user_mention} عزیز، {reason} مجاز نیست.\n⚠️ اخطار: {new_warn_count}/3"

    warning = await context.bot.send_message(chat_id=update.message.chat_id, text=msg_text, parse_mode="HTML")
    asyncio.create_task(delete_later(context.bot, update.message.chat_id, warning.message_id, 5))

# ==================== LOGIC: TEXT CLEANING & CHECKING ====================

def normalize_text(text: str) -> str:
    """
    NUCLEAR CLEANING: Removes ALL symbols to catch hidden words.
    Input: "ع /// نننن ... ت،،، ر"
    Output: "عنتر"
    """
    if not text: return ""
    
    # 1. Remove everything that is NOT a letter or number (Persian & English)
    # This strips spaces, dots, commas, slashes, emojis, etc.
    clean = re.sub(r'[^\w\d\u0600-\u06FF]', '', text)
    
    # 2. Remove underscores (often used as spacers like "b_a_d")
    clean = clean.replace('_', '')
    
    # 3. Deduplicate (remove repeating characters)
    # "nnnoooo" -> "no"
    clean = re.sub(r'(.)\1+', r'\1', clean)
    
    return clean.lower()

def has_link(message) -> bool:
    """
    Checks for links including obfuscated ones like "see /// x ... c oooomm"
    """
    # 1. Check Telegram Entities (Best for clickable links)
    entities = message.entities or []
    caption_entities = message.caption_entities or []
    all_entities = list(entities) + list(caption_entities)
    for entity in all_entities:
        if entity.type in [MessageEntity.URL, MessageEntity.TEXT_LINK]:
            return True

    text_content = message.text or message.caption or ""
    text_lower = text_content.lower()

    # 2. Check Standard Keywords
    url_keywords = ['http://', 'https://', 'www.', '.com', '.ir', '.net', '.org', 't.me', 'bit.ly']
    for keyword in url_keywords:
        if keyword in text_lower: return True

    # 3. ADVANCED SKELETON CHECK
    # Clean the text using the same "Nuclear" logic as banned words
    # Input: "see /// x ... c oooomm" -> "seexcom"
    skeleton = re.sub(r'[^a-z]+', '', text_lower) # Keep only English letters
    skeleton_clean = re.sub(r'(.)\1+', r'\1', skeleton) # Deduplicate
    
    # Signatures
    extensions = ['com', 'ir', 'net', 'org', 'xyz', 'tk', 'info', 'io', 'me', 'site']
    common_sites = ['google', 'youtube', 'instagram', 'telegram', 'whatsapp', 'sex', 'porn', 'xxx']
    prefixes = ['http', 'https', 'www', 'tme']

    # A. Check Known Sites (Strongest)
    for site in common_sites:
        for ext in extensions:
            if site + ext in skeleton_clean: return True # Matches "youtubecom", "sexcom"

    # B. Check Prefixes
    for p in prefixes:
        if p in skeleton_clean: return True # Matches "www..." or "http..."

    # C. Check "Suspicious Extension"
    # If the text has symbols like / or . or , AND ends with a known extension
    has_symbols = bool(re.search(r'[\./,\\_]', text_lower))
    if has_symbols:
        for ext in extensions:
            # Check if skeleton ends with extension (e.g. "blabla...com")
            if skeleton_clean.endswith(ext):
                # Ensure it's not just the extension itself (length check > 3)
                if len(skeleton_clean) > len(ext) + 2:
                    return True

    return False

# ==================== HANDLER 1: APPROVAL LOGIC ====================

async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reply 'تایید' or 'رد' to admin DMs."""
    # 🔴 REPLACE WITH YOUR ID
    OWNER_ID = 2117254740 
    
    if update.effective_user.id != OWNER_ID: return
    if not update.message.reply_to_message: return

    target_msg_id = update.message.reply_to_message.message_id
    data = PENDING_APPROVALS.get(target_msg_id)

    if not data:
        await update.message.reply_text("⚠️ پیام یافت نشد.")
        return

    group_id = data['chat_id']
    user_id = data['user_id']
    command = update.message.text

    try:
        if command == "تایید":
            await update.message.reply_to_message.copy(
                chat_id=group_id,
                caption=f"✅ <b>تایید شد</b>\nتوسط مدیر گروه.",
                parse_mode="HTML"
            )
            await update.message.reply_text("✅ ارسال شد.")
            
        elif command == "رد":
            try:
                member = await context.bot.get_chat_member(group_id, user_id)
                user_mention = member.user.mention_html()
            except:
                user_mention = "کاربر"
            
            reject_msg = f"❌ مدیا ارسالی توسط {user_mention} **تایید نشد**."
            msg = await context.bot.send_message(chat_id=group_id, text=reject_msg, parse_mode="HTML")
            asyncio.create_task(delete_later(context.bot, group_id, msg.message_id, 10))
            await update.message.reply_text("❌ رد شد.")

        del PENDING_APPROVALS[target_msg_id]
    except Exception as e:
        logger.error(f"Approval error: {e}")

# ==================== HANDLER 2: MEDIA (Photos & Videos) ====================

async def check_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user: return
    if await is_admin(update, context): return

    try:
        # 🔴 REPLACE WITH YOUR ID
        OWNER_ID = 2117254740
        try:
            forwarded_msg = await update.message.forward(chat_id=OWNER_ID)
            PENDING_APPROVALS[forwarded_msg.message_id] = {
                'chat_id': update.message.chat_id,
                'user_id': update.effective_user.id
            }
            await context.bot.send_message(chat_id=OWNER_ID, text=f"📩 مدیا برای بررسی:\nتایید / رد")
        except Exception: pass 

        await update.message.delete()
        msg_text = f"🔒 {update.effective_user.mention_html()} عزیز، فایل شما برای بررسی ارسال شد."
        warning = await context.bot.send_message(chat_id=update.message.chat_id, text=msg_text, parse_mode="HTML")
        asyncio.create_task(delete_later(context.bot, update.message.chat_id, warning.message_id, 5))
    except Exception as e:
        logger.error(f"Media error: {e}")

# ==================== HANDLER 3: TEXT (Links & Bad Words) ====================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user: return
    
    user = update.effective_user
    message = update.message
    db.initialize_user(user.id, user.username or "Unknown")
    
    if await is_admin(update, context): return

    message_text = message.text or message.caption or ""
    if not message_text:
        return # No text to check
        
    message_text_lower = message_text.lower()
    
    # 1. Check Links
    if has_link(message):
        try:
            await message.delete()
            await handle_punishment(update, context, user, "ارسال لینک")
            # Log the spam event (Restored!)
            await log_spam_event(user.id, user.username or "Unknown", "link", message_text[:100], message.chat_id)
            return
        except Exception: pass
    
    # 2. Check Banned Words
    banned_words = db.get_banned_words()
    if banned_words:
        # Nuclear Clean
        cleaned_message = normalize_text(message_text_lower)
        
        found_banned = False
        found_word = ""
        
        for word in banned_words:
            # Check 1: Normal
            if word in message_text_lower:
                found_banned = True
                found_word = word
                break
            # Check 2: Nuclear Cleaned
            word_clean = normalize_text(word)
            if word_clean and word_clean in cleaned_message:
                found_banned = True
                found_word = word
                break
        
        if found_banned:
            try:
                await message.delete()
                await handle_punishment(update, context, user, "ارسال کلمات نامناسب")
                # Log the spam event (Restored!)
                await log_spam_event(user.id, user.username or "Unknown", "banned_word", found_word, message.chat_id)
                return
            except Exception: pass