import os
import re
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

# ১. আপনার বট টোকেন
TOKEN = os.getenv("BOT_TOKEN", "8781582257:AAFiv9liUbPvFCUkARJNqEKOxFmuBGs-uI8")

# ২. আপনার মূল চ্যানেল বা গ্রুপের ইউজারনেম (@ সহ লিখুন)
# উদাহরণ: "@my_main_channel" অথবা আইডি
MAIN_CHANNEL = "@your_channel_username"  # <-- এখানে আপনার চ্যানেলের ইউজারনেম দিন

# লিংক ধরার জন্য ফিল্টার
LINK_REGEX = r'(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+|wa\.me/\S+|\b\w+\.(com|net|org|xyz|io|me|info|site|online|shop|live|app)\b)'

# ইউজার চ্যানেলে জয়েন আছে কিনা চেক করার ফাংশন
async def is_user_member(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=MAIN_CHANNEL, user_id=user_id)
        # জয়েন থাকলে স্ট্যাটাস হবে member, administrator বা creator
        if member.status in ['member', 'administrator', 'creator', 'restricted']:
            return True
        return False
    except Exception as e:
        print(f"চ্যানেল চেক করতে সমস্যা: {e}")
        # যদি চ্যানেল না পাওয়া যায় বা বট এডমিন না থাকে তবে মেসেজ আটকাবে না
        return True

# ১. নতুন সদস্য আসলে স্বাগতম মেসেজ
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        if user.id == context.bot.id:
            continue
        name = user.first_name
        welcome_text = f"👋 স্বাগতম {name}!\n🌸 আমাদের গ্রুপে আপনাকে স্বাগতম!"
        await update.message.reply_text(welcome_text)

# ২. মেসেজ ফিল্টারিং (লিংক ডিলিট + জয়েন চেক)
async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    user = update.message.from_user
    chat_id = update.effective_chat.id
    text = update.message.text or update.message.caption or ""

    # এডমিনদের মেসেজ ডিলিট হবে না
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user.id)
        if chat_member.status in ['administrator', 'creator']:
            return
    except:
        pass

    # --- চেক ১: ইউজার মূল চ্যানেলে জয়েন আছে কিনা ---
    if MAIN_CHANNEL and MAIN_CHANNEL != "@your_channel_username":
        is_joined = await is_user_member(context, user.id)
        if not is_joined:
            try:
                await update.message.delete()
                warning_join = (
                    f"⚠️ দুঃখিত {user.first_name}!\n\n"
                    f"এখানে মেসেজ বা কমেন্ট করতে হলে আপনাকে অবশ্যই আমাদের মূল চ্যানেলে জয়েন থাকতে হবে।\n\n"
                    f"👉 আগে জয়েন করুন: {MAIN_CHANNEL}"
                )
                await context.bot.send_message(chat_id=chat_id, text=warning_join)
                return
            except Exception as e:
                print(f"মেসেজ ডিলিট করতে সমস্যা: {e}")

    # --- চেক ২: কোনো লিংক পাঠিয়েছে কিনা ---
    if re.search(LINK_REGEX, text, re.IGNORECASE):
        try:
            await update.message.delete()
            warning_link = f"🚫 দুঃখিত {user.first_name}! এই গ্রুপে কোনো লিংক পাঠানো সম্পূর্ণ নিষেধ।"
            await context.bot.send_message(chat_id=chat_id, text=warning_link)
        except Exception as e:
            print(f"লিংক ডিলিট করতে সমস্যা: {e}")

def main():
    print("Bot is starting...")
    app = Application.builder().token(TOKEN).build()

    # মেম্বার জয়েন হ্যান্ডলার
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # সব টেক্সট এবং মিডিয়া মেসেজ চেক করার হ্যান্ডলার
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.StatusUpdate.ALL, check_message))

    print("Bot is successfully running!")
    app.run_polling()

if __name__ == "__main__":
    main()
