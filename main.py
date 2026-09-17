import os
import re
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

# ১. টোকেন ও চ্যানেল কনফিগারেশন
TOKEN = os.getenv("BOT_TOKEN", "8781582257:AAFiv9liUbPvFCUkARJNqEKOxFmuBGs-uI8")
MAIN_CHANNEL = "@your_channel_username"  # <-- আপনার চ্যানেলের ইউজারনেম দিন

LINK_REGEX = r'(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+|wa\.me/\S+|\b\w+\.(com|net|org|xyz|io|me|info|site|online|shop|live|app)\b)'

# ২. সার্ভার ২৪ ঘণ্টা চালু রাখার জন্য ডামি ওয়েব সার্ভার (Flask)
server = Flask(__name__)

@server.route('/')
def home():
    return "Bot is running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    server.run(host="0.0.0.0", port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()

# ৩. চ্যানেল জয়েন চেক ফাংশন
async def is_user_member(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=MAIN_CHANNEL, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator', 'restricted']:
            return True
        return False
    except Exception as e:
        print(f"চ্যানেল চেক করতে সমস্যা: {e}")
        return True

# ৪. ওয়েলকাম মেসেজ
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        if user.id == context.bot.id:
            continue
        name = user.first_name
        await update.message.reply_text(f"👋 স্বাগতম {name}!\n🌸 আমাদের গ্রুপে আপনাকে স্বাগতম!")

# ৫. লিংক ডিলিট ও মূল চ্যানেলে জয়েন চেক
async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    user = update.message.from_user
    chat_id = update.effective_chat.id
    text = update.message.text or update.message.caption or ""

    # এডমিন চেক
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user.id)
        if chat_member.status in ['administrator', 'creator']:
            return
    except:
        pass

    # চ্যানেল জয়েন চেক
    if MAIN_CHANNEL and MAIN_CHANNEL != "@your_channel_username":
        is_joined = await is_user_member(context, user.id)
        if not is_joined:
            try:
                await update.message.delete()
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ দুঃখিত {user.first_name}!\nএখানে মেসেজ করতে হলে মূল চ্যানেলে জয়েন থাকতে হবে।\n👉 জয়েন করুন: {MAIN_CHANNEL}"
                )
                return
            except Exception as e:
                print(f"মেসেজ ডিলিট এরর: {e}")

    # লিংক চেক
    if re.search(LINK_REGEX, text, re.IGNORECASE):
        try:
            await update.message.delete()
            await context.bot.send_message(
                chat_id=chat_id, 
                text=f"🚫 দুঃখিত {user.first_name}! এই গ্রুপে কোনো লিংক পাঠানো সম্পূর্ণ নিষেধ।"
            )
        except Exception as e:
            print(f"লিংক ডিলিট এরর: {e}")

def main():
    # Flask ওয়েব সার্ভার চালু করা
    keep_alive()

    print("Bot is starting...")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.StatusUpdate.ALL, check_message))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
