import os
import re
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN", "8781582257:AAFiv9liUbPvFCUkARJNqEKOxFmuBGs-uI8")

# লিংক ধরার ফিল্টার
LINK_REGEX = r'(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+|wa\.me/\S+|\b\w+\.(com|net|org|xyz|io|me|info|site|online|shop|live|app)\b)'

# ক্যাশ মেমরি (লিংক করা চ্যানেল মনে রাখার জন্য)
GROUP_CHANNEL_CACHE = {}

# ২৪ ঘণ্টা চালুর জন্য Flask সার্ভার
server = Flask(__name__)

@server.route('/')
def home():
    return "Bot is dynamically running 24/7!"

def keep_alive():
    def run():
        port = int(os.environ.get("PORT", 8080))
        server.run(host="0.0.0.0", port=port)
    threading.Thread(target=run, daemon=True).start()

# সদস্যপদ চেক ফাংশন
async def is_member(bot, chat_id, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator', 'restricted']:
            return True
        return False
    except Exception as e:
        print(f"মেম্বার চেক এরর ({chat_id}): {e}")
        return False

# নতুন জয়েন করাদের ওয়েলকাম মেসেজ
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        if user.id == context.bot.id:
            continue
        await update.message.reply_text(
            f"👋 স্বাগতম {user.first_name}!\n🌸 আমাদের গ্রুপ ও চ্যানেলে আপনাকে স্বাগতম।"
        )

# মেসেজ ও কমেন্ট ফিল্টারিং (সম্পূর্ণ অটোমেটিক)
async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # চ্যানেল থেকে আসা অটো-পোস্ট ডিলিট হবে না
    if msg.is_automatic_forward:
        return

    # কেউ অন্য চ্যানেলের নামে কমেন্ট করলে ডিলিট হবে
    if msg.sender_chat and not msg.from_user:
        try:
            await msg.delete()
        except:
            pass
        return

    user = msg.from_user
    chat_id = update.effective_chat.id
    text = msg.text or msg.caption or ""

    # এডমিনদের মেসেজ ফিল্টার হবে না
    try:
        chat_admin = await context.bot.get_chat_member(chat_id, user.id)
        if chat_admin.status in ['administrator', 'creator']:
            return
    except:
        pass

    # --- অটোমেটিকভাবে লিংক করা চ্যানেল খুঁজে বের করা ---
    linked_channel_id = GROUP_CHANNEL_CACHE.get(chat_id)
    if not linked_channel_id:
        try:
            chat_info = await context.bot.get_chat(chat_id)
            linked_channel_id = chat_info.linked_chat_id
            if linked_channel_id:
                GROUP_CHANNEL_CACHE[chat_id] = linked_channel_id
        except Exception as e:
            print(f"চ্যানেল লিংক ডিটেক্ট এরর: {e}")

    # ১. ইউজার গ্রুপ ও মূল চ্যানেল উভয়টিতে জয়েন আছে কিনা যাচাই
    in_group = await is_member(context.bot, chat_id, user.id)
    in_channel = True

    if linked_channel_id:
        in_channel = await is_member(context.bot, linked_channel_id, user.id)

    # যদি যেকোনো একটায় জয়েন না থাকে -> সাথে সাথে ডিলিট
    if not in_group or not in_channel:
        try:
            await msg.delete()
            warning_msg = (
                f"⚠️ দুঃখিত {user.first_name}!\n\n"
                f"এখানে কমেন্ট বা মেসেজ করতে হলে আপনাকে অবশ্যই আমাদের **চ্যানেল এবং গ্রুপ উভয়টিতে জয়েন থাকতে হবে**।\n\n"
                f"👉 দয়া করে উভয় জায়গায় জয়েন হয়ে পুনরায় চেষ্টা করুন।"
            )
            await context.bot.send_message(chat_id=chat_id, text=warning_msg)
            return
        except Exception as e:
            print(f"মেসেজ ডিলিট করতে সমস্যা: {e}")

    # ২. কোনো লিংক শেয়ার করলে সাথে সাথে ডিলিট
    if re.search(LINK_REGEX, text, re.IGNORECASE):
        try:
            await msg.delete()
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🚫 দুঃখিত {user.first_name}! এখানে যেকোনো ধরণের লিংক শেয়ার করা সম্পূর্ণ নিষেধ।"
            )
        except Exception as e:
            print(f"লিংক ডিলিট এরর: {e}")

def main():
    keep_alive()
    print("Bot is starting...")
    app = Application.builder().token(TOKEN).build()

    # মেম্বার জয়েন হ্যান্ডলার
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # মেসেজ ও কমেন্ট ফিল্টার হ্যান্ডলার
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, check_message))

    print("Bot is successfully running!")
    app.run_polling()

if __name__ == "__main__":
    main()
