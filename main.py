import os
import re
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.constants import MessageEntityType
from telegram.ext import Application, MessageHandler, ContextTypes, filters

# ১. বট টোকেন (Render-এ Environment Variable হিসেবে BOT_TOKEN সেট করুন)
TOKEN = os.getenv("BOT_TOKEN", "8781582257:AAFiv9liUbPvFCUkARJNqEKOxFmuBGs-uI8")

# ২. ফিল্টারিং রেগুলার এক্সপ্রেশন (Regex)
LINK_REGEX = r'(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+|wa\.me/\S+|\b\w+\.(com|net|org|xyz|io|me|info|site|online|shop|live|app|top|link|bd|in|club|vip)\b)'
MENTION_REGEX = r'@[a-zA-Z0-9_]+'

# ইনবক্স, ডিএম, পিএম, আইবি (বাংলা, ইংরেজি ও বাংলিশ প্যাটার্ন)
INBOX_REGEX = r'(?i)\b(inbox|inboxe|inbx|dm|pm|pvt|privet|private|ib)\b|ইনবক্স|ইনবক্সে|আইবি|আইবিতে|ডিএম|পিএম|পার্সোনাল|পার্সোনালে|মেসেজ\s*(দিন|দেন|করো|করুন)|ইনবক্স\s*(করুন|করো|এ\s*আসুন)'

# ৩. Render-এ ২৪/৭ চালু রাখার জন্য Flask সার্ভার
server = Flask(__name__)

@server.route('/')
def home():
    return "Bot Server is Active 24/7!"

@server.route('/health')
def health():
    return "OK", 200

def keep_alive():
    def run():
        port = int(os.environ.get("PORT", 8080))
        server.run(host="0.0.0.0", port=port)
    t = threading.Thread(target=run, daemon=True)
    t.start()

# ৪. সদস্যপদ যাচাই ফাংশন
async def is_member(bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator', 'restricted']
    except Exception as e:
        print(f"Member check error for chat {chat_id}: {e}")
        return False

# ৫. ডিলিটযোগ্য সতর্কবার্তা পাঠানোর ফাংশন
async def send_auto_delete_warning(bot, chat_id, thread_id, text, delay=7):
    try:
        sent = await bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=text
        )
        await asyncio.sleep(delay)
        await bot.delete_message(chat_id=chat_id, message_id=sent.message_id)
    except Exception:
        pass

# ৬. নতুন মেম্বার জয়েন হলে স্বাগতম মেসেজ
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.new_chat_members:
        return

    for user in msg.new_chat_members:
        if user.id == context.bot.id:
            continue
        try:
            await msg.reply_text(
                f"👋 স্বাগতম {user.first_name}!\n🌸 আমাদের পরিবারে আপনাকে স্বাগতম।"
            )
        except Exception as e:
            print(f"Welcome Error: {e}")

# ৭. মেসেজ, কমেন্ট ও ইনবক্স ফিল্টারিং
async def filter_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # চ্যানেলের মূল পোস্ট অটো-ফরোয়ার্ড হলে এড়িয়ে যাবে
    if msg.is_automatic_forward:
        return

    chat_id = update.effective_chat.id
    thread_id = msg.message_thread_id if msg.is_topic_message else None

    # লিঙ্কড চ্যানেল আইডি খোঁজা
    linked_channel_id = None
    try:
        chat_info = await context.bot.get_chat(chat_id)
        linked_channel_id = chat_info.linked_chat_id
    except Exception:
        pass

    # অ্যাডমিন যদি চ্যানেল বা অ্যানোনিমাস প্রোফাইল দিয়ে মেসেজ দেয়
    if msg.sender_chat:
        if msg.sender_chat.id == chat_id or (linked_channel_id and msg.sender_chat.id == linked_channel_id):
            return  # মূল চ্যানেল/গ্রুপের নিজস্ব পোস্ট
        
        # বাইরের অন্য চ্যানেল প্রোফাইল দিয়ে মেসেজ করলে ডিলিট
        try:
            await msg.delete()
        except Exception:
            pass
        return

    user = msg.from_user
    if not user or user.is_bot:
        return

    # ==================== অ্যাডমিন ও ওনার বাইপাস ====================
    # ১. গ্রুপ অ্যাডমিন কিনা চেক
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user.id)
        if chat_member.status in ['administrator', 'creator']:
            return
    except Exception:
        pass

    # ২. চ্যানেল অ্যাডমিন কিনা চেক
    if linked_channel_id:
        try:
            channel_member = await context.bot.get_chat_member(linked_channel_id, user.id)
            if channel_member.status in ['administrator', 'creator']:
                return
        except Exception:
            pass
    # ==============================================================

    # ==================== সাধারণ মেম্বার চেক ====================
    # ১. মূল চ্যানেলে জয়েন আছে কি না যাচাই করা
    if linked_channel_id:
        in_channel = await is_member(context.bot, linked_channel_id, user.id)
        if not in_channel:
            try:
                await msg.delete()
                warning = (
                    f"⚠️ দুঃখিত {user.first_name}!\n\n"
                    f"এখানে কমেন্ট করতে হলে আপনাকে আমাদের মূল চ্যানেলে জয়েন থাকতে হবে।"
                )
                asyncio.create_task(send_auto_delete_warning(context.bot, chat_id, thread_id, warning))
            except Exception as e:
                print(f"Channel membership delete error: {e}")
            return

    # ২. লিংক ও @ মেনশন চেক
    text = msg.text or msg.caption or ""
    entities = (msg.entities or ()) + (msg.caption_entities or ())

    has_link = bool(re.search(LINK_REGEX, text, re.IGNORECASE))
    has_mention = bool(re.search(MENTION_REGEX, text))

    for entity in entities:
        if entity.type in [MessageEntityType.MENTION, MessageEntityType.TEXT_MENTION]:
            has_mention = True
        elif entity.type in [MessageEntityType.URL, MessageEntityType.TEXT_LINK]:
            has_link = True

    # মেনশন ডিলিট
    if has_mention:
        try:
            await msg.delete()
            warning = f"🚫 দুঃখিত {user.first_name}! এখানে `@` দিয়ে মেনশন করা নিষেধ।"
            asyncio.create_task(send_auto_delete_warning(context.bot, chat_id, thread_id, warning))
            return
        except Exception as e:
            print(f"Mention Delete Error: {e}")

    # লিংক ডিলিট
    if has_link:
        try:
            await msg.delete()
            warning = f"🚫 দুঃখিত {user.first_name}! এখানে যেকোনো ধরণের লিংক শেয়ার করা নিষেধ।"
            asyncio.create_task(send_auto_delete_warning(context.bot, chat_id, thread_id, warning))
            return
        except Exception as e:
            print(f"Link Delete Error: {e}")

    # ৩. ইনবক্স সতর্কবার্তা চেক (Inbox / DM / PM / IB / ইনবক্স ইত্যাদি)
    if re.search(INBOX_REGEX, text):
        try:
            warning_msg = "⚠️ সতর্কতা: Inbox-এ লেনদেন বা কথাবার্তার ক্ষেত্রে সবাই সতর্ক থাকুন। কেউ কাউকে ঠকালে তার দায়ভার গ্রুপ কর্তৃপক্ষ নেবে না। 🚫"
            await msg.reply_text(warning_msg)
        except Exception as e:
            print(f"Inbox warning error: {e}")

def main():
    # Flask সার্ভার চালু করা
    keep_alive()
    print("Bot is starting...")

    app = Application.builder().token(TOKEN).build()

    # মেম্বার জয়েন হ্যান্ডলার
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # সকল মেসেজ ফিল্টার হ্যান্ডলার
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, filter_messages))

    print("Bot is successfully running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
