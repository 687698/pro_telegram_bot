"""
Command handlers for the Telegram bot (Persian/Farsi)
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from src.database import db

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - Welcome message in Persian"""
    try:
        if not update.message or not update.effective_user:
            logger.warning("No message or user in /start command")
            return
        
        user = update.effective_user
        logger.info(f"🔔 /start command received from user {user.id} ({user.first_name})")
        
        # Initialize user in database
        db.initialize_user(user.id, user.username or "Unknown")
        
        welcome_message = f"""👋 سلام {user.first_name}!

خوش آمدید به گروه ما! 🎉

این بات برای مدیریت و نظارت بر گروه طراحی شده است.
من می‌توانم:
✅ کاربران را اخطار دهم
✅ کاربران مزاحم را مسدود کنم
✅ کلمات ممنوع را فیلتر کنم
✅ آمار و اطلاعات را نمایش دهم

برای دیدن دستورات بیشتر، /help را بزنید."""
        
        await update.message.reply_text(welcome_message)
        logger.info(f"✅ /start response sent to user {user.id}")
    except Exception as e:
        logger.error(f"❌ Error in /start command: {e}", exc_info=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command - Show help in Persian"""
    try:
        if not update.message:
            return
        
        logger.info(f"🔔 /help command received from user {update.effective_user.id}")
        
        help_text = """📖 راهنما - دستورات دستیار

👥 دستورات عمومی:
/start - شروع
/stats - مشاهده اخطارات شما

⚙️ دستورات مدیران (فقط برای ادمین‌ها):
/warn - اخطار دادن به کاربر
/ban - مسدود کردن کاربر
/unmute - باز کردن سکوت
/addword [کلمه] - اضافه کردن کلمه ممنوع

مثال:
/addword تبلیغ"""
        
        await update.message.reply_text(help_text)
        logger.info(f"✅ /help response sent to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"❌ Error in /help command: {e}", exc_info=True)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - Show user statistics in Persian"""
    try:
        if not update.message or not update.effective_user:
            return
        
        user = update.effective_user
        logger.info(f"🔔 /stats command received from user {user.id}")
        
        user_stats = db.get_user_stats(user.id)
        
        if not user_stats:
            response = "⚠️ اطلاعات شما در سیستم ثبت نشده است."
        else:
            warn_count = user_stats.get("warn_count", 0)
            
            if warn_count == 0:
                status = "✅ شما هیچ اخطاری ندارید!"
            elif warn_count < 3:
                remaining = 3 - warn_count
                status = f"⚠️ شما {warn_count} اخطار دارید. ({remaining} اخطار باقی‌مانده تا مسدود شدن)"
            else:
                status = "🚫 شما مسدود شده‌اید!"
            
            response = f"""📊 آمار شما:

👤 نام: {user.first_name}
🆔 شناسه: {user.id}
⚠️ تعداد اخطار: {warn_count}
{status}"""
        
        await update.message.reply_text(response)
        logger.info(f"✅ /stats response sent to user {user.id}")
    except Exception as e:
        logger.error(f"❌ Error in /stats command: {e}", exc_info=True)
