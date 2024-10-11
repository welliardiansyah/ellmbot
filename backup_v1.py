import logging
import os
import json
import random
import httpx
from gtts import gTTS
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from fuzzywuzzy import process
from nltk.stem import PorterStemmer
import re
from bs4 import BeautifulSoup
import sympy as sp

load_dotenv()

WELCOME_TEXT = "Selamat datang! Kirim pesan untuk memulai pertanyaan."
HELP_TEXT = "/start - Memulai percakapan\n/help - Menampilkan daftar perintah\n/about - Informasi tentang bot\n/feedback - Kirim feedback"
ABOUT_TEXT = "Saya adalah bot yang belajar dari percakapan Anda untuk memberikan jawaban dan saran yang lebih baik!"
FILTER_WORDS = ["kontol", "memek"]
BING_API_KEY = os.getenv("BING_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
QA_MODEL_FILE = "qa_model.json"
ADVICE_MODEL_FILE = "advice_model.json"
FILTER_WORDS_FILE = "filtered_words.json"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def load_model(filename):
    """Load model from a JSON file."""
    if os.path.exists(filename):
        with open(filename, "r", encoding='utf-8') as f:
            return json.load(f)
    return {}

qa_model = load_model(QA_MODEL_FILE)
advice_model = load_model(ADVICE_MODEL_FILE)
filter_words = load_model(FILTER_WORDS_FILE)
response_cache = {}
ps = PorterStemmer()

def contains_filtered_words(text: str) -> bool:
    """Check if the text contains any filtered words."""
    return any(word in text for word in filter_words)

async def save_model(filename, model):
    """Save model to a JSON file asynchronously."""
    with open(filename, "w", encoding='utf-8') as f:
        json.dump(model, f, ensure_ascii=False, indent=4)

async def add_filtered_word(word: str):
    """Add a new word to the filtered words list."""
    if word not in filter_words:
        filter_words.append(word)
        await save_model(FILTER_WORDS_FILE, filter_words)

def calculate(expression: str) -> str:
    """Calculate derivatives, integrals, or evaluate arithmetic expressions."""
    try:
        if "turun" in expression or "turunan" in expression:
            func_str = re.search(r'fungsi (.+)', expression)
            if not func_str:
                return "Silakan berikan format yang benar, misalnya: 'turunan fungsi x^2'."
            func_str = func_str.group(1).strip()
            x = sp.symbols('x')
            func = sp.sympify(func_str)
            derivative = sp.diff(func, x)
            return f"Turunan dari {func} adalah {derivative}"

        elif "integral" in expression:
            func_str = re.search(r'integral (.+)', expression)
            if not func_str:
                return "Silakan berikan format yang benar, misalnya: 'integral x^2'."
            func_str = func_str.group(1).strip()
            x = sp.symbols('x')
            func = sp.sympify(func_str)
            integral = sp.integrate(func, x)
            return f"Integral dari {func} adalah {integral}"

        # Evaluate basic arithmetic expressions
        expression = re.sub(r'[^\d+\-*/().]', '', expression)
        result = eval(expression)
        return str(result)

    except Exception as e:
        logger.error(f"Error calculating expression: {e}")
        return "Maaf, saya tidak dapat menghitung itu. Pastikan input Anda benar."

async def fetch_with_httpx(endpoint: str, params: dict, headers: dict) -> dict:
    """Fetch data using httpx for asynchronous requests."""
    async with httpx.AsyncClient() as client:
        response = await client.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

async def search_bing(query: str) -> str:
    """Perform a Bing search with results in Indonesian."""
    endpoint = "https://api.bing.microsoft.com/v7.0/search"
    
    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    params = {
        "q": query,
        "textDecorations": True,
        "textFormat": "HTML",
        "setLang": "id"
    }

    try:
        search_results = await fetch_with_httpx(endpoint, params, headers)
        if "webPages" in search_results and "value" in search_results["webPages"]:
            top_result = search_results["webPages"]["value"][0]
            raw_snippet = top_result["snippet"]
            cleaned_snippet = BeautifulSoup(raw_snippet, "html.parser").get_text()
            return cleaned_snippet
    except Exception as e:
        logger.error(f"Bing search error: {e}")
    return None

async def search_wikipedia(query: str) -> str:
    """Perform a Wikipedia search."""
    endpoint = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "utf8": 1,
        "srlimit": 1
    }

    try:
        search_results = await fetch_with_httpx(endpoint, params, {})
        if "query" in search_results and "search" in search_results["query"]:
            if search_results["query"]["search"]:
                page_snippet = search_results["query"]["search"][0]["snippet"]
                cleaned_snippet = BeautifulSoup(page_snippet, 'html.parser').get_text()
                return cleaned_snippet
    except Exception as e:
        logger.error(f"Wikipedia search error: {e}")
    return None

def filter_response(text: str) -> str:
    """Filter the response text for unwanted content."""
    if contains_filtered_words(text):
        return "Maaf, saya tidak dapat memberikan informasi tentang itu."
    return text

async def cached_search(query: str):
    """Cache responses from Bing and Wikipedia."""
    if query in response_cache:
        return response_cache[query]
    bing_response = await search_bing(query)
    wiki_response = await search_wikipedia(query)

    combined_response = bing_response or wiki_response
    response_cache[query] = combined_response
    return combined_response

async def match_response(user_query: str):
    """Match user query to a response from the QA model."""
    result = process.extractOne(user_query, qa_model.keys(), score_cutoff=70)
    if result:
        best_match, _ = result
        return best_match, random.choice(qa_model[best_match])
    return None, None

async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user queries."""
    user_query = update.message.text.lower().strip()
    user_id = update.message.from_user.id
    response = None

    user_query_count = context.user_data.setdefault(user_id, {})
    
    user_query_count[user_query] = user_query_count.get(user_query, 0) + 1

    REPEAT_THRESHOLD = 2

    if user_query_count[user_query] > REPEAT_THRESHOLD:
        await update.message.reply_text("Sepertinya Anda telah bertanya tentang itu beberapa kali. Mungkin Anda ingin mencoba pertanyaan lain?")
        return

    best_match, response = await match_response(user_query)
    if response:
        await update.message.reply_text(response)
        await send_voice_response(update, response)
    else:
        await handle_no_response(update, context, user_query)

async def handle_no_response(update: Update, context: ContextTypes.DEFAULT_TYPE, user_query: str):
    """Handle cases where no direct response is found."""
    if re.match(r'^[\d\s\+\-\*/().]+$|turun|integral', user_query):
        response = calculate(user_query)
        await update.message.reply_text(response)
        await send_voice_response(update, response)
        return

    response = await cached_search(user_query)
    if response:
        filtered_response = filter_response(response)
        await update.message.reply_text(filtered_response)
        await send_voice_response(update, filtered_response)
    else:
        await update.message.reply_text("Sepertinya saya tidak tahu jawaban untuk itu. Namun, saya akan berusaha belajar dari Anda.")
        context.user_data['learning_query'] = user_query

async def handle_learning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle learning from user input with feedback."""
    if 'learning_query' in context.user_data:
        user_query = context.user_data['learning_query']
        user_answer = update.message.text

        await update.message.reply_text(f"Apakah jawaban ini benar? (Ya/Tidak): {user_answer}")

        context.user_data['user_answer'] = user_answer
        context.user_data['expected_answer'] = user_query  # Save the original question

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user feedback on answers."""
    if 'user_answer' in context.user_data and 'expected_answer' in context.user_data:
        feedback = update.message.text.lower().strip()
        if feedback in ["ya", "tidak"]:
            user_query = context.user_data['expected_answer']
            user_answer = context.user_data['user_answer']

            if feedback == "ya":
                if user_query in qa_model:
                    qa_model[user_query].append(user_answer)
                else:
                    qa_model[user_query] = [user_answer]
                await save_model(QA_MODEL_FILE, qa_model)
                await update.message.reply_text("Saya telah belajar tentang: " + user_query + ". Terima kasih!")
            else:
                await update.message.reply_text("Terima kasih atas feedback! Saya akan berusaha lebih baik.")
            del context.user_data['user_answer']
            del context.user_data['expected_answer']
        else:
            await update.message.reply_text("Silakan jawab dengan 'Ya' atau 'Tidak'.")
    else:
        await update.message.reply_text("Saya belum meminta feedback.")

async def provide_advice(user_query: str) -> str:
    """Provide advice based on user query."""
    for keyword, advice in advice_model.items():
        if keyword in user_query:
            return advice
    return "Saya tidak memiliki saran untuk itu. Namun, saya akan berusaha belajar lebih banyak."

async def handle_advice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle requests for advice."""
    user_query = update.message.text.lower().strip()
    advice = await provide_advice(user_query)
    await update.message.reply_text(advice)

async def send_voice_response(update: Update, text: str) -> None:
    """Send a voice response to the user."""
    voice_file = "voice_response.ogg"
    try:
        text_to_speak = re.sub(r'http\S+|www\S+|https\S+', '', text).strip()
        if not text_to_speak:
            return
        tts = gTTS(text=text_to_speak, lang='id')
        tts.save(voice_file)
        with open(voice_file, 'rb') as voice:
            await update.message.reply_voice(voice=voice)
    except Exception as e:
        logger.error(f"Error sending voice message: {e}")
    finally:
        if os.path.exists(voice_file):
            os.remove(voice_file)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command handler."""
    keyboard = [
        [KeyboardButton("/help"), KeyboardButton("/about")],
        [KeyboardButton("/feedback")]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    await update.message.reply_text(WELCOME_TEXT, reply_markup=reply_markup)
    await send_voice_response(update, WELCOME_TEXT)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help command handler."""
    await update.message.reply_text(HELP_TEXT)
    await send_voice_response(update, HELP_TEXT)

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """About command handler."""
    await update.message.reply_text(ABOUT_TEXT)
    await send_voice_response(update, ABOUT_TEXT)

def main() -> None:
    """Main entry point for the bot."""
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("feedback", handle_feedback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_learning))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_advice))

    application.run_polling()

if __name__ == '__main__':
    main()
