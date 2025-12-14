import telebot
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import smtplib
import ssl
import random
import re
from email.message import EmailMessage

# ==============================================================================
#   1. ការកំណត់ (CONFIGURATION)
# ==============================================================================

BOT_TOKEN = '8284240201:AAFxNOZkvvSyrFma7J-zfAeXMj1aT5oeT9Q'

# Database URLs
MASTER_DB_URL = 'https://dilistname-default-rtdb.firebaseio.com/' 
RECORDING_DB_URL = 'https://itinfo-8501a-default-rtdb.firebaseio.com/' 

# --- EMAIL CONFIGURATION (ថ្មី) ---
# ដាក់ Email របស់អ្នកដែលត្រូវប្រើសម្រាប់ផ្ញើ OTP
SENDER_EMAIL = "perdigitalindustry@gmail.com" 
# ដាក់ App Password (16 ខ្ទង់) ដែលបានបង្កើតពី Google Account (មិនមែន Password ចូល Gmail ទេ)
SENDER_PASSWORD = "uhki vcie unle xgxq" 

# ==============================================================================
#   2. ការភ្ជាប់ FIREBASE (CONNECTION)
# ==============================================================================

if not firebase_admin._apps:
    # Master App
    try:
        master_app = firebase_admin.get_app('master_app')
    except ValueError:
        master_cred = credentials.Certificate("master_key.json")
        master_app = firebase_admin.initialize_app(master_cred, {
            'databaseURL': MASTER_DB_URL
        }, name='master_app')

    # Recording App
    try:
        record_app = firebase_admin.get_app('record_app')
    except ValueError:
        record_cred = credentials.Certificate("serviceAccountKey.json")
        record_app = firebase_admin.initialize_app(record_cred, {
            'databaseURL': RECORDING_DB_URL
        }, name='record_app')

# References
MASTER_REF = db.reference('students', app=master_app)
RECORD_REF = db.reference('students', app=record_app)

# Start Bot
bot = telebot.TeleBot(BOT_TOKEN)
user_data = {}

# ==============================================================================
#   3. HELPER FUNCTIONS (មុខងារជំនួយ)
# ==============================================================================

def is_valid_email(email):
    # ពិនិត្យទម្រង់ Email (Regex)
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email)

def send_otp_email(receiver_email, otp_code):
    try:
        subject = "លេខកូដផ្ទៀងផ្ទាត់ (OTP Code)"
        body = f"""
        សួស្តី!
        
        លេខកូដ OTP សម្រាប់ការចុះឈ្មោះរបស់អ្នកគឺ: {otp_code}
        
        សូមកុំចែករំលែកលេខកូដនេះទៅអ្នកផ្សេង។
        """
        
        em = EmailMessage()
        em['From'] = SENDER_EMAIL
        em['To'] = receiver_email
        em['Subject'] = subject
        em.set_content(body)

        context = ssl.create_default_context()
        
        # ផ្ញើ Email តាមរយៈ Gmail SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(em)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# ==============================================================================
#   4. BOT LOGIC
# ==============================================================================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        user_id = message.from_user.id
        
        # Capture Telegram Info
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

        msg = bot.reply_to(message, "❤️ **សូមស្វាគមន៍!**\n\nដើម្បីចុះឈ្មោះ សូមវាយបញ្ចូល **អត្តលេខ** (Student ID) របស់អ្នក៖", parse_mode="Markdown")
        bot.register_next_step_handler(msg, verify_student_id_from_master)
    except Exception as e:
        bot.reply_to(message, "មានបញ្ហាបច្ចេកទេស។ សូមព្យាយាមម្តងទៀត។")

def verify_student_id_from_master(message):
    try:
        user_id = message.from_user.id
        input_id = message.text.strip()
        
        if user_id not in user_data:
             bot.reply_to(message, "⚠️ ទិន្នន័យបាត់បង់ សូមចុច /start ដើម្បីចាប់ផ្តើមឡើងវិញ។")
             return

        # --- PHASE 1: Security Check ---
        existing_record = RECORD_REF.child(input_id).get()
        if existing_record:
            registered_telegram_id = existing_record.get('telegram_id')
            if str(registered_telegram_id) != str(user_id):
                bot.reply_to(message, "⛔️ **មិនអនុញ្ញាត!** អត្តលេខនេះមានម្ចាស់ហើយ។")
                msg = bot.send_message(message.chat.id, "🔄 **សូមវាយបញ្ចូលអត្តលេខផ្សេង៖**", parse_mode="Markdown")
                bot.register_next_step_handler(msg, verify_student_id_from_master) 
                return 

        # --- PHASE 2: Check Master DB ---
        student_check = MASTER_REF.child(input_id).get()

        if student_check is None:
            msg = bot.reply_to(message, f"❌ អត្តលេខ `{input_id}` មិនត្រឹមត្រូវទេ។\nសូមព្យាយាមវាយ **អត្តលេខ** ម្តងទៀត៖", parse_mode="Markdown")
            bot.register_next_step_handler(msg, verify_student_id_from_master)
            return
        
        real_name_in_master = student_check.get('ឈ្មោះ') 
        if not real_name_in_master:
            msg = bot.reply_to(message, "❌ អត្តលេខនេះមានបញ្ហាបច្ចេកទេស។ សូមទាក់ទង Admin។")
            return

        user_data[user_id]['student_id'] = input_id
        user_data[user_id]['expected_name'] = real_name_in_master 
        
        msg = bot.reply_to(message, f"✅ អត្តលេខត្រឹមត្រូវ។\nសូមវាយបញ្ចូល **ឈ្មោះពេញជាភាសាខ្មែរ** របស់អ្នក៖")
        bot.register_next_step_handler(msg, verify_name_step)
            
    except Exception as e:
        msg = bot.reply_to(message, f"⚠️ Error: {e}\nសូមព្យាយាមវាយអត្តលេខម្តងទៀត៖")
        bot.register_next_step_handler(msg, verify_student_id_from_master)

def verify_name_step(message):
    try:
        user_id = message.from_user.id
        input_name = message.text.strip()
        
        if user_id not in user_data:
             bot.reply_to(message, "សូមចុច /start ម្តងទៀត។")
             return

        expected_name = user_data[user_id]['expected_name']

        # --- PHASE 3: Name Validation ---
        if input_name != expected_name:
            msg = bot.reply_to(message, 
                         f"❌ ឈ្មោះមិនត្រឹមត្រូវ!\n"
                         f"អត្តលេខនេះត្រូវមានឈ្មោះ៖ **{expected_name}**\n"
                         "សូមវាយ **ឈ្មោះ** របស់អ្នកម្តងទៀត៖", parse_mode="Markdown")
            bot.register_next_step_handler(msg, verify_name_step)
            return
            
        # ឈ្មោះត្រូវហើយ -> ទៅជំហាន Email
        # Save correct name to memory
        user_data[user_id]['khmer_name'] = expected_name
        
        msg = bot.reply_to(message, "✅ ឈ្មោះត្រឹមត្រូវ។\n\n📧 **សូមវាយបញ្ចូល Email របស់អ្នកដើម្បីទទួលលេខកូដ OTP:**")
        bot.register_next_step_handler(msg, process_email_step)

    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

# --- ជំហានថ្មី: ទទួល Email និងផ្ញើ OTP ---
def process_email_step(message):
    try:
        user_id = message.from_user.id
        email = message.text.strip()

        if user_id not in user_data:
             bot.reply_to(message, "សូមចុច /start ម្តងទៀត។")
             return

        # 1. ពិនិត្យទម្រង់ Email
        if not is_valid_email(email):
            msg = bot.reply_to(message, "❌ **Email មិនត្រឹមត្រូវ!**\nសូមពិនិត្យមើលហើយវាយបញ្ចូល **Email** ម្តងទៀត៖", parse_mode="Markdown")
            bot.register_next_step_handler(msg, process_email_step)
            return

        # 2. បង្កើតលេខ OTP (6 ខ្ទង់)
        otp_code = str(random.randint(100000, 999999))
        
        # 3. ផ្ញើ Email
        bot.send_message(message.chat.id, "⏳ កំពុងផ្ញើលេខកូដ OTP ទៅកាន់ Email របស់អ្នក...")
        
        if send_otp_email(email, otp_code):
            # រក្សាទុក OTP និង Email ក្នុង Memory ដើម្បីផ្ទៀងផ្ទាត់
            user_data[user_id]['otp'] = otp_code
            user_data[user_id]['email'] = email
            
            msg = bot.reply_to(message, f"✅ លេខកូដ OTP ត្រូវបានផ្ញើទៅកាន់ `{email}`\n\n🔑 **សូមវាយបញ្ចូលលេខកូដ ៦ ខ្ទង់នោះនៅទីនេះ៖**", parse_mode="Markdown")
            bot.register_next_step_handler(msg, verify_otp_and_save)
        else:
            msg = bot.reply_to(message, "❌ បរាជ័យក្នុងការផ្ញើ Email។ សូមវាយបញ្ចូល Email ផ្សេងទៀត៖")
            bot.register_next_step_handler(msg, process_email_step)

    except Exception as e:
        bot.reply_to(message, f"Error Email Step: {e}")

# --- ជំហានចុងក្រោយ: ផ្ទៀងផ្ទាត់ OTP និង Save ---
def verify_otp_and_save(message):
    try:
        user_id = message.from_user.id
        input_otp = message.text.strip()
        
        if user_id not in user_data:
             bot.reply_to(message, "សូមចុច /start ម្តងទៀត។")
             return
        
        expected_otp = user_data[user_id].get('otp')
        
        # 1. ផ្ទៀងផ្ទាត់ OTP
        if input_otp != expected_otp:
            msg = bot.reply_to(message, "❌ **លេខកូដ OTP មិនត្រឹមត្រូវ!**\nសូមពិនិត្យក្នុង Email ហើយវាយបញ្ចូលម្តងទៀត៖", parse_mode="Markdown")
            bot.register_next_step_handler(msg, verify_otp_and_save)
            return
        
        # 2. OTP ត្រឹមត្រូវ -> Save ចូល Firebase
        final_data = user_data[user_id]
        
        # លុបព័ត៌មានមិនចាំបាច់ចេញ
        clean_keys = ['expected_name', 'otp']
        for key in clean_keys:
            if key in final_data:
                del final_data[key]
        
        student_key = final_data['student_id']
        
        # Save to Recording DB
        RECORD_REF.child(str(student_key)).set(final_data)
        
        response_text = (
            "🎉 **ចុះឈ្មោះបានជោគជ័យ!**\n\n"
            f"👤 ឈ្មោះ: {final_data['khmer_name']}\n"
            f"🆔 អត្តលេខ: {final_data['student_id']}\n"
            f"📧 Email: {final_data['email']}\n"
            f"🔗 Telegram: {final_data['telegram_link']}\n\n"
            "✅ ទិន្នន័យរបស់អ្នកត្រូវបានកត់ត្រាទុកក្នុងប្រព័ន្ធ។"
        )
        bot.send_message(message.chat.id, response_text, parse_mode="Markdown")
        
        # សម្អាត Memory
        del user_data[user_id]

    except Exception as e:
        bot.reply_to(message, f"Save Error: {e}")

# RUN BOT
print("Bot is running with Email Verification...")
bot.infinity_polling()
