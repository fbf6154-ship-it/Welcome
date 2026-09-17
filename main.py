import os
import re
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

# ১. টোকেন ও চ্যানেল/গ্রুপ কনফিগারেশন
TOKEN = os.getenv("BOT_TOKEN", "8781582257:AAFiv9liUbPvFCUkARJNqEKOxFmuBGs-uI8")

# আপনার মূল চ্যানেল এবং গ্রুপের ইউজারনেম (@ সহ দিন)
MAIN_CHANNEL = "@your_channel_username"  # <-- মূল চ্যানেলের ইউজারনেম
MAIN_GROUP = "@your_group_username"      # <-- মূল গ্রুপের ইউজারনেম

# লিংক ধরার ফিল্টার
LINK_REGEX = r'(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+|wa\.me/\S+|\b\w+\.(com|net|org|xyz|io|me|info|site|online|shop|live|app)\b)'

# ২. ২৪ ঘণ্টা চালু রাখার জন্য Flask ওয়েব সার্ভার
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

# ৩. জয়েনিং চেক করার ফাংশন (চ্যানেল এবং গ্রুপ)
async def is_member(context: ContextTypes.DEFAULT_TYPE, chat_id, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        # জয়েন থাকলে স্ট্যাটাস হবে member, administrator বা creator
        if member.status in ['member', 'administrator', 'creator', 'restricted']:
            return True
        return False
    except Exception as e:
        print(f"মেম্বারশিপ চেক এরর ({chat_id}): {e}")
        # বট এডমিন না থাকলে বা কোনো সমস্যা হলে মেসেজ আটকাবে না
        return True

# ৪. নতুন সদস্যের জন্য স্বাগতম মেসেজ
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        if user.id == context.bot.id:
            continue
        name = user.first_name
        await update.message.reply_text(f"👋 স্বাগতম {name}!\n🌸 আমাদের পরিবারে আপনাকে স্বাগতম!")

# ৫. মেসেজ ফিল্টারিং (চ্যানেল + গ্রুপ জয়েন চেক এবং অ্যান্টি-লিংক)
async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    user = update.message.from_user
    chat_id = update.effective_chat.id
    text = update.message.text or update.message.caption or ""

    # গ্রুপ এডমিনদের মেসেজ ডিলিট হবে না
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user.id)
        if chat_member.status in ['administrator', 'creator']:
            return
    except:
        pass

    # --- ১. মূল চ্যানেলে এবং গ্রুপে জয়েন আছে কিনা চেক করা ---
    in_channel = True
    in_group = True

    if MAIN_CHANNEL and MAIN_CHANNEL != "@your_channel_username":
        in_channel = await is_member(context, MAIN_CHANNEL, user.id)

    if MAIN_GROUP and MAIN_GROUP != "@your_group_username":
        in_group = await is_member(context, MAIN_GROUP, user.id)

    # যদি যেকোনো একটিতে জয়েন না থাকে, তবে মেসেজ ডিলিট হবে
    if not in_channel or not in_group:
        try:
            await update.message.delete()
            warning_text = (
                f"⚠️ দুঃখিত {user.first_name}!\n\n"
                f"এখানে কমেন্ট বা মেসেজ করার জন্য আপনাকে আমাদের **চ্যানেল এবং গ্রুপ উভয়টিতেই জয়েন থাকতে হবে**।\n\n"
                f"📢 চ্যানেল: {MAIN_CHANNEL}\n"
                f"👥 গ্রুপ: {MAIN_GROUP}\n\n"
                f"👉 দয়া করে জয়েন হয়ে পুনরায় চেষ্টা করুন।"
            )
            await context.bot.send_message(chat_id=chat_id, text=warning_text)
            return
        except Exception as e:
            print(f"মেসেজ ডিলিট করতে সমস্যা: {e}")

    # --- ২. কোনো লিংক পাঠিয়েছে কিনা চেক করা ---
    if re.search(LINK_REGEX, text, re.IGNORECASE):
        try:
            await update.message.delete()
            await context.bot.send_message(
                chat_id=chat_id, 
                text=f"🚫 দুঃখিত {user.first_name}! এই গ্রুপে কোনো প্রকার লিংক পাঠানো সম্পূর্ণ নিষেধ।"
            )
        except Exception as e:
            print(f"লিংক ডিলিট এরর: {e}")

def main():
    keep_alive()  # ব্যাকগ্রাউন্ড সার্ভার চালু
    print("Bot is starting...")
    
    app = Application.builder().token(TOKEN).build()

    # মেম্বার জয়েন হ্যান্ডলার
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # সব ধরণের টেক্সট, ফটো, ভিডিও ইত্যাদি মেসেজ চেক হ্যান্ডলার
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.StatusUpdate.ALL, check_message))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
