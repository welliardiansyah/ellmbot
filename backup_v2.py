import logging
import os
import json
import httpx
from gtts import gTTS
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import re
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression
import pickle
import asyncio
import random

load_dotenv()

WELCOME_TEXT = "Selamat datang! Kirim pesan untuk memulai percakapan. 😊"
HELP_TEXT = "/start - Memulai percakapan\n/help - Menampilkan daftar perintah\n/about - Informasi tentang bot\n/feedback - Kirim feedback\n/topics - Lihat topik yang sudah dibahas"
ABOUT_BOT = "Saya adalah bot yang dirancang untuk membantu Anda dengan berbagai pertanyaan. 🤖"
ABOUT_CREATOR = "Saya dibuat oleh Welli Ardiansyah."
FILTER_WORDS_FILE = "filtered_words.json"
RESPONSE_MODEL_FILE = "responses.json"
TRAINING_DATA_FILE = "training_data.json"
BING_API_KEY = os.getenv("BING_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

responses = {}
filter_words = []
user_context = {}
training_data = []
models = {}
vectorizers = {}

def load_responses():
    if os.path.exists(RESPONSE_MODEL_FILE):
        with open(RESPONSE_MODEL_FILE, "r", encoding='utf-8') as f:
            data = f.read().strip()
            if data:
                return json.loads(data)
    return {}

responses = load_responses()

def load_filter_words():
    if os.path.exists(FILTER_WORDS_FILE):
        with open(FILTER_WORDS_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    return []

filter_words = load_filter_words()

def load_training_data():
    if os.path.exists(TRAINING_DATA_FILE):
        with open(TRAINING_DATA_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    return []

training_data = load_training_data()

def save_training_data():
    with open(TRAINING_DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(training_data, f, ensure_ascii=False, indent=4)

def contains_filtered_words(text: str) -> bool:
    return any(word in text for word in filter_words)

async def calculate(expression: str) -> str:
    try:
        expression = re.sub(r'[^\d+\-*/().]', '', expression)
        result = eval(expression)
        return str(result)
    except Exception as e:
        logger.error(f"Kesalahan menghitung ekspresi: {e}")
        return "Maaf, saya tidak dapat menghitung itu. Pastikan input Anda benar."

async def fetch_with_httpx(endpoint: str, params: dict, headers: dict, timeout: int = 5) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

async def search_bing(query: str) -> str:
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
    except httpx.ReadTimeout:
        logger.error("Pencarian Bing memakan waktu terlalu lama.")
    except Exception as e:
        logger.error(f"Kesalahan pencarian Bing: {e}")
    return None

async def search_wikipedia(query: str) -> str:
    endpoint = "https://id.wikipedia.org/w/api.php"
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
    except httpx.ReadTimeout:
        logger.error("Pencarian Wikipedia memakan waktu terlalu lama.")
    except Exception as e:
        logger.error(f"Kesalahan pencarian Wikipedia: {e}")
    return None

async def update_training_data(user_query: str, response: str):
    training_data.append({"query": user_query, "response": response})
    save_training_data()

async def train_model():
    if training_data:
        vectorizer = TfidfVectorizer()
        X = vectorizer.fit_transform([data["query"] for data in training_data])
        y = [data["response"] for data in training_data]

        models = {
            'naive_bayes': MultinomialNB(),
            'logistic_regression': LogisticRegression(max_iter=1000)
        }
        
        for model_name, model in models.items():
            model.fit(X, y)
            with open(f"{model_name}.pkl", "wb") as model_file:
                pickle.dump(model, model_file)
            with open(f"{model_name}_vectorizer.pkl", "wb") as vector_file:
                pickle.dump(vectorizer, vector_file)

async def load_models():
    global models, vectorizers
    models = {}
    vectorizers = {}
    
    for model_name in ['naive_bayes', 'logistic_regression']:
        with open(f"{model_name}.pkl", "rb") as model_file:
            models[model_name] = pickle.load(model_file)
        with open(f"{model_name}_vectorizer.pkl", "rb") as vector_file:
            vectorizers[model_name] = pickle.load(vector_file)

def generate_follow_up_question(user_query: str) -> str:
    if "apa" in user_query:
        return "Bisa jelaskan lebih lanjut tentang apa yang Anda maksud?"
    elif "kenapa" in user_query:
        return "Apa yang membuat Anda penasaran tentang itu?"
    elif "siapa" in user_query:
        return "Apakah Anda merujuk kepada seseorang atau sesuatu yang spesifik?"
    elif "bagaimana" in user_query:
        return "Bagaimana perasaan Anda tentang itu?"
    return ""

def generate_topic_suggestions() -> list:
    topics = [
        "Kesehatan mental",
        "Inovasi teknologi",
        "Seni dan budaya",
        "Perubahan iklim",
        "Sejarah dunia",
        "Pendidikan di era digital",
        "Ekonomi global",
        "Olahraga dan kebugaran",
        "Wisata dan petualangan",
        "Makanan dan kuliner",
        "Kecerdasan buatan",
        "Etika dalam teknologi",
        "Tren mode saat ini",
        "Masyarakat dan budaya",
        "Literatur klasik"
    ]
    return random.sample(topics, 3)

def generate_custom_topic_suggestions(user_preferences: list) -> list:
    available_topics = [
        "Kesehatan mental",
        "Inovasi teknologi",
        "Seni dan budaya",
        "Perubahan iklim",
        "Sejarah dunia",
        "Pendidikan di era digital",
        "Ekonomi global",
        "Olahraga dan kebugaran",
        "Wisata dan petualangan",
        "Makanan dan kuliner",
        "Kecerdasan buatan",
        "Etika dalam teknologi",
        "Tren mode saat ini",
        "Masyarakat dan budaya",
        "Literatur klasik"
    ]
    return random.sample([topic for topic in available_topics if topic in user_preferences], 3)

async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_query = update.message.text.lower().strip()
    
    if contains_filtered_words(user_query):
        await update.message.reply_text("Maaf, saya tidak dapat memberikan informasi tentang itu.")
        return

    response = None

    if re.match(r'^[\d\s+\-*/().]+$', user_query):
        response = await calculate(user_query)
    elif "siapa kamu" in user_query or "apa itu" in user_query:
        response = ABOUT_BOT
    elif "siapa penciptamu" in user_query or "siapa yang membuatmu" in user_query:
        response = ABOUT_CREATOR
    elif "apa kabar" in user_query or "bagaimana kabarmu" in user_query:
        response = "Saya baik-baik saja, terima kasih! Bagaimana dengan Anda?"
    elif "cinta" in user_query or "suka" in user_query:
        response = "Cinta adalah emosi yang mendalam. Apakah Anda memiliki pengalaman yang ingin dibagikan?"
    elif "musik" in user_query:
        response = "Musik adalah bagian penting dari budaya kita. Jenis musik apa yang Anda suka?"
    elif "film" in user_query:
        response = "Film bisa menjadi pengalaman yang menghibur. Apa film terakhir yang Anda tonton?"
    elif "cuaca" in user_query:
        response = "Cuaca bisa sangat berpengaruh pada suasana hati. Anda ingin tahu tentang cuaca di mana?"
    elif "makanan" in user_query:
        response = "Makanan adalah bagian penting dari kehidupan. Apa makanan favorit Anda?"
    elif "teknologi" in user_query:
        response = "Teknologi terus berkembang. Apa yang terbaru yang Anda dengar?"
    else:
        bing_response = await search_bing(user_query)
        wiki_response = await search_wikipedia(user_query)
        response = bing_response or wiki_response

        if response:
            await update_training_data(user_query, response)
            await train_model()  # Train the model with new data
        else:
            response = "Maaf, saya tidak tahu jawaban untuk itu. Bisakah Anda memberi tahu saya lebih lanjut?"

    await update.message.reply_text(f"\n{response}")
    follow_up_question = generate_follow_up_question(user_query)
    if follow_up_question:
        await update.message.reply_text(follow_up_question)

    # Get user preferences from context
    user_preferences = context.user_data.get('preferences', [])
    if user_preferences:
        topic_suggestions = generate_custom_topic_suggestions(user_preferences)
    else:
        topic_suggestions = generate_topic_suggestions()
        
    await update.message.reply_text(f"Coba diskusikan topik ini: {', '.join(topic_suggestions)}")

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    feedback = update.message.text.lower().strip()
    if feedback in ["ya", "tidak"]:
        if feedback == "ya":
            await update.message.reply_text("Terima kasih atas feedback! Saya senang jawaban saya membantu. 😊")
        else:
            last_query = context.user_data.get('last_query', "pertanyaan yang Anda ajukan")
            await update.message.reply_text(f"Maaf jika jawaban saya tidak membantu untuk '{last_query}'. Saya akan berusaha lebih baik. 😊")
    else:
        await update.message.reply_text("Silakan jawab dengan 'ya' atau 'tidak'.")

async def send_voice_response(update: Update, text: str) -> None:
    voice_file = "voice_response.ogg"
    try:
        tts = gTTS(text=text, lang='id')
        tts.save(voice_file)
        with open(voice_file, 'rb') as voice:
            await update.message.reply_voice(voice=voice)
    except Exception as e:
        logger.error(f"Kesalahan mengirim pesan suara: {e}")
    finally:
        if os.path.exists(voice_file):
            os.remove(voice_file)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [KeyboardButton("/help"), KeyboardButton("/about")],
        [KeyboardButton("/feedback"), KeyboardButton("/topics")]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    await update.message.reply_text(WELCOME_TEXT, reply_markup=reply_markup)
    await send_voice_response(update, WELCOME_TEXT)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)
    await send_voice_response(update, HELP_TEXT)

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(ABOUT_BOT)
    await send_voice_response(update, ABOUT_BOT)

async def suggest_topics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    topics = [data["query"] for data in training_data]
    if topics:
        await update.message.reply_text("Topik yang sudah dibahas: " + ", ".join(topics))
    else:
        await update.message.reply_text("Belum ada topik yang dibahas.")

async def periodic_training():
    while True:
        await asyncio.sleep(3600)
        await train_model()

def main() -> None:
    global models, vectorizers
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Create an event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Load models in the loop
    loop.run_until_complete(load_models())

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("feedback", handle_feedback))
    application.add_handler(CommandHandler("topics", suggest_topics))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_query))

    # Create periodic training task
    loop.create_task(periodic_training())

    application.run_polling()

if __name__ == '__main__':
    main()

