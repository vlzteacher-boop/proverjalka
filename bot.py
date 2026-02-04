import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

# ====== НАСТРОЙКИ ЛОГИРОВАНИЯ ======
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ====== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ======
TOKEN = os.environ.get('TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '-1003810095854')
DATABASE_URL = os.environ.get('DATABASE_URL')

if not TOKEN:
    logger.error("❌ Токен не найден! Добавьте TOKEN в Render")
    exit(1)

if not DATABASE_URL:
    logger.error("❌ DATABASE_URL не найден! Добавьте PostgreSQL в Render")
    exit(1)

# ====== БАЗА ДАННЫХ POSTGRESQL ======
def get_connection():
    """Создать подключение к PostgreSQL"""
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    """Инициализация базы данных"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS works (
            id SERIAL PRIMARY KEY,
            date TEXT NOT NULL,
            class TEXT NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            student_count INTEGER NOT NULL,
            total_students INTEGER NOT NULL,
            submitted_students TEXT,
            absent_students TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ PostgreSQL база данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")

# ====== БАЗА УЧЕНИКОВ ======
STUDENTS_DATABASE = {
    "7": ["Ваня А.", "Ангелина Гр.", "Ангелина Гт.", "Платон", "Миша", "Лев", "Ваня Ч."],
    "5": ["Алиса", "Джулия", "Ульяна", "Башир", "Ваня", "Вова"],
    "8": ["Диана", "Полина", "Настя", "Влада", "Амалия", "Соня", "Лиза", "Никита", "Роберт", "Егор", "Ульяна", "Стас"],
    "10": ["Денис", "Амелия", "Макар", "Яна", "Ева"]
}

# ====== КОМАНДА /START (минимальная) ======
def start(update: Update, context: CallbackContext):
    """Команда /start - главное меню"""
    keyboard = [
        [InlineKeyboardButton("➕ Создать работу", callback_data='create')],
        [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
        [InlineKeyboardButton("📋 Список работ", callback_data='list')],
        [InlineKeyboardButton("✅ Отметить проверку", callback_data='check_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "📚 *Бот для проверки работ*\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ====== КОМАНДА /CHECK ======
def check_command(update: Update, context: CallbackContext):
    """Команда /check"""
    if not context.args:
        update.message.reply_text("Используйте: `/check 1`", parse_mode='Markdown')
        return
    
    try:
        work_id = int(context.args[0])
        update.message.reply_text(f"✅ Работа #{work_id} отмечена как проверенная!")
    except:
        update.message.reply_text("❌ Ошибка. Используйте: `/check 1`")

# ====== ОБРАБОТЧИК КНОПОК (упрощенный) ======
def button_handler(update: Update, context: CallbackContext):
    """Обработка кнопок"""
    query = update.callback_query
    query.answer()
    
    if query.data == 'create':
        show_classes(query)
    elif query.data == 'summary':
        show_summary(query)
    elif query.data == 'list':
        show_list(query)
    elif query.data == 'check_menu':
        show_check_menu(query)

def show_classes(query):
    """Показать выбор класса"""
    keyboard = [
        [InlineKeyboardButton("5 класс", callback_data='class_5')],
        [InlineKeyboardButton("7 класс", callback_data='class_7')],
        [InlineKeyboardButton("8 класс", callback_data='class_8')],
        [InlineKeyboardButton("10 класс", callback_data='class_10')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text("Выберите класс:", reply_markup=reply_markup)

def show_summary(query):
    """Показать сводку"""
    query.edit_message_text("📊 *Сводка*\n\nРабот на проверке: 0\nПроверено: 0", parse_mode='Markdown')

def show_list(query):
    """Показать список работ"""
    query.edit_message_text("📋 *Список работ*\n\nНет работ на проверке", parse_mode='Markdown')

def show_check_menu(query):
    """Меню проверки"""
    query.edit_message_text("✅ Используйте команду: `/check 1`", parse_mode='Markdown')

# ====== ЗАПУСК БОТА ======
def run_bot():
    """Функция запуска бота"""
    # Инициализация БД
    init_db()
    
    # Создаем Updater
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Регистрируем обработчики
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("check", check_command))
    dp.add_handler(CallbackQueryHandler(button_handler))
    
    # Запускаем бота
    logger.info("🤖 Telegram бот запущен!")
    updater.start_polling()
    updater.idle()
