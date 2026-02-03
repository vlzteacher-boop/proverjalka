from flask import Flask
import os
import threading
import logging

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Telegram Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

def run_bot():
    """Запуск бота в отдельном потоке"""
    try:
        from bot import main
        main()
    except Exception as e:
        logging.error(f"Bot error: {e}")

if __name__ == "__main__":
    # Запускаем бот в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем Flask сервер
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)