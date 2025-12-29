"""
Moderation handlers for group administration (Persian/Farsi)
"""

import logging
from telegram import Update, ChatMember, ChatPermissions
from telegram.ext import ContextTypes
from src.database import db

logger = logging.getLogger(__name__)


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user is a group administrator"""
    if not update.message or not update.effective_user:
        return False
    
    try:
        # Get user status in the chat
        user_status = await update.message.chat.get_member(update.effective_user.id)
        
        # Check if user is admin or owner (CREATOR is deprecated, use OWNER)
        # We check for both to be safe
        admin_statuses = [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        
        # Fallback for older versions that might still use CREATOR
        if hasattr(ChatMember, 'CREATOR'):
            admin_statuses.append(ChatMember.CREATOR)
        
        return user_status.status in admin_statuses
    except Exception as e:
        logger.error(f"خطا در بررسی دسترسی ادمین: {e}")
        return False


async def delete_messages(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, admin_message_id: int = None):
    """Delete bot and admin messages after 5 seconds"""
    try:
        # Delete bot's response message
        await context.bot.delete_message(chat_id, message_id)
        
        # Delete admin's command message if provided
        if admin_message_id:
            await context.bot.delete_message(chat_id, admin_message_id)
    except Exception as e:
        logger.warning(f"خطا در حذف پیام: {e}")


async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /warn command - Warn a user (Flash Mode)"""
    if not update.message or not update.effective_user:
        return
    
    # Check admin permissions
    if not await is_admin(update, context):
        return

    # 1. Delete Admin's Command IMMEDIATELY
    try:
        await update.message.delete()
    except Exception:
        pass
    
    # Check if replying to a message
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        # Send error, delete after 3s
        msg = await context.bot.send_message(chat_id=update.message.chat_id, text="⚠️ لطفاً به پیام کاربر پاسخ دهید.")
        context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(update.message.chat_id, msg.message_id), when=3)
        return
    
    target_user = update.message.reply_to_message.from_user
    
    # Add warning to database
    new_warn_count = db.add_warn(target_user.id)
    
    if new_warn_count is None:
        return

    # Prepare Message
    if new_warn_count >= 3:
        # Mute the user
        try:
            await context.bot.restrict_chat_member(
                chat_id=update.message.chat_id,
                user_id=target_user.id,
                permissions=ChatPermissions(can_send_messages=False)
            )
            warning_msg = f"🚫 کاربر {target_user.mention_html()} به دلیل دریافت ۳ اخطار مسدود شد!"
        except Exception:
            warning_msg = f"🚫 اخطار سوم برای {target_user.mention_html()} (خطا در مسدود سازی)"
    else:
        warning_msg = f"⚠️ اخطار برای {target_user.mention_html()}\n📊 تعداد: {new_warn_count}/3"
    
    # 2. Send Warning
    response = await context.bot.send_message(
        chat_id=update.message.chat_id,
        text=warning_msg,
        parse_mode="HTML"
    )
    
    # 3. Delete Warning after 10 SECONDS (Give them time to read it)
    context.job_queue.run_once(
        lambda ctx: ctx.bot.delete_message(update.message.chat_id, response.message_id),
        when=10, 
        name=f"del_warn_{response.message_id}"
    )


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ban command - Ban a user (Flash Mode)"""
    if not update.message or not update.effective_user:
        return
    
    if not await is_admin(update, context):
        return

    # 1. Delete Admin's Command
    try:
        await update.message.delete()
    except Exception:
        pass
    
    if not update.message.reply_to_message:
        msg = await context.bot.send_message(chat_id=update.message.chat_id, text="⚠️ لطفاً به پیام کاربر پاسخ دهید.")
        context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(update.message.chat_id, msg.message_id), when=3)
        return
    
    target_user = update.message.reply_to_message.from_user
    
    try:
        await context.bot.ban_chat_member(chat_id=update.message.chat_id, user_id=target_user.id)
        ban_msg = f"🚫 کاربر {target_user.mention_html()} از گروه اخراج شد."
    except Exception as e:
        ban_msg = "❌ خطا در بن کردن کاربر."
    
    # 2. Send Confirmation
    response = await context.bot.send_message(chat_id=update.message.chat_id, text=ban_msg, parse_mode="HTML")
    
    # 3. Delete Confirmation after 5 seconds
    context.job_queue.run_once(
        lambda ctx: ctx.bot.delete_message(update.message.chat_id, response.message_id),
        when=5,
        name=f"del_ban_{response.message_id}"
    )


async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unmute command - Unmute a user (Flash Mode)"""
    if not update.message or not update.effective_user:
        return
    
    if not await is_admin(update, context):
        return

    # 1. Delete Admin's Command
    try:
        await update.message.delete()
    except Exception:
        pass
    
    if not update.message.reply_to_message:
        return # Just ignore if no reply
    
    target_user = update.message.reply_to_message.from_user
    
    try:
        await context.bot.restrict_chat_member(
            chat_id=update.message.chat_id,
            user_id=target_user.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_add_web_page_previews=True
            )
        )
        msg_text = f"🔊 کاربر {target_user.mention_html()} آزاد شد."
    except Exception:
        msg_text = "❌ خطا در آزاد کردن کاربر."
    
    # 2. Send Confirmation
    response = await context.bot.send_message(chat_id=update.message.chat_id, text=msg_text, parse_mode="HTML")
    
    # 3. Delete Confirmation after 5 seconds
    context.job_queue.run_once(
        lambda ctx: ctx.bot.delete_message(update.message.chat_id, response.message_id),
        when=5,
        name=f"del_unmute_{response.message_id}"
    )


async def addword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /addword command - Add a banned word (Flash Mode)"""
    if not update.message or not update.effective_user:
        return
    
    # Check admin permissions
    if not await is_admin(update, context):
        return
    
    # 1. Delete the command message IMMEDIATELY
    try:
        await update.message.delete()
    except Exception:
        pass

    # Check if word is provided
    if not context.args or len(context.args) == 0:
        msg = await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="⚠️ لطفاً کلمه را وارد کنید. (مثال: /addword تبلیغ)"
        )
        # Delete error after 3 seconds
        context.job_queue.run_once(
            lambda ctx: ctx.bot.delete_message(update.message.chat_id, msg.message_id),
            when=3, name=f"del_{msg.message_id}"
        )
        return
    
    word = " ".join(context.args).strip()
    
    # Add to DB
    result = db.add_banned_word(word)
    
    if result is None:
        text = f"⚠️ کلمه '{word}' قبلاً وجود داشت."
    else:
        text = f"✅ کلمه '{word}' اضافه شد."
        logger.info(f"کلمه '{word}' توسط {update.effective_user.id} اضافه شد")
    
    # 2. Send Confirmation
    response = await context.bot.send_message(
        chat_id=update.message.chat_id,
        text=text
    )
    
    # 3. Delete Confirmation after 2 SECONDS (Flash)
    context.job_queue.run_once(
        lambda ctx: ctx.bot.delete_message(update.message.chat_id, response.message_id),
        when=2, # <--- Disappears very fast
        name=f"del_{response.message_id}"
    )