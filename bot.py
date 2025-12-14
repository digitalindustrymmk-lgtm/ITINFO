import telebot
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

# --- Configuration ---
BOT_TOKEN = '8284240201:AAFxNOZkvvSyrFma7J-zfAeXMj1aT5oeT9Q'

# ==============================================================================
#   ការភ្ជាប់ទៅកាន់ FIREBASE ទាំង ២ (DUAL CONNECTION)
# ==============================================================================

# 1. ភ្ជាប់ទៅ Master Firebase (សម្រាប់ផ្ទៀងផ្ទាត់ - Read Only)
# សូមប្រើ key របស់ Database ដែលមានបញ្ជីឈ្មោះ (Image 2)
master_cred = credentials.Certificate("master_key.json")
master_app = firebase_admin.initialize_app(master_cred, {
    'databaseURL': 'https://dilistname-default-rtdb.firebaseio.com/'
}, name='master_app')

# 2. ភ្ជាប់ទៅ Recording Firebase (សម្រាប់កត់ត្រា - Write)
# សូមប្រើ key របស់ Database ថ្មីដែលចង់រក្សាទុក (Image 1)
record_cred = credentials.Certificate("record_key.json")
record_app = firebase_admin.initialize_app(record_cred, {
    'databaseURL': 'https://itinfo-8501a-default-rtdb.firebaseio.com/'
}, name='record_app')

# --- Database References ---

# យោងតាមរូបភាពទី ២: Path គឺ 'students'
MASTER_REF = db.reference('students', app=master_app)

# យោងតាមរូបភាពទី ១: Path កត់ត្រាក៏ឈ្មោះ 'students' ដែរ
RECORD_REF = db.reference('students', app=record_app)


bot = telebot.TeleBot(BOT_TOKEN)
user_data = {}

# --- Bot Logic ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # ចាប់យកព័ត៌មាន Telegram
    username = message.from_user.username
    full_telegram_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
    telegram_link = f"https://t.me/{username}" if username else "No Link"
    username_text = f"@{username}" if username else "No Username"

    user_data[user_id] = {
        "telegram_id": user_id,
        "telegram_name": full_telegram_name,
        "telegram_username": username_text,
        "telegram_link": telegram_link
    }

    msg = bot.reply_to(message, "❤️សូមស្វាគមន៍!បំពេញព័ត៌មានសិក្សា!\nសូមវាយបញ្ចូល **អត្តលេខការងារ**ដើម្បីផ្ទៀងផ្ទាត់៖")
    bot.register_next_step_handler(msg, verify_student_id_from_master)

def verify_student_id_from_master(message):
    try:
        user_id = message.from_user.id
        input_id = message.text.strip() # អត្តលេខដែល User វាយ (ឧ. 111)
        
        if user_id not in user_data:
             bot.reply_to(message, "សូមប្អូនចុច /start ម្តងទៀត។")
             return

        # ===============================================================
        #  ជំហានទី ១: ឆែកមើលក្នុង MASTER DB (តាមរូបភាពទី ២)
        # ===============================================================
        # MASTER_REF ចង្អុលទៅ 'students'
        # child(input_id) នឹងរត់ទៅរក Folder '111'
        student_check = MASTER_REF.child(input_id).get()

        if student_check is None:
            bot.reply_to(message, f"❌ អត្តលេខ `{input_id}` របស់ប្អូនមិនមាននៅក្នុងបញ្ជីឈ្មោះគោលទេ។", parse_mode="Markdown")
            return
        
        # ទាញយកឈ្មោះពិតពី Master DB
        # យោងតាមរូបភាពទី ២ Field ឈ្មោះគឺសរសេរថា "ឈ្មោះ"
        real_name_in_master = student_check.get('ឈ្មោះ') 
        
        if not real_name_in_master:
            # ការពារករណីមាន Folder តែអត់មាន Field ឈ្មោះ
            bot.reply_to(message, "❌ រកឃើញអត្តលេខ តែទិន្នន័យឈ្មោះមិនពេញលេញ។")
            return

        # រក្សាទុកក្នុង Memory ដើម្បីផ្ទៀងផ្ទាត់ជំហានក្រោយ
        user_data[user_id]['student_id'] = input_id
        user_data[user_id]['expected_name'] = real_name_in_master 
        
        msg = bot.reply_to(message, f"✅ អត្តលេខត្រឹមត្រូវ។\nសូមប្អូនវាយបញ្ចូល **ឈ្មោះពេញជាភាសាខ្មែរ** របស់ប្អូន៖")
        bot.register_next_step_handler(msg, verify_name_and_save)
            
    except Exception as e:
        bot.reply_to(message, f"Error Master DB: {e}")

def verify_name_and_save(message):
    try:
        user_id = message.from_user.id
        input_name = message.text.strip()
        
        if user_id not in user_data:
             bot.reply_to(message, "សូមចុច /start ម្តងទៀត។")
             return

        expected_name = user_data[user_id]['expected_name']

        # ===============================================================
        #  ជំហានទី ២: ផ្ទៀងផ្ទាត់ឈ្មោះ
        # ===============================================================
        # ប្រៀបធៀបឈ្មោះដែលវាយ ជាមួយឈ្មោះក្នុង Database ("ស៊ី ប៊ុនស៊ឹង")
        if input_name != expected_name:
            bot.reply_to(message, 
                         f"❌ ឈ្មោះមិនត្រឹមត្រូវ!\n"
                         f"អត្តលេខនេះត្រូវមានឈ្មោះ៖ **{expected_name}**\n"
                         f"តែអ្នកវាយ៖ **{input_name}**\n\n"
                         "សូមប្អូនព្យាយាមម្តងទៀត។", parse_mode="Markdown")
            return

        # ===============================================================
        #  ជំហានទី ៣: រក្សាទុកចូល RECORDING DB (តាមរូបភាពទី ១)
        # ===============================================================
        
        final_data = user_data[user_id]
        
        # លុប Field ដែលមិនចង់ Save
        del final_data['expected_name'] 
        
        # យកឈ្មោះដែលត្រឹមត្រូវដាក់ចូល
        final_data['khmer_name'] = expected_name 
        
        # ប្រើអត្តលេខជា Key សម្រាប់ Save
        student_key = final_data['student_id']
        
        # Save ចូល Database ទី ១ (Recording)
        RECORD_REF.child(str(student_key)).set(final_data)
        
        response_text = (
            "✅ **ចុះឈ្មោះបានជោគជ័យ!**\n"
            f"👤 ឈ្មោះ: {final_data['khmer_name']}\n"
            f"🆔 អត្តលេខ: {final_data['student_id']}\n"
            "❤️ទិន្នន័យរបស់ប្អូនត្រូវបានកត់ត្រា។"
        )
        bot.send_message(message.chat.id, response_text, parse_mode="Markdown")
        
        # Clear Memory
        del user_data[user_id]
        
    except Exception as e:
        bot.reply_to(message, f"Error Recording DB: {str(e)}")

print("Bot is running...")
bot.infinity_polling()
