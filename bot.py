import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import re
import os
from flask import Flask, request
import asyncio

# --- Configuration ---
TOKEN = os.environ.get('TOKEN')
PORT = int(os.environ.get('PORT', '8443'))
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Bot Functions ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    await update.message.reply_text(
        "Hi! Send me a link to a video, and I'll try to download it for you."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message when the /help command is issued."""
    await update.message.reply_text("Just send me a video link. That's it!")

def get_video_url(url: str) -> str | None:
    """
    Uses yt-dlp to extract the direct video URL.
    """
    try:
        ydl_opts = {
            'format': 'best',  # Get the best quality
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # The 'url' key usually holds the direct video link
            return info.get('url')
    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles non-command messages (i.e., the video links)."""
    message_text = update.message.text
    
    # Simple regex to find the first URL in the message
    url_match = re.search(r'https?://[^\s]+', message_text)
    
    if not url_match:
        await update.message.reply_text("I didn't find a URL in your message. Please send a valid link.")
        return

    url = url_match.group(0)
    
    # Notify the user that processing has started
    await update.message.reply_text("Got it! Fetching the video, please wait...")

    # Get the direct video link
    video_url = await context.application.create_task(get_video_url(url))

    if video_url:
        try:
            # Send the video by passing the direct URL
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=video_url,
                caption="Here's your video!"
            )
        except Exception as e:
            logger.error(f"Telegram send_video error: {e}")
            await update.message.reply_text(
                "Sorry, I found the video but failed to send it. "
                "The file might be too large for Telegram (max 50MB for bots by URL)."
            )
    else:
        await update.message.reply_text(
            "Sorry, I couldn't get a downloadable link for that video."
        )

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # on non-command i.e message - handle the message
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Set up the webhook
    async def setup():
        await application.bot.set_webhook(url=WEBHOOK_URL)

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting...")
    
    app = Flask(__name__)

    @app.route('/webhook', methods=['POST'])
    def webhook():
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.run(application.process_update(update))
        return 'ok'

    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup())

    app.run(host='0.0.0.0', port=PORT)


if __name__ == "__main__":
    main()