import os
import threading
import time
from flask import Flask
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Telegram Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

def start_bot():
    """Запуск Telegram бота в отдельном потоке"""
    # Даем время на запуск Flask
    time.sleep(2)
    
    try:
        from bot import run_bot
        logger.info("🚀 Запуск Telegram бота...")
        run_bot()
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")

# Запускаем бот в отдельном потоке при старте Flask
if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    # Это предотвращает двойной запуск в режиме разработки
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    logger.info("📱 Telegram бот запускается в фоне...")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
