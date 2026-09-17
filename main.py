import os
import re
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters

# ১. টোকেন ও চ্যানেল/গ্রুপ তথ্য
TOKEN = os.getenv("BOT_TOKEN", "8781582257:AAFiv9liUbPvFCUkARJNqEKOxFmuBGs-uI8")

# 👉 এখানে আপনার চ্যানেল ও গ্রুপের ইউজারনেম (@ সহ) দিন
CHANNEL_USERNAME = "@your_channel_username"  # আপনার মূল চ্যানেল
GROUP_USERNAME = "@your_group_username"      # আপনার কমেন্ট/আলোচনা গ্রুপ

LINK_REGEX = r'(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+|wa\.me/\S+|\b\w+\.(com|net|org|xyz|io|me|info|site|online|shop|live|app)\b)'

# ২. ২৪ ঘণ্টা চালু রাখার জন্য Flask সার্ভার
server = Flask(__name__)

@server.route('/')
def home():
    return "Bot is active 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    server.run(host="0.0.0.0", port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()

# ৩. সদস্যপদ চেক করার নির্ভুল ফাংশন
async def check_user_membership(bot, chat_target, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat_target, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator', 'restricted']:
            return True
        return False
    except Exception as e:
        print(f"Error checking {chat_target}: {e}")
        return False

# ৪. /status কমান্ড (বট ঠিকমতো কাজ করছে কিনা পরীক্ষা করার জন্য)
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    msg = "🔍 **বটের বর্তমান স্ট্যাটাস পরীক্ষা:**\n\n"
    
    # চ্যানেল চেক
    try:
        ch_bot = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=bot.id)
        msg += f"✅ মূল চ্যানেল ({CHANNEL_USERNAME}): বট অ্যাডমিন আছে!\n"
    except Exception:
        msg += f"❌ মূল চ্যানেল ({CHANNEL_USERNAME}): বট অ্যাডমিন নেই বা ভুল ইউজারনেম!\n"

    # গ্রুপ চেক
    try:
        gr_bot = await bot.get_chat_member(chat_id=GROUP_USERNAME, user_id=bot.id)
        msg += f"✅ মূল গ্রুপ ({GROUP_USERNAME}): বট অ্যাডমিন আছে!\n"
    except Exception:
        msg += f"❌ মূল গ্রুপ ({GROUP_USERNAME}): বট অ্যাডমিন নেই বা ভুল ইউজারনেম!\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# ৫. নতুন মেম্বার আসলে স্বাগতম মেসেজ
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        if user.id == context.bot.id:
            continue
        await update.message.reply_text(f"👋 স্বাগতম {user.first_name}!\n🌸 আমাদের গ্রুপ ও চ্যানেলে আপনাকে স্বাগতম!")

# ৬. মেসেজ এবং কমেন্ট ফিল্টারিং (মূল প্রসেস)
async def filter_incoming_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # চ্যানেলের নিজস্ব অটো-ফরওয়ার্ড পোস্ট ডিলিট হবে না
    if msg.is_automatic_forward:
        return

    # যদি কেউ অন্য কোনো চ্যানেলের মাধ্যমে কমেন্ট করতে আসে
    if msg.sender_chat and not msg.from_user:
        try:
            await msg.delete()
        except:
            pass
        return

    user = msg.from_user
    chat_id = update.effective_chat.id
    text = msg.text or msg.caption or ""

    # গ্রুপ অ্যাডমিনদের মেসেজ ডিলিট হবে না
    try:
        chat_admin = await context.bot.get_chat_member(chat_id, user.id)
        if chat_admin.status in ['administrator', 'creator']:
            return
    except:
        pass

    # --- চ্যানেল এবং গ্রুপ উভয়ের সদস্যপদ যাচাই ---
    is_in_channel = await check_user_membership(context.bot, CHANNEL_USERNAME, user.id)
    is_in_group = await check_user_membership(context.bot, GROUP_USERNAME, user.id)

    # যদি যেকোনো একটিতে জয়েন না থাকে
    if not is_in_channel or not is_in_group:
        try:
            await msg.delete()
            warning = (
                f"⚠️ দুঃখিত {user.first_name}!\n\n"
                f"এখানে কমেন্ট বা মেসেজ করতে হলে আপনাকে **উভয় জায়গায় জয়েন থাকতে হবে**:\n\n"
                f"১️⃣ মূল চ্যানেল: {CHANNEL_USERNAME}\n"
                f"২️⃣ মূল গ্রুপ: {GROUP_USERNAME}\n\n"
                f"দয়া করে জয়েন হয়ে পুনরায় মেসেজ করুন।"
            )
            await context.bot.send_message(chat_id=chat_id, text=warning)
            return
        except Exception as e:
            print(f"Delete Error: {e}")

    # --- কোনো লিংক থাকলে সাথে সাথে ডিলিট ---
    if re.search(LINK_REGEX, text, re.IGNORECASE):
        try:
            await msg.delete()
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🚫 দুঃখিত {user.first_name}! এখানে যেকোনো ধরণের লিংক শেয়ার করা নিষিদ্ধ।"
            )
        except Exception as e:
            print(f"Link Delete Error: {e}")

def main():
    keep_alive()
    print("Bot is starting...")

    app = Application.builder().token(TOKEN).build()

    # কমান্ড হ্যান্ডলার
    app.add_handler(CommandHandler("status", status_command))

    # ওয়েলকাম হ্যান্ডলার
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # মূল ফিল্টারিং হ্যান্ডলার
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, filter_incoming_messages))

    print("Bot is fully running!")
    app.run_polling()

if __name__ == "__main__":
    main()
