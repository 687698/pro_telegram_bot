"""
Entry point for Railway deployment
Starts the Telegram bot
"""

import logging
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=False)

# Setup logging before importing bot
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=os.getenv("LOG_LEVEL", "INFO")
)
logger = logging.getLogger(__name__)

logger.info("🚀 Starting bot from main.py...")

try:
    from src.bot import main
    logger.info("✅ Successfully imported main from src.bot")
    asyncio.run(main())
except ImportError as e:
    logger.error(f"❌ Import error: {e}", exc_info=True)
    raise
except KeyboardInterrupt:
    logger.info("❌ Bot stopped by user")
except Exception as e:
    logger.error(f"❌ خطای غیرمنتظره: {e}", exc_info=True)
    raise
