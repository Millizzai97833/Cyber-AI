import os
import logging
import aiohttp
import urllib.parse
from datetime import date
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-4o-mini"

client = OpenAI(api_key=OPENAI_API_KEY)

# Daily image limit
DAILY_IMAGE_LIMIT = 8
user_daily_count = defaultdict(int)
user_last_reset = {}

SYSTEM_PROMPT = """
You are ShadowGuard, an elite Cyber Security Expert and Telegram Bot.
You also have free AI image generation (NSFW allowed).

Rules:
- Only defensive cyber security. Never give offensive hacking, cracking, or illegal methods.
- For images tell users to use /image or /gen.
- Keep replies short, sharp, and dark-hacker style.
- Start new chats with: [ShadowGuard Online] Ready. What do you need secured?
"""

conversations = {}
logging.basicConfig(level=logging.INFO)

def check_daily_limit(user_id: int) -> bool:
    today = date.today()
    if user_last_reset.get(user_id) != today:
        user_daily_count[user_id] = 0
        user_last_reset[user_id] = today
    return user_daily_count[user_id] < DAILY_IMAGE_LIMIT

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    conversations[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    await update.message.reply_text(
        "[ShadowGuard Online]\n"
        "Cyber Security Expert + Free AI Image Maker\n\n"
        "Commands:\n"
        "/image <prompt>  → Generate image (NSFW allowed)\n"
        "/gen <prompt>    → Same as /image\n"
        "/limit           → Check remaining images today\n\n"
        f"Daily free limit: {DAILY_IMAGE_LIMIT} images\n"
        "Ready. What do you need secured?"
    )

async def check_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    remaining = DAILY_IMAGE_LIMIT - user_daily_count[user_id]
    await update.message.reply_text(f"Images remaining today: {remaining}/{DAILY_IMAGE_LIMIT}")

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prompt = " ".join(context.args)

    if not prompt:
        await update.message.reply_text("Usage:\n/image your prompt here\nExample: /image cyberpunk girl neon lights, detailed, nsfw")
        return

    if not check_daily_limit(user_id):
        await update.message.reply_text(f"Daily limit reached ({DAILY_IMAGE_LIMIT}). Come back tomorrow.")
        return

    await update.message.reply_text("Generating image... please wait.")

    encoded_prompt = urllib.parse.quote(prompt)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&enhance=true"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, timeout=60) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    await update.message.reply_photo(photo=image_data, caption=f"Prompt: {prompt}")
                    user_daily_count[user_id] += 1
                else:
                    await update.message.reply_text("Generation failed. Try again later.")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_message = update.message.text

    if chat_id not in conversations:
        conversations[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    conversations[chat_id].append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=conversations[chat_id],
            temperature=0.7,
            max_tokens=800
        )
        reply = response.choices[0].message.content
        conversations[chat_id].append({"role": "assistant", "content": reply})

        if len(conversations[chat_id]) > 16:
            conversations[chat_id] = [conversations[chat_id][0]] + conversations[chat_id][-8:]

        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"[Error] {str(e)}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("limit", check_limit))
    app.add_handler(CommandHandler("image", generate_image))
    app.add_handler(CommandHandler("gen", generate_image))
    app.add_handler(MessageHandler(filters.TEXT & \~filters.COMMAND, handle_message
