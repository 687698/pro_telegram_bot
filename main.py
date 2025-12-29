"""
Entry point for Railway deployment
Starts the Telegram bot
"""

from src.bot import run_bot

if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Error: {e}")
