import os
import re
import threading
from flask import Flask
from telegram import Update
from telegram.constants import MessageEntityType
from telegram.ext import Application, MessageHandler, ContextTypes, filters

# ১. বট টোকেন
TOKEN = os.getenv("BOT_TOKEN", "8781582257:AAFiv9liUbPvFCUkARJNqEKOxFmuBGs-uI8")

# ২. লিংক এবং @ মেনশন ডিটেকশন রেগুলার এক্সপ্রেশন
LINK_REGEX = r'(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+|wa\.me/\S+|\b\w+\.(com|net|org|xyz|io|me|info|site|online|shop|live|app|top|link|bd|in|club|vip)\b)'
MENTION_REGEX = r'@[a-zA-Z0-9_]+'

# ৩. Render-এ ২৪ ঘণ্টা চালু রাখার জন্য Flask ওয়েব সার্ভার
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
async def is_member(bot, chat_id, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator', 'restricted']
    except Exception:
        return False

# ৫. নতুন মেম্বার আসলে স্বাগতম মেসেজ
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        if user.id == context.bot.id:
            continue
        try:
            await update.message.reply_text(
                f"👋 স্বাগতম {user.first_name}!\n🌸 আমাদের পরিবারে আপনাকে স্বাগতম।"
            )
        except Exception as e:
            print(f"Welcome Error: {e}")

# ৬. মেসেজ ও কমেন্ট ফিল্টারিং
async def filter_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # চ্যানেলের মূল পোস্ট অটোমেটিক কপি বা ফরোয়ার্ড হলে তা ডিলিট হবে না
    if msg.is_automatic_forward:
        return

    chat_id = update.effective_chat.id

    # লিঙ্কড চ্যানেল আইডি বের করা
    linked_channel_id = None
    try:
        chat_info = await context.bot.get_chat(chat_id)
        linked_channel_id = chat_info.linked_chat_id
    except Exception:
        pass

    # অ্যাডমিন যদি অ্যানোনিমাস (গ্রুপের নাম দিয়ে) বা মূল চ্যানেলের প্রোফাইল দিয়ে মেসেজ দেয়
    if msg.sender_chat:
        if msg.sender_chat.id == chat_id or (linked_channel_id and msg.sender_chat.id == linked_channel_id):
            return  # অ্যাডমিন/চ্যানেলের মেসেজ, কোনো কিছু ডিলিট হবে না
        
        # বহিরাগত কোনো চ্যানেলের প্রোফাইল দিয়ে কমেন্ট করলে ডিলিট
        try:
            await msg.delete()
        except:
            pass
        return

    user = msg.from_user
    if not user:
        return

    # ==================== অ্যাডমিন এবং ওনার চেক ====================
    # ১. গ্রুপ অ্যাডমিন বা ওনার কিনা চেক করা
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user.id)
        if chat_member.status in ['administrator', 'creator']:
            return  # অ্যাডমিন/ওনারদের কোনো মেসেজ ডিলিট হবে না
    except Exception:
        pass

    # ২. লিঙ্কড চ্যানেল অ্যাডমিন বা ওনার কিনা চেক করা
    if linked_channel_id:
        try:
            channel_member = await context.bot.get_chat_member(linked_channel_id, user.id)
            if channel_member.status in ['administrator', 'creator']:
                return  # চ্যানেল অ্যাডমিন/ওনারদের কোনো মেসেজ ডিলিট হবে না
        except Exception:
            pass
    # ===============================================================

    # --- সাধারণ মেম্বারদের জন্য ফিল্টারিং শুরু ---

    # ১. গ্রুপ এবং মূল চ্যানেলে জয়েন আছে কিনা চেক করা
    in_group = await is_member(context.bot, chat_id, user.id)
    in_channel = True

    if linked_channel_id:
        in_channel = await is_member(context.bot, linked_channel_id, user.id)

    # যদি যেকোনো একটিতে জয়েন না থাকে -> মেসেজ ডিলিট
    if not in_group or not in_channel:
        try:
            await msg.delete()
            warning = (
                f"⚠️ দুঃখিত {user.first_name}!\n\n"
                f"এখানে কমেন্ট বা মেসেজ পাঠাতে হলে আপনাকে **মূল চ্যানেল এবং গ্রুপ উভয়টিতেই জয়েন থাকতে হবে**।\n\n"
                f"👉 দয়া করে জয়েন হয়ে পুনরায় চেষ্টা করুন।"
            )
            await context.bot.send_message(chat_id=chat_id, text=warning)
        except Exception as e:
            print(f"Delete Error: {e}")
        return

    # ২. লিংক অথবা @ দিয়ে মেনশন/ইউজারনেম চেক করা
    text = msg.text or msg.caption or ""
    entities = (msg.entities or ()) + (msg.caption_entities or ())

    has_link = bool(re.search(LINK_REGEX, text, re.IGNORECASE))
    has_mention = bool(re.search(MENTION_REGEX, text))

    # টেলিগ্রাম এনটিটি দিয়েও নিখুঁতভাবে চেক করা
    for entity in entities:
        if entity.type in [MessageEntityType.MENTION, MessageEntityType.TEXT_MENTION]:
            has_mention = True
        elif entity.type in [MessageEntityType.URL, MessageEntityType.TEXT_LINK]:
            has_link = True

    # @ মেনশন বা ইউজারনেম থাকলে ডিলিট
    if has_mention:
        try:
            await msg.delete()
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🚫 দুঃখিত {user.first_name}! এখানে `@` দিয়ে কাউকে মেনশন বা ইউজারনেম শেয়ার করা সম্পূর্ণ নিষেধ।"
            )
            return
        except Exception as e:
            print(f"Mention Delete Error: {e}")

    # লিংক থাকলে ডিলিট
    if has_link:
        try:
            await msg.delete()
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🚫 দুঃখিত {user.first_name}! এখানে যেকোনো ধরণের লিংক শেয়ার করা সম্পূর্ণ নিষেধ।"
            )
            return
        except Exception as e:
            print(f"Link Delete Error: {e}")

def main():
    keep_alive()
    print("Bot starting...")

    app = Application.builder().token(TOKEN).build()

    # মেম্বার জয়েন হ্যান্ডলার
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # সকল মেসেজ ফিল্টার হ্যান্ডলার
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, filter_messages))

    print("Bot is successfully running 24/7!")
    app.run_polling()

if __name__ == "__main__":
    main()
