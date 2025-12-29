"""
Entry point for Railway deployment
Starts the Telegram bot
"""

import asyncio
from src.bot import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Error: {e}")
