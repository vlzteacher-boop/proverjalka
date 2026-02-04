from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Telegram Bot is running on Render with PostgreSQL!"

@app.route('/health')
def health():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
