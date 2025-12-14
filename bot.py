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
record_cred = credentials.Certificate("serviceAccountKey.json")
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

def verify_student_id_from_master(message):
    try:
        user_id = message.from_user.id
        input_id = message.text.strip()
        
        # ការពារករណីបាត់ Memory (Bot Restart)
        if user_id not in user_data:
             bot.reply_to(message, "ទិន្នន័យបាត់បង់ សូមចុច /start ដើម្បីចាប់ផ្តើមឡើងវិញ។")
             return

        # ===============================================================
        #  ជំហានទី ១: ឆែកមើលក្នុង MASTER DB
        # ===============================================================
        student_check = MASTER_REF.child(input_id).get()

        if student_check is None:
            # === កន្លែងកែប្រែ (FIX) ===
            # បើខុស សូមឱ្យវាចាំទទួលសារម្តងទៀត មិនមែនឈប់ទេ
            msg = bot.reply_to(message, f"❌ អត្តលេខ `{input_id}` មិនត្រឹមត្រូវទេ។\nសូមព្យាយាមវាយ **អត្តលេខ** ម្តងទៀត៖", parse_mode="Markdown")
            bot.register_next_step_handler(msg, verify_student_id_from_master) # <--- បន្ថែមបន្ទាត់នេះ
            return
        
        # ទាញយកឈ្មោះពិត "ឈ្មោះ" (តាមរូបភាពរបស់អ្នក)
        real_name_in_master = student_check.get('ឈ្មោះ') 
        
        if not real_name_in_master:
            msg = bot.reply_to(message, "❌ អត្តលេខនេះមានបញ្ហាបច្ចេកទេស (គ្មានឈ្មោះ)។ សូមទាក់ទង Admin ឬវាយអត្តលេខផ្សេង៖")
            bot.register_next_step_handler(msg, verify_student_id_from_master) # <--- បន្ថែមបន្ទាត់នេះ
            return

        # បើត្រូវ រក្សាទុកក្នុង Memory
        user_data[user_id]['student_id'] = input_id
        user_data[user_id]['expected_name'] = real_name_in_master 
        
        # ទៅជំហានបន្ទាប់
        msg = bot.reply_to(message, f"✅ អត្តលេខត្រឹមត្រូវ។\nសូមវាយបញ្ចូល **ឈ្មោះពេញជាភាសាខ្មែរ** របស់ប្អូន៖")
        bot.register_next_step_handler(msg, verify_name_and_save)
            
    except Exception as e:
        # បើ Error System ឱ្យវាមកសួរអត្តលេខម្តងទៀត
        msg = bot.reply_to(message, f"Error: {e}\nសូមវាយអត្តលេខម្តងទៀត៖")
        bot.register_next_step_handler(msg, verify_student_id_from_master)

def verify_student_id_from_master(message):
    try:
        user_id = message.from_user.id
        input_id = message.text.strip()
        
        # ការពារករណីបាត់ Memory
        if user_id not in user_data:
             bot.reply_to(message, "ទិន្នន័យបាត់បង់ សូមចុច /start ដើម្បីចាប់ផ្តើមឡើងវិញ។")
             return

        # ===============================================================
        #  ផ្នែកទី ១: Security Check (ឆែកមើលម្ចាស់ដើមក្នុង RECORDING DB)
        # ===============================================================
        # ទៅមើលក្នុង Database កត់ត្រា ថាតើអត្តលេខនេះធ្លាប់មានម្ចាស់ឬនៅ?
        existing_record = RECORD_REF.child(input_id).get()

        if existing_record:
            # បើមានទិន្នន័យចាស់ -> យក Telegram ID ចាស់មកមើល
            registered_telegram_id = existing_record.get('telegram_id')
            
            # ប្រៀបធៀប ID អ្នកកំពុងចុច (user_id) ជាមួយ ID ចាស់ (registered_telegram_id)
            # យើងប្តូរទៅជា String ទាំងពីរដើម្បីធានាការប្រៀបធៀបត្រឹមត្រូវ
            if str(registered_telegram_id) != str(user_id):
                
                # === ករណីបន្លំ ឬប្តូរគណនី Telegram (BLOCK) ===
                error_text = (
                    f"⛔️ **មិនអនុញ្ញាតឱ្យកែប្រែ!**\n\n"
                    f"អត្តលេខ `{input_id}` នេះត្រូវបានចុះឈ្មោះដោយគណនី Telegram ផ្សេងរួចហើយ។\n"
                    "ប្អូនមិនអាចប្រើគណនីថ្មីមក Update ទិន្នន័យនេះបានទេ។\n\n"
                    "👉 **សូមទាក់ទង Admin ដើម្បីដោះស្រាយ។**"
                )
                bot.reply_to(message, error_text, parse_mode="Markdown")
                
                # បញ្ចប់ការងារត្រឹមនេះ (មិនទៅមុខ មិនឱ្យវាយឈ្មោះ)
                # យើងមិន Register Next Step ទេ ដើម្បីឱ្យគាត់ទាក់ទង Admin
                return 

        # ===============================================================
        #  ផ្នែកទី ២: ឆែកមើលក្នុង MASTER DB (ដូចមុន)
        # ===============================================================
        student_check = MASTER_REF.child(input_id).get()

        if student_check is None:
            msg = bot.reply_to(message, f"❌ អត្តលេខ `{input_id}` មិនត្រឹមត្រូវទេ។\nសូមប្អូនព្យាយាមវាយ **អត្តលេខ** ម្តងទៀត៖", parse_mode="Markdown")
            bot.register_next_step_handler(msg, verify_student_id_from_master)
            return
        
        real_name_in_master = student_check.get('ឈ្មោះ') 
        
        if not real_name_in_master:
            msg = bot.reply_to(message, "❌ អត្តលេខនេះមានបញ្ហាបច្ចេកទេស (គ្មានឈ្មោះក្នុងបញ្ជី)។ សូមប្អូនទាក់ទង Admin។")
            # ករណីនេះក៏ឈប់ដែរ
            return

        # រក្សាទុកក្នុង Memory
        user_data[user_id]['student_id'] = input_id
        user_data[user_id]['expected_name'] = real_name_in_master 
        
        msg = bot.reply_to(message, f"✅ អត្តលេខត្រឹមត្រូវ។\nសូមវាយបញ្ចូល **ឈ្មោះពេញជាភាសាខ្មែរ** របស់ប្អូន៖")
        bot.register_next_step_handler(msg, verify_name_and_save)
            
    except Exception as e:
        msg = bot.reply_to(message, f"Error: {e}\nសូមប្អូនវាយអត្តលេខម្តងទៀត៖")
        bot.register_next_step_handler(msg, verify_student_id_from_master)

# ===============================================================
        #  ជំហានទី ៣: រក្សាទុកចូល RECORDING DB
        # ===============================================================
        final_data = user_data[user_id]
        
        # Clean data
        if 'expected_name' in final_data:
            del final_data['expected_name'] 
        
        final_data['khmer_name'] = expected_name 
        student_key = final_data['student_id']
        
        # Save
        RECORD_REF.child(str(student_key)).set(final_data)
        
        response_text = (
            "✅ **ចុះឈ្មោះបានជោគជ័យ!**\n"
            f"👤 ឈ្មោះ: {final_data['khmer_name']}\n"
            f"🆔 អត្តលេខ: {final_data['student_id']}\n"
            "❤️ទិន្នន័យរបស់ប្អូនត្រូវបានកត់ត្រា។"
        )
        bot.send_message(message.chat.id, response_text, parse_mode="Markdown")
        
        # ចប់ជំហាននេះ យើងលុប Memory ចោលបាន
        del user_data[user_id]
        
    except Exception as e:
        bot.reply_to(message, f"Error Recording DB: {str(e)}")

print("Bot is running...")
bot.infinity_polling()
