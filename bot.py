import os
import re
import logging
import asyncio
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import firebase_admin
from firebase_admin import credentials, db

# --- KEEP ALIVE (បើអ្នកមិនមាន file keep_alive.py សូមលុបផ្នែកនេះចេញ) ---
try:
    from keep_alive import keep_alive
    HAS_KEEP_ALIVE = True
except ImportError:
    HAS_KEEP_ALIVE = False
    print("⚠️ មិនមាន keep_alive.py ទេ (ដំណើរការធម្មតា)")

# --- CONFIGURATION ---
# ដាក់ Token ថ្មីរបស់អ្នកនៅទីនេះ (កុំឱ្យគេឃើញ)
TOKEN = '8284240201:AAFgnJBRmKn18QzDURQ6fuHhR7lqp4QbM2A' 
FIREBASE_KEY = 'serviceAccountKey.json' 
DATABASE_URL = 'https://itinfo-8501a-default-rtdb.firebaseio.com/'

# --- FIREBASE SETUP ---
if not firebase_admin._apps:
    if os.path.exists(FIREBASE_KEY):
        cred = credentials.Certificate(FIREBASE_KEY)
        firebase_admin.initialize_app(cred, {
            'databaseURL': DATABASE_URL
        })
    else:
        print(f"❌ រកមិនឃើញឯកសារ {FIREBASE_KEY} ទេ។ សូមដាក់វានៅកន្លែងជាមួយកូដ។")
        exit()

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- STATES ---
FULL_NAME, PROVINCE, PHONE = range(3)

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    
    # ប្រមូលព័ត៌មានមូលដ្ឋាន
    base_info = {
        'telegram_id': user.id,
        'username': user.username if user.username else "N/A",
        'first_name': user.first_name,
        'last_name': user.last_name if user.last_name else "",
        'link': f"https://t.me/{user.username}" if user.username else "N/A",
        'joined_at': str(update.message.date)
    }

    # រក្សាទុកក្នុង Firebase
    try:
        ref = db.reference(f'users/{user.id}')
        ref.update(base_info)
    except Exception as e:
        logger.error(f"Firebase Error: {e}")

    await update.message.reply_text(
        f"សួស្តី {user.first_name}! 👋\nBot បានកត់ត្រាព័ត៌មាន Telegram របស់អ្នករួចរាល់។\n\n"
        "ដើម្បីបញ្ចប់ការចុះឈ្មោះ សូមជួយបំពេញព័ត៌មានបន្ថែម៖\n\n"
        "1️⃣ **សូមវាយឈ្មោះពេញរបស់អ្នក (ជាភាសាខ្មែរ)៖**",
        parse_mode='Markdown'
    )
    return FULL_NAME

# --- HANDLE FULL NAME ---
async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    name_input = update.message.text

    ref = db.reference(f'users/{user_id}')
    ref.update({'khmer_name': name_input})

    await update.message.reply_text("2️⃣ **តើអ្នកមកពីខេត្តណាដែរ?**")
    return PROVINCE

# --- HANDLE PROVINCE ---
async def receive_province(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    province_input = update.message.text

    ref = db.reference(f'users/{user_id}')
    ref.update({'province': province_input})

    await update.message.reply_text("3️⃣ **សូមវាយបញ្ចូលលេខទូរស័ព្ទរបស់អ្នក (ឧទាហរណ៍: 012345678)៖**")
    return PHONE

# --- HANDLE PHONE ---
async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    phone_input = update.message.text

    # Validate Phone Number
    pattern = re.compile(r'^(0|\+855)?[1-9][0-9]{7,8}$')
    
    if not pattern.match(phone_input):
        await update.message.reply_text("❌ លេខទូរស័ព្ទមិនត្រឹមត្រូវ។ សូមព្យាយាមម្តងទៀត (ឧទាហរណ៍: 012345678)៖")
        return PHONE

    ref = db.reference(f'users/{user_id}')
    ref.update({'phone_number': phone_input, 'status': 'completed'})

    await update.message.reply_text(
        "✅ **ការចុះឈ្មោះជោគជ័យ!**\n\nទិន្នន័យរបស់អ្នកត្រូវបានរក្សាទុកក្នុងប្រព័ន្ធ។\nសូមអរគុណ!",
        parse_mode='Markdown'
    )
    return ConversationHandler.END

# --- CANCEL ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("ប្រតិបត្តិការត្រូវបានលុបចោល។ /start ដើម្បីចាប់ផ្តើមថ្មី។")
    return ConversationHandler.END

# --- MAIN FUNCTION ---
def main():
    # ដំណើរការ Web Server ប្រសិនបើមាន keep_alive
    if HAS_KEEP_ALIVE:
        keep_alive()

    # បង្កើត Application
    application = Application.builder().token(TOKEN).build()

    # កំណត់លំហូរនៃការសន្ទនា
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            PROVINCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_province)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
