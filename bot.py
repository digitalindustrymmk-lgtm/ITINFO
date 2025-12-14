import telebot
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

# ==============================================================================
#   ការកំណត់រចនាសម្ព័ន្ធ (CONFIGURATION)
# ==============================================================================

# 1. ដាក់ Token របស់ Bot អ្នក
BOT_TOKEN = '8284240201:AAFxNOZkvvSyrFma7J-zfAeXMj1aT5oeT9Q'

# 2. ដាក់ URL របស់ Firebase ទាំងពីរ
# URL របស់ Master DB (រូបភាពទី ២ - បញ្ជីឈ្មោះសិស្ស)
MASTER_DB_URL = 'https://dilistname-default-rtdb.firebaseio.com/' 

# URL របស់ Recording DB (រូបភាពទី ១ - កន្លែងកត់ត្រា)
RECORDING_DB_URL = 'https://itinfo-8501a-default-rtdb.firebaseio.com/'

# ==============================================================================
#   ការភ្ជាប់ FIREBASE (CONNECTION)
# ==============================================================================

# ភ្ជាប់ទៅ Master App (សម្រាប់មើលឈ្មោះផ្ទៀងផ្ទាត់)
# ត្រូវប្រាកដថាបាន Upload 'master_key.json' ចូល Render -> Secret Files
master_cred = credentials.Certificate("master_key.json")
master_app = firebase_admin.initialize_app(master_cred, {
    'databaseURL': MASTER_DB_URL
}, name='master_app')

# ភ្ជាប់ទៅ Recording App (សម្រាប់កត់ត្រាទិន្នន័យ)
# ប្រើឈ្មោះ 'serviceAccountKey.json' តាមដែលអ្នកមានស្រាប់ក្នុង Render
record_cred = credentials.Certificate("serviceAccountKey.json")
record_app = firebase_admin.initialize_app(record_cred, {
    'databaseURL': RECORDING_DB_URL
}, name='record_app')

# ==============================================================================
#   DATABASE REFERENCES
# ==============================================================================

# យោងតាមរូបភាពទី ២: Path គឺ 'students' (សម្រាប់មើល)
MASTER_REF = db.reference('students', app=master_app)

# យោងតាមរូបភាពទី ១: Path គឺ 'students' (សម្រាប់កត់ត្រា)
RECORD_REF = db.reference('students', app=record_app)


# ចាប់ផ្តើម BOT
bot = telebot.TeleBot(BOT_TOKEN)
user_data = {}

# ==============================================================================
#   BOT LOGIC
# ==============================================================================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        user_id = message.from_user.id
        
        # 1. ចាប់យកព័ត៌មាន Telegram ស្វ័យប្រវត្តិ
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name if message.from_user.last_name else ""
        full_telegram_name = f"{first_name} {last_name}".strip()
        
        telegram_link = f"https://t.me/{username}" if username else "No Link"
        username_text = f"@{username}" if username else "No Username"

        # 2. រក្សាទុកក្នុង Memory ជាបណ្តោះអាសន្ន
        user_data[user_id] = {
            "telegram_id": user_id,
            "telegram_name": full_telegram_name,
            "telegram_username": username_text,
            "telegram_link": telegram_link
        }

        msg = bot.reply_to(message, "❤️ **សូមស្វាគមន៍!**\n\nដើម្បីចុះឈ្មោះ សូមវាយបញ្ចូលអត្តលេខការងាររបស់ប្អូន៖", parse_mode="Markdown")
        bot.register_next_step_handler(msg, verify_student_id_from_master)
    except Exception as e:
        bot.reply_to(message, "មានបញ្ហាបច្ចេកទេស។ សូមប្អូនព្យាយាមម្តងទៀត។")

def verify_student_id_from_master(message):
    try:
        user_id = message.from_user.id
        input_id = message.text.strip()
        
        # ការពារករណីបាត់ Memory (Bot Restart)
        if user_id not in user_data:
             bot.reply_to(message, "⚠️ ទិន្នន័យបាត់បង់ សូមចុច /start ដើម្បីចាប់ផ្តើមឡើងវិញ។")
             return

        # ---------------------------------------------------------
        #  PHASE 1: SECURITY CHECK (ឆែកម្ចាស់គណនីក្នុង RECORD DB)
        # ---------------------------------------------------------
        existing_record = RECORD_REF.child(input_id).get()

        if existing_record:
            # បើមានទិន្នន័យចាស់ -> យក Telegram ID ចាស់មកផ្ទៀងផ្ទាត់
            registered_telegram_id = existing_record.get('telegram_id')
            
            # បើ ID មិនដូចគ្នា -> បិទការកែប្រែភ្លាម
            if str(registered_telegram_id) != str(user_id):
                error_text = (
                    f"⛔️ **មិនអនុញ្ញាតឱ្យកែប្រែ!**\n\n"
                    f"អត្តលេខ `{input_id}` នេះត្រូវបានចុះឈ្មោះដោយគណនី Telegram ផ្សេងរួចហើយ។\n"
                    "ប្អូនមិនអាចប្រើគណនីថ្មីមក Update ទិន្នន័យនេះបានទេ។\n\n"
                    "👉 **សូមទាក់ទង Admin ដើម្បីដោះស្រាយ។**"
                )
                bot.reply_to(message, error_text, parse_mode="Markdown")
                return # បញ្ចប់ (Stop)

        # ---------------------------------------------------------
        #  PHASE 2: VERIFICATION (ឆែកបញ្ជីឈ្មោះក្នុង MASTER DB)
        # ---------------------------------------------------------
        student_check = MASTER_REF.child(input_id).get()

        if student_check is None:
            # បើខុស: Loop សួរម្តងទៀត
            msg = bot.reply_to(message, f"❌ អត្តលេខ `{input_id}` មិនត្រឹមត្រូវទេ។\nសូមប្អូនព្យាយាមវាយ **អត្តលេខ** ម្តងទៀត៖", parse_mode="Markdown")
            bot.register_next_step_handler(msg, verify_student_id_from_master)
            return
        
        # ទាញយក field 'ឈ្មោះ' (តាមរូបភាពរបស់អ្នក)
        real_name_in_master = student_check.get('ឈ្មោះ') 
        
        if not real_name_in_master:
            msg = bot.reply_to(message, "❌ អត្តលេខនេះមានបញ្ហាបច្ចេកទេស (គ្មានឈ្មោះក្នុងបញ្ជី)។ សូមទាក់ទង Admin។")
            return

        # ត្រឹមត្រូវ -> រក្សាទុកក្នុង Memory
        user_data[user_id]['student_id'] = input_id
        user_data[user_id]['expected_name'] = real_name_in_master 
        
        msg = bot.reply_to(message, f"✅ អត្តលេខត្រឹមត្រូវ។\nសូមវាយបញ្ចូល **ឈ្មោះពេញជាភាសាខ្មែរ** របស់អ្នក៖")
        bot.register_next_step_handler(msg, verify_name_and_save)
            
    except Exception as e:
        msg = bot.reply_to(message, f"Error: {e}\nសូមវាយអត្តលេខម្តងទៀត៖")
        bot.register_next_step_handler(msg, verify_student_id_from_master)

def verify_name_and_save(message):
    try:
        user_id = message.from_user.id
        input_name = message.text.strip()
        
        if user_id not in user_data:
             bot.reply_to(message, "សូមចុច /start ម្តងទៀត។")
             return

        expected_name = user_data[user_id]['expected_name']

        # ---------------------------------------------------------
        #  PHASE 3: NAME VALIDATION (ផ្ទៀងផ្ទាត់ឈ្មោះ)
        # ---------------------------------------------------------
        if input_name != expected_name:
            # បើខុស: Loop សួរម្តងទៀត
            msg = bot.reply_to(message, 
                         f"❌ ឈ្មោះមិនត្រឹមត្រូវ!\n"         
                         f"ប្អូនបានវាយ៖ **{input_name}** \n\n"
                         "សូមវាយ **ឈ្មោះពេញជាភាសាខ្មែរ** របស់ប្អូនម្តងទៀតឱ្យបានត្រឹមត្រូវ៖", parse_mode="Markdown")
            bot.register_next_step_handler(msg, verify_name_and_save)
            return

        # ---------------------------------------------------------
        #  PHASE 4: SAVE TO RECORDING DB
        # ---------------------------------------------------------
        final_data = user_data[user_id]
        
        # លុប Field បណ្តោះអាសន្ន
        if 'expected_name' in final_data:
            del final_data['expected_name'] 
        
        # ដាក់ឈ្មោះដែលត្រឹមត្រូវចូល
        final_data['khmer_name'] = expected_name 
        student_key = final_data['student_id']
        
        # Save ដោយប្រើ អត្តលេខ ជា Key
        RECORD_REF.child(str(student_key)).set(final_data)
        
        response_text = (
            "✅ **❤️ចុះឈ្មោះបានជោគជ័យ!**\n\n"
            f"👤 ឈ្មោះ: {final_data['khmer_name']}\n"
            f"🆔 អត្តលេខ: {final_data['student_id']}\n"
            f"🔗 Telegram: {final_data['telegram_link']}\n\n"
            "ទិន្នន័យរបស់ប្អូនត្រូវបានកត់ត្រាទុកក្នុងប្រព័ន្ធ។ \n\n❤️សូមអរគុណសម្រាប់ផ្ដល់ព័ត៌មានរបស់ប្អូន!"
        )
        bot.send_message(message.chat.id, response_text, parse_mode="Markdown")
        
        # សម្អាត Memory
        del user_data[user_id]
        
    except Exception as e:
        bot.reply_to(message, f"បរាជ័យក្នុងការរក្សាទុក: {str(e)}")

# RUN BOT
print("Bot is running...")
bot.infinity_polling()
