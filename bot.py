import telebot
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from telebot import types

# --- Configuration ---
BOT_TOKEN = '8284240201:AAFxNOZkvvSyrFma7J-zfAeXMj1aT5oeT9Q'

# ភ្ជាប់ទៅ Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://itinfo-8501a-default-rtdb.firebaseio.com/' 
    })

bot = telebot.TeleBot(BOT_TOKEN)

# ឃ្លាំងផ្ទុកទិន្នន័យបណ្តោះអាសន្ន
user_data = {}

# --- Bot Logic ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # ទទួលព័ត៌មាន Telegram
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name if message.from_user.last_name else ""
    full_telegram_name = f"{first_name} {last_name}".strip()
    telegram_link = f"https://t.me/{username}" if username else "No Link"
    username_text = f"@{username}" if username else "No Username"

    # Save temp data
    user_data[user_id] = {
        "telegram_id": user_id,
        "telegram_name": full_telegram_name,
        "telegram_username": username_text,
        "telegram_link": telegram_link
    }

    msg = bot.reply_to(message, "សូមស្វាគមន៍! \nសូមវាយបញ្ចូល **អត្តលេខ** (Student ID) របស់អ្នក៖\n(ឧទាហរណ៍: 9090)")
    bot.register_next_step_handler(msg, process_student_id)

def process_student_id(message):
    try:
        user_id = message.from_user.id
        student_id = message.text.strip()
        
        if user_id not in user_data:
             bot.reply_to(message, "សូមចុច /start ម្តងទៀត។")
             return

        # រក្សាទុក Student ID បណ្តោះអាសន្ន
        user_data[user_id]['student_id'] = student_id
        
        # --- ត្រួតពិនិត្យទិន្នន័យស្ទួន (Check Duplicate) ---
        ref = db.reference('students')
        # ទាញយកទិន្នន័យតាមរយៈ ID ដែលបានបញ្ចូល
        snapshot = ref.child(student_id).get()
        
        if snapshot:
            # ករណីមានទិន្នន័យរួចហើយ (Duplicate)
            existing_name = snapshot.get('khmer_name', 'Unknown')
            
            # បង្កើតប៊ូតុង ជម្រើស
            markup = types.InlineKeyboardMarkup()
            btn_update = types.InlineKeyboardButton("📝 Update (កែប្រែ)", callback_data="cmd_update")
            btn_cancel = types.InlineKeyboardButton("❌ Cancel (បោះបង់)", callback_data="cmd_cancel")
            markup.add(btn_update, btn_cancel)
            
            text_warning = (
                f"⚠️ **ជូនដំណឹង:** អត្តលេខ `{student_id}` នេះមានក្នុងប្រព័ន្ធរួចហើយ!\n"
                f"👤 ឈ្មោះម្ចាស់ចាស់: **{existing_name}**\n\n"
                "តើអ្នកចង់ធ្វើអ្វីបន្ត?"
            )
            bot.send_message(message.chat.id, text_warning, reply_markup=markup, parse_mode="Markdown")
            
        else:
            # ករណីថ្មី (New User) -> ទៅសួរឈ្មោះខ្មែរតែម្តង
            msg = bot.reply_to(message, "សូមវាយបញ្ចូល **ឈ្មោះពេញជាភាសាខ្មែរ** របស់អ្នក៖")
            bot.register_next_step_handler(msg, process_khmer_name)
            
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

# --- Callback Handler សម្រាប់ប៊ូតុង Update / Cancel ---
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    user_id = call.from_user.id
    
    if call.data == "cmd_cancel":
        # ករណីបោះបង់
        bot.answer_callback_query(call.id, "ប្រតិបត្តិការត្រូវបានបោះបង់")
        bot.send_message(call.message.chat.id, "✅ អ្នកបានជ្រើសរើស **បោះបង់**។ សូមចុច /start ដើម្បីចាប់ផ្តើមថ្មី។")
        # លុបទិន្នន័យបណ្តោះអាសន្ន
        if user_id in user_data:
            del user_data[user_id]

    elif call.data == "cmd_update":
        # ករណីចង់ Update (បន្តទៅសួរឈ្មោះ)
        bot.answer_callback_query(call.id, "កំពុងដំណើរការ...")
        msg = bot.send_message(call.message.chat.id, "សូមវាយបញ្ចូល **ឈ្មោះពេញជាភាសាខ្មែរ** ថ្មីរបស់អ្នក ដើម្បីធ្វើបច្ចុប្បន្នភាព៖")
        bot.register_next_step_handler(msg, process_khmer_name)

def process_khmer_name(message):
    try:
        user_id = message.from_user.id
        khmer_name = message.text
        
        if user_id not in user_data:
             bot.reply_to(message, "សូមចុច /start ម្តងទៀត។")
             return

        # Update ឈ្មោះខ្មែរក្នុង Memory
        user_data[user_id]['khmer_name'] = khmer_name
        
        # Save to Firebase
        final_data = user_data[user_id]
        student_key = final_data['student_id']
        
        ref = db.reference('students')
        ref.child(str(student_key)).set(final_data)
        
        response_text = (
            "✅ **រក្សាទុកជោគជ័យ!**\n\n"
            f"👤 ឈ្មោះ: {final_data['khmer_name']}\n"
            f"🆔 អត្តលេខ: {final_data['student_id']}\n"
            "ទិន្នន័យត្រូវបានធ្វើបច្ចុប្បន្នភាព។"
        )
        bot.send_message(message.chat.id, response_text, parse_mode="Markdown")
        
        # Clear Memory
        del user_data[user_id]
        
    except Exception as e:
        bot.reply_to(message, f"Error Save: {str(e)}")

# --- Run Bot ---
print("Bot is running...")
bot.infinity_polling()
