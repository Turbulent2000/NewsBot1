import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.utils import executor
import feedparser
import sqlite3
from gtts import gTTS  # Для голосовых уведомлений
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import requests  # Для интеграции с новостными API

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Вставьте ваш токен
API_TOKEN = "7819794470:AAFzom825LhumYjjAhbxkAGFh5r0zD4n3ms"

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# RSS-ленты
RSS_FEEDS = {
    "BBC News": "http://feeds.bbci.co.uk/news/rss.xml",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "TechCrunch": "https://techcrunch.com/feed/",
    "Лента.ру": "https://lenta.ru/rss",
}

# Создание базы данных
conn = sqlite3.connect("users.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    keywords TEXT DEFAULT '',
    voice_enabled INTEGER DEFAULT 0
)
""")
conn.commit()

# Инициализация планировщика
scheduler = AsyncIOScheduler()

# Команда /start
@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    await message.reply(
        "Привет! Я бот новостей. Используй команды:\n"
        "/news — последние новости\n"
        "/add_keyword — добавить ключевое слово\n"
        "/keywords — показать ваши ключевые слова\n"
        "/enable_voice — включить голосовые уведомления\n"
        "/disable_voice — отключить голосовые уведомления\n"
        "/popular_news — топ-новости"
    )

# Функция: фильтрованные новости
@dp.message_handler(commands=["news"])
async def send_filtered_news(message: types.Message):
    cursor.execute("SELECT keywords FROM users WHERE user_id = ?", (message.from_user.id,))
    result = cursor.fetchone()
    keywords = result[0].split(",") if result and result[0] else []

    response = "📰 *Ваши новости:*\n\n"
    for source, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        response += f"📍 *{source}*\n"
        for entry in feed.entries[:5]:
            if not keywords or any(keyword.lower() in entry.title.lower() for keyword in keywords):
                response += f"- [{entry.title}]({entry.link})\n"
        response += "\n"
    await message.reply(response, parse_mode=ParseMode.MARKDOWN)

# Функция: добавить ключевое слово
@dp.message_handler(commands=["add_keyword"])
async def add_keyword(message: types.Message):
    keyword = message.get_args()
    if keyword:
        cursor.execute("SELECT keywords FROM users WHERE user_id = ?", (message.from_user.id,))
        result = cursor.fetchone()
        current_keywords = result[0] if result else ""
        new_keywords = f"{current_keywords},{keyword}" if current_keywords else keyword
        cursor.execute("UPDATE users SET keywords = ? WHERE user_id = ?", (new_keywords, message.from_user.id))
        conn.commit()
        await message.reply(f"Ключевое слово '{keyword}' добавлено!")
    else:
        await message.reply("Пожалуйста, укажите ключевое слово после команды.")

# Функция: включение голосовых уведомлений
@dp.message_handler(commands=["enable_voice"])
async def enable_voice(message: types.Message):
    cursor.execute("UPDATE users SET voice_enabled = 1 WHERE user_id = ?", (message.from_user.id,))
    conn.commit()
    await message.reply("Голосовые уведомления включены! Теперь новости будут отправляться голосом.")

# Функция: отключение голосовых уведомлений
@dp.message_handler(commands=["disable_voice"])
async def disable_voice(message: types.Message):
    cursor.execute("UPDATE users SET voice_enabled = 0 WHERE user_id = ?", (message.from_user.id,))
    conn.commit()
    await message.reply("Голосовые уведомления отключены.")

# Функция: топовые новости через сторонний API (пример на NewsAPI)
@dp.message_handler(commands=["popular_news"])
async def send_popular_news(message: types.Message):
    api_key = "ed2d6eaa94194ed28539ab41fe481f49"  # Зарегистрируйтесь на https://newsapi.org
    url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={api_key}"
    response = requests.get(url).json()
    
    if response.get("articles"):
        news = "🔥 *Топ-новости:*\n\n"
        for article in response["articles"][:5]:
            news += f"- [{article['title']}]({article['url']})\n"
        await message.reply(news, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply("Не удалось загрузить популярные новости. Попробуйте позже.")

# Автоматическая рассылка (с голосом)
async def send_daily_news():
    cursor.execute("SELECT user_id, keywords, voice_enabled FROM users")
    users = cursor.fetchall()
    for user_id, keywords, voice_enabled in users:
        keywords_list = keywords.split(",") if keywords else []
        response = "📰 *Ежедневные новости:*\n\n"
        for source, url in RSS_FEEDS.items():
            feed = feedparser.parse(url)
            response += f"📍 *{source}*\n"
            for entry in feed.entries[:3]:
                if not keywords_list or any(keyword.lower() in entry.title.lower() for keyword in keywords_list):
                    response += f"- {entry.title}\n{entry.link}\n"
            response += "\n"
        
        if voice_enabled:
            tts = gTTS(response, lang="ru")
            tts.save("daily_news.mp3")
            await bot.send_audio(user_id, audio=open("daily_news.mp3", "rb"))
        else:
            await bot.send_message(user_id, response, parse_mode=ParseMode.MARKDOWN)

scheduler.add_job(send_daily_news, "interval", hours=24)
scheduler.start()

# Запуск бота
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)