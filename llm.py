import logging
import os
import json
import random
import requests
from gtts import gTTS
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from fuzzywuzzy import process
from nltk.stem import PorterStemmer
import re
from bs4 import BeautifulSoup
import sympy as sp  # Impor pustaka sympy

# Load environment variables
load_dotenv()

WELCOME_TEXT = "Selamat datang! Kirim pesan untuk memulai pertanyaan."
HELP_TEXT = "/start - Memulai percakapan\n/help - Menampilkan daftar perintah"
ABOUT_TEXT = "Saya adalah bot yang belajar dari percakapan Anda untuk memberikan jawaban dan saran yang lebih baik!"

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load models
def load_qa_model():
    if os.path.exists("qa_model.json"):
        with open("qa_model.json", "r") as f:
            return json.load(f)
    return {}

def load_pantun_model():
    if os.path.exists("pantun_model.json"):
        with open("pantun_model.json", "r") as f:
            return json.load(f)
    return {}

def load_advice_model():
    if os.path.exists("advice_model.json"):
        with open("advice_model.json", "r") as f:
            return json.load(f)
    return {}

qa_model = load_qa_model()
pantun_model = load_pantun_model()
advice_model = load_advice_model()

user_query_count = {}
FILTER_WORDS = ["kontol", "memek"]
ps = PorterStemmer()  # Initialize the stemmer

# Check for filtered words
def contains_filtered_words(text: str) -> bool:
    return any(word in text for word in FILTER_WORDS)

# Stem user query for better matching
def stem_query(query: str) -> str:
    return ' '.join([ps.stem(word) for word in query.split()])

# Extract keywords from user query
def extract_keywords(query: str) -> list:
    return query.split()  # Simple space-based extraction

# Save updated QA model
def save_qa_model(model):
    with open("qa_model.json", "w") as f:
        json.dump(model, f, ensure_ascii=False, indent=4)

# Function to evaluate mathematical expressions, including calculus
def calculate(expression: str) -> str:
    try:
        # Detect if the user wants to perform calculus operations
        if "turun" in expression or "turunan" in expression:
            # Ambil fungsi dan variabel
            func_str = re.search(r'fungsi (.+)', expression).group(1).strip()
            x = sp.symbols('x')
            func = sp.sympify(func_str)
            derivative = sp.diff(func, x)
            return f"Turunan dari {func} adalah {derivative}"
        
        elif "integral" in expression:
            # Ambil fungsi
            func_str = re.search(r'integral (.+)', expression).group(1).strip()
            x = sp.symbols('x')
            func = sp.sympify(func_str)
            integral = sp.integrate(func, x)
            return f"Integral dari {func} adalah {integral}"

        # Remove any unwanted characters and spaces for basic calculations
        expression = re.sub(r'[^\d+\-*/().]', '', expression)
        result = eval(expression)
        return str(result)
    
    except Exception as e:
        logger.error(f"Error calculating expression: {e}")
        return "Maaf, saya tidak dapat menghitung itu."

# Fungsi untuk mencari di Bing
async def search_bing(query: str) -> str:
    api_key = os.getenv("BING_API_KEY")
    endpoint = "https://api.bing.microsoft.com/v7.0/search"
    
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    params = {"q": query, "textDecorations": True, "textFormat": "HTML"}

    response = requests.get(endpoint, headers=headers, params=params)
    if response.status_code == 200:
        search_results = response.json()
        if "webPages" in search_results and "value" in search_results["webPages"]:
            top_result = search_results["webPages"]["value"][0]
            raw_snippet = top_result["snippet"]
            cleaned_snippet = BeautifulSoup(raw_snippet, "html.parser").get_text()
            return cleaned_snippet  # Mengembalikan cuplikan yang sudah dibersihkan
    return None

# Fungsi untuk mencari di Wikipedia
async def search_wikipedia(query: str) -> str:
    endpoint = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "utf8": 1,
        "srlimit": 1  # Ambil hanya satu hasil
    }

    response = requests.get(endpoint, params=params)
    if response.status_code == 200:
        search_results = response.json()
        if "query" in search_results and "search" in search_results["query"]:
            if search_results["query"]["search"]:
                page_title = search_results["query"]["search"][0]["title"]
                page_snippet = search_results["query"]["search"][0]["snippet"]
                return f"{page_title}: {BeautifulSoup(page_snippet, 'html.parser').get_text()}"  # Mengembalikan judul dan cuplikan
    return None

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [KeyboardButton("/help"), KeyboardButton("/about")],
        [KeyboardButton("/feedback")]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    await update.message.reply_text(WELCOME_TEXT, reply_markup=reply_markup)
    await send_voice_response(update, WELCOME_TEXT)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)
    await send_voice_response(update, HELP_TEXT)

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(ABOUT_TEXT)
    await send_voice_response(update, ABOUT_TEXT)

async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_feedback = " ".join(context.args)
    logger.info(f"Feedback from {update.message.from_user.id}: {user_feedback}")
    await update.message.reply_text("Terima kasih atas feedback Anda!")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await handle_text_message(update, context)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_query = update.message.text.lower().strip()
    user_id = update.message.from_user.id
    response = None

    user_query_count.setdefault(user_id, {})
    user_query_count[user_id][user_query] = user_query_count[user_id].get(user_query, 0) + 1

    # Pertama, cari di model QA
    result = process.extractOne(user_query, qa_model.keys(), score_cutoff=70)
    if result:
        best_match, score = result
        response = random.choice(qa_model[best_match])
    else:
        # Jika tidak ada hasil, cari di Bing
        bing_response = await search_bing(user_query)
        if bing_response:
            response = bing_response
        else:
            # Jika tidak ada hasil dari Bing, cari di Wikipedia
            wiki_response = await search_wikipedia(user_query)
            if wiki_response:
                response = wiki_response
            else:
                response = "Sepertinya saya tidak tahu jawaban untuk itu. Namun, saya akan berusaha belajar dari Anda."
                context.user_data['learning_query'] = user_query  # Simpan kueri untuk pembelajaran

    # Periksa apakah ini adalah ekspresi matematis
    if re.match(r'^[\d\s\+\-\*/().]+$|turun|integral', user_query):
        response = calculate(user_query)

    if contains_filtered_words(response):
        response = "Maaf, saya tidak dapat memberikan informasi tentang itu."

    await update.message.reply_text(response)
    await send_voice_response(update, response)

    if response.startswith("Sepertinya saya tidak tahu jawaban untuk itu."):
        await update.message.reply_text("Silakan kirim jawaban Anda untuk mengajarkan saya.")

async def handle_learning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if 'learning_query' in context.user_data:
        user_query = context.user_data['learning_query']
        user_answer = update.message.text

        qa_model[user_query] = [user_answer]
        save_qa_model(qa_model)

        await update.message.reply_text(f"Saya telah belajar tentang: {user_query}. Terima kasih!")
        del context.user_data['learning_query']

async def provide_advice(user_query: str) -> str:
    for keyword, advice in advice_model.items():
        if keyword in user_query:
            return advice
    return "Saya tidak memiliki saran untuk itu. Namun, saya akan berusaha belajar lebih banyak."

async def handle_advice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_query = update.message.text.lower().strip()
    advice = await provide_advice(user_query)
    await update.message.reply_text(advice)

async def send_voice_response(update: Update, text: str) -> None:
    voice_file = "voice_response.ogg"
    try:
        tts = gTTS(text=text, lang='id')
        tts.save(voice_file)
        with open(voice_file, 'rb') as voice:
            await update.message.reply_voice(voice=voice)
    except Exception as e:
        logger.error(f"Error sending voice message: {e}")
    finally:
        if os.path.exists(voice_file):
            os.remove(voice_file)

def main() -> None:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    application = ApplicationBuilder().token(bot_token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("feedback", feedback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_learning))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_advice))

    application.run_polling()

if __name__ == '__main__':
    main()
