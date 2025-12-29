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
    """Handle /warn command - Warn a user (Admin only)"""
    if not update.message or not update.effective_user:
        return
    
    # Check admin permissions
    if not await is_admin(update, context):
        await update.message.reply_text("❌ فقط مدیران می‌تواند از این دستور استفاده کنند.")
        return
    
    # Check if replying to a message
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("⚠️ لطفاً به پیام کاربر پاسخ دهید.")
        return
    
    target_user = update.message.reply_to_message.from_user
    admin = update.effective_user
    
    # Add warning to database
    new_warn_count = db.add_warn(target_user.id)
    
    if new_warn_count is None:
        await update.message.reply_text("❌ خطا در اضافه کردن اخطار.")
        return
    
    logger.info(f"کاربر {target_user.id} توسط {admin.id} اخطار داده شد. تعداد اخطار: {new_warn_count}")
    
    # Send warning message
    if new_warn_count >= 3:
        # Mute the user
        try:
            await context.bot.restrict_chat_member(
                chat_id=update.message.chat_id,
                user_id=target_user.id,
                permissions=ChatPermissions(can_send_messages=False)
            )
            
            warning_msg = f"""🚫 کاربر {target_user.mention_html()} مسدود شد!

📊 اخطار: {new_warn_count}/3
💬 دلیل: اخطار‌های متعدد"""
        except Exception as e:
            logger.error(f"خطا در مسدود کردن کاربر: {e}")
            warning_msg = f"""⚠️ اخطار برای {target_user.mention_html()}

📊 اخطار: {new_warn_count}/3
🚨 شما مسدود شدید!"""
    else:
        warning_msg = f"""⚠️ اخطار برای {target_user.mention_html()}

📊 اخطار: {new_warn_count}/3
⏰ {3 - new_warn_count} اخطار باقی‌مانده تا مسدود شدن"""
    
    # Send warning and schedule deletion
    response = await update.message.reply_text(warning_msg, parse_mode="HTML")
    
    # Delete messages after 5 seconds
    context.job_queue.run_once(
        lambda ctx: delete_messages(ctx, update.message.chat_id, response.message_id, update.message.message_id),
        when=5,
        name=f"delete_warn_{response.message_id}"
    )


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ban command - Ban a user (Admin only)"""
    if not update.message or not update.effective_user:
        return
    
    # Check admin permissions
    if not await is_admin(update, context):
        await update.message.reply_text("❌ فقط مدیران می‌تواند از این دستور استفاده کنند.")
        return
    
    # Check if replying to a message
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("⚠️ لطفاً به پیام کاربر پاسخ دهید.")
        return
    
    target_user = update.message.reply_to_message.from_user
    
    try:
        # Ban the user
        await context.bot.ban_chat_member(
            chat_id=update.message.chat_id,
            user_id=target_user.id
        )
        
        ban_msg = f"""🚫 کاربر {target_user.mention_html()} از گروه حذف شد.

⚠️ این کاربر دیگر نمی‌تواند به گروه برگردد."""
        
        logger.info(f"کاربر {target_user.id} توسط {update.effective_user.id} بن شد")
        
    except Exception as e:
        logger.error(f"خطا در بن کردن کاربر: {e}")
        ban_msg = "❌ خطا در بن کردن کاربر."
    
    # Send message and schedule deletion
    response = await update.message.reply_text(ban_msg, parse_mode="HTML")
    
    # Delete messages after 5 seconds
    context.job_queue.run_once(
        lambda ctx: delete_messages(ctx, update.message.chat_id, response.message_id, update.message.message_id),
        when=5,
        name=f"delete_ban_{response.message_id}"
    )


async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unmute command - Remove restrictions (Admin only)"""
    if not update.message or not update.effective_user:
        return
    
    # Check admin permissions
    if not await is_admin(update, context):
        await update.message.reply_text("❌ فقط مدیران می‌تواند از این دستور استفاده کنند.")
        return
    
    # Check if replying to a message
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("⚠️ لطفاً به پیام کاربر پاسخ دهید.")
        return
    
    target_user = update.message.reply_to_message.from_user
    
    try:
        # Unmute the user
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
        
        unmute_msg = f"""🔊 کاربر {target_user.mention_html()} باز شد.

✅ کاربر می‌تواند دوباره پیام بفرستد."""
        
        logger.info(f"کاربر {target_user.id} توسط {update.effective_user.id} باز شد")
        
    except Exception as e:
        logger.error(f"خطا در باز کردن کاربر: {e}")
        unmute_msg = "❌ خطا در باز کردن کاربر."
    
    # Send message and schedule deletion
    response = await update.message.reply_text(unmute_msg, parse_mode="HTML")
    
    # Delete messages after 5 seconds
    context.job_queue.run_once(
        lambda ctx: delete_messages(ctx, update.message.chat_id, response.message_id, update.message.message_id),
        when=5,
        name=f"delete_unmute_{response.message_id}"
    )


async def addword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /addword command - Add a banned word (Admin only)"""
    if not update.message or not update.effective_user:
        return
    
    # Check admin permissions
    if not await is_admin(update, context):
        await update.message.reply_text("❌ فقط مدیران می‌تواند از این دستور استفاده کنند.")
        return
    
    # Check if word is provided
    if not context.args or len(context.args) == 0:
        await update.message.reply_text("⚠️ لطفاً یک کلمه برای بن کردن وارد کنید.\n\nمثال: /addword تبلیغ")
        return
    
    word = " ".join(context.args).strip()
    
    if len(word) == 0:
        await update.message.reply_text("⚠️ کلمه نمی‌تواند خالی باشد.")
        return
    
    # Add word to database
    result = db.add_banned_word(word)
    
    if result is None:
        response_msg = "⚠️ این کلمه قبلاً در لیست سیاه بوده است."
    else:
        response_msg = f"✅ کلمه '{word}' به لیست سیاه اضافه شد."
        logger.info(f"کلمه '{word}' توسط {update.effective_user.id} اضافه شد")
    
    # Send message and schedule deletion
    response = await update.message.reply_text(response_msg)
    
    # Delete messages after 5 seconds
    context.job_queue.run_once(
        lambda ctx: delete_messages(ctx, update.message.chat_id, response.message_id, update.message.message_id),
        when=5,
        name=f"delete_addword_{response.message_id}"
    )
