import telebot
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from telebot import types

# --- Configuration ---
# ដាក់ Token របស់ Bot អ្នកនៅទីនេះ
BOT_TOKEN = '8284240201:AAFxNOZkvvSyrFma7J-zfAeXMj1aT5oeT9Q'

# ភ្ជាប់ទៅ Firebase
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://itinfo-8501a-default-rtdb.firebaseio.com/' 
    # ឧទាហរណ៍: https://your-project.firebasedatabase.app/
})

bot = telebot.TeleBot(BOT_TOKEN)

# ឃ្លាំងផ្ទុកទិន្នន័យបណ្តោះអាសន្ន
user_data = {}

# --- Bot Logic ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # ទាញយកព័ត៌មានស្វ័យប្រវត្តិ
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name if message.from_user.last_name else ""
    full_telegram_name = f"{first_name} {last_name}".strip()
    
    telegram_link = f"https://t.me/{username}" if username else "No Link"
    username_text = f"@{username}" if username else "No Username"

    # រក្សាទុកក្នុង Memory ជាបណ្តោះអាសន្ន
    user_data[user_id] = {
        "telegram_id": user_id,
        "telegram_name": full_telegram_name,
        "telegram_username": username_text,
        "telegram_link": telegram_link
    }

    msg = bot.reply_to(message, "សូមស្វាគមន៍! \nសូមវាយបញ្ចូល **អត្តលេខ** (Student ID) របស់អ្នក៖")
    bot.register_next_step_handler(msg, process_student_id)

def process_student_id(message):
    try:
        user_id = message.from_user.id
        student_id = message.text
        
        # រក្សាទុកអត្តលេខ
        user_data[user_id]['student_id'] = student_id
        
        msg = bot.reply_to(message, "សូមវាយបញ្ចូល **ឈ្មោះពេញជាភាសាខ្មែរ** របស់អ្នក៖")
        bot.register_next_step_handler(msg, process_khmer_name)
    except Exception as e:
        bot.reply_to(message, "មានបញ្ហាបច្ចេកទេស សូមចុច /start ម្តងទៀត។")

def process_khmer_name(message):
    try:
        user_id = message.from_user.id
        khmer_name = message.text
        
        # រក្សាទុកឈ្មោះខ្មែរ
        user_data[user_id]['khmer_name'] = khmer_name
        
        # --- Save to Firebase Realtime Database ---
        # យើងប្រើ Student ID ជា Key ឬ User ID ជា Key ក៏បាន
        ref = db.reference('students')
        
        # បង្កើតទិន្នន័យចុងក្រោយ
        final_data = user_data[user_id]
        
        # Push ទៅ Database (ប្រើ child(user_id) ដើម្បីកុំឱ្យជាន់គ្នា)
        ref.child(str(user_id)).set(final_data)
        
        # ឆ្លើយតបទៅកាន់ User វិញ
        response_text = (
            "✅ **ការចុះឈ្មោះជោគជ័យ!**\n\n"
            f"👤 ឈ្មោះ: {final_data['khmer_name']}\n"
            f"🆔 អត្តលេខ: {final_data['student_id']}\n"
            f"🔗 Telegram: {final_data['telegram_link']}\n"
            "ទិន្នន័យរបស់អ្នកត្រូវបានរក្សាទុក។"
        )
        bot.send_message(message.chat.id, response_text, parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"បរាជ័យក្នុងការរក្សាទុកទិន្នន័យ: {str(e)}")

# --- Run Bot ---
print("Bot is running...")
bot.infinity_polling()
