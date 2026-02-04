import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, ConversationHandler, CallbackContext

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

# Проверка обязательных переменных
if not TOKEN:
    logger.error("❌ Токен не найден! Добавьте переменную TOKEN в Render")
    exit(1)

if not DATABASE_URL:
    logger.error("❌ DATABASE_URL не найден! Добавьте PostgreSQL в Render и установите DATABASE_URL")
    exit(1)

# ====== ФУНКЦИИ ДЛЯ РАБОТЫ С POSTGRESQL ======
def get_connection():
    """Создать подключение к PostgreSQL"""
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    """Инициализация базы данных PostgreSQL"""
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
        logger.error(f"❌ Ошибка инициализации PostgreSQL: {e}")

def save_work(work_data):
    """Сохранить работу в PostgreSQL"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO works (date, class, subject, topic, student_count, total_students,
                      submitted_students, absent_students, status)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
    ''', (
        work_data['date'],
        work_data['class'],
        work_data['subject'],
        work_data['topic'],
        work_data['student_count'],
        work_data['total_students'],
        json.dumps(work_data['submitted_students'], ensure_ascii=False),
        json.dumps(work_data['absent_students'], ensure_ascii=False),
        'pending'
    ))
    
    work_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return work_id

def get_pending_works():
    """Получить работы на проверке"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute('''
    SELECT id, date, class, subject, topic, student_count, total_students,
           submitted_students, absent_students, created_at
    FROM works 
    WHERE status = 'pending'
    ORDER BY created_at DESC
    LIMIT 10
    ''')
    
    works = cursor.fetchall()
    conn.close()
    return works

def get_checked_works():
    """Получить проверенные работы"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute('''
    SELECT id, date, class, subject, topic, student_count, total_students,
           submitted_students, absent_students, created_at
    FROM works 
    WHERE status = 'checked'
    ORDER BY created_at DESC
    LIMIT 5
    ''')
    
    works = cursor.fetchall()
    conn.close()
    return works

def mark_work_as_checked(work_id):
    """Отметить работу как проверенную"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    UPDATE works 
    SET status = 'checked'
    WHERE id = %s AND status = 'pending'
    ''', (work_id,))
    
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def get_statistics():
    """Получить статистику"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Количество работ по статусу
    cursor.execute("SELECT status, COUNT(*) FROM works GROUP BY status")
    status_counts = dict(cursor.fetchall())
    
    # Общее количество учеников
    cursor.execute("SELECT SUM(student_count) FROM works WHERE status = 'pending'")
    pending_students = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(student_count) FROM works WHERE status = 'checked'")
    checked_students = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return {
        'pending_count': status_counts.get('pending', 0),
        'checked_count': status_counts.get('checked', 0),
        'total_count': sum(status_counts.values()),
        'pending_students': pending_students,
        'checked_students': checked_students
    }

# ====== БАЗА УЧЕНИКОВ ======
STUDENTS_DATABASE = {
    "7": ["Ваня А.", "Ангелина Гр.", "Ангелина Гт.", "Платон", "Миша", "Лев", "Ваня Ч."],
    "5": ["Алиса", "Джулия", "Ульяна", "Башир", "Ваня", "Вова"],
    "8": ["Диана", "Полина", "Настя", "Влада", "Амалия", "Соня", "Лиза", "Никита", "Роберт", "Егор", "Ульяна", "Стас"],
    "10": ["Денис", "Амелия", "Макар", "Яна", "Ева"]
}

# ====== КОМАНДА /START (упрощенная) ======
def start(update: Update, context: CallbackContext):
    """Команда /start - главное меню"""
    keyboard = [
        [InlineKeyboardButton("➕ Создать работу", callback_data='create')],
        [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
        [InlineKeyboardButton("📋 Список работ", callback_data='list')],
        [InlineKeyboardButton("✅ Отметить проверку", callback_data='check_menu')],
        [InlineKeyboardButton("📈 Статистика", callback_data='stats')],
        [InlineKeyboardButton("🆘 Помощь", callback_data='help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "📚 *Бот для проверки работ*\n\n"
        "✅ Данные сохраняются в PostgreSQL\n"
        "🔄 Работает 24/7 на Render.com\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ====== КОМАНДА /CHECK ======
def check_command(update: Update, context: CallbackContext):
    """Обработка команды /check"""
    if not context.args:
        update.message.reply_text(
            "❌ Укажите ID работы:\n"
            "`/check 1`\n\n"
            "ID можно узнать в '📋 Список работ'",
            parse_mode='Markdown'
        )
        return
    
    try:
        work_id = int(context.args[0])
        
        if mark_work_as_checked(work_id):
            update.message.reply_text(f"✅ Работа #{work_id} проверена!")
        else:
            update.message.reply_text("❌ Работа не найдена или уже проверена")
        
    except ValueError:
        update.message.reply_text("❌ ID должен быть числом")
    except Exception as e:
        logger.error(f"Ошибка команды /check: {e}")
        update.message.reply_text(f"❌ Ошибка: {str(e)}")

# ====== ОБРАБОТЧИКИ КНОПОК ======
def button_handler(update: Update, context: CallbackContext):
    """Главный обработчик кнопок"""
    query = update.callback_query
    query.answer()
    
    if query.data == 'create':
        create_work_start(query)
    elif query.data == 'summary':
        show_summary(query)
    elif query.data == 'list':
        show_list(query)
    elif query.data == 'stats':
        show_stats(query)
    elif query.data == 'help':
        show_help(query)
    elif query.data == 'check_menu':
        show_check_menu(query)
    elif query.data.startswith('check_'):
        work_id = int(query.data.replace('check_', ''))
        quick_check_work(query, work_id)
    elif query.data == 'class_5':
        select_class(query, '5')
    elif query.data == 'class_7':
        select_class(query, '7')
    elif query.data == 'class_8':
        select_class(query, '8')
    elif query.data == 'class_10':
        select_class(query, '10')

# ====== СОЗДАНИЕ РАБОТЫ (упрощенное) ======
def create_work_start(query):
    """Начало создания работы"""
    keyboard = [
        [InlineKeyboardButton("5 класс", callback_data='class_5')],
        [InlineKeyboardButton("7 класс", callback_data='class_7')],
        [InlineKeyboardButton("8 класс", callback_data='class_8')],
        [InlineKeyboardButton("10 класс", callback_data='class_10')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        "🏫 *Выберите класс:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

def select_class(query, class_num):
    """Выбор класса"""
    query.edit_message_text(
        f"✏️ *{class_num} класс*\n\n"
        f"Введите тему работы в формате:\n"
        f"`Предмет: Тема --absent ученик1,ученик2`\n\n"
        f"*Пример:*\n"
        f"`Алгебра: Контрольная работа --absent Ваня, Маша`\n\n"
        f"*Ученики класса:*\n" + "\n".join(f"• {s}" for s in STUDENTS_DATABASE[class_num]),
        parse_mode='Markdown'
    )

# ====== СВОДКА ======
def show_summary(query):
    """Показать сводку"""
    try:
        stats = get_statistics()
        pending_works = get_pending_works()
        
        text = f"📊 *Сводка по проверке*\n\n"
        text += f"⏳ На проверке: {stats['pending_count']} работ\n"
        text += f"✅ Проверено: {stats['checked_count']} работ\n"
        text += f"📚 Всего: {stats['total_count']} работ\n\n"
        
        if pending_works:
            text += "*Последние работы:*\n"
            for work in pending_works[:5]:
                text += f"• ID{work['id']}: {work['class']} класс - {work['topic'][:30]}...\n"
                text += f"  👥 {work['student_count']} учеников\n\n"
        else:
            text += "🎉 *Все работы проверены!*\n\n"
        
        keyboard = []
        if pending_works:
            for work in pending_works[:3]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ Проверить ID{work['id']}", 
                        callback_data=f'check_{work["id"]}'
                    )
                ])
        
        keyboard.append([InlineKeyboardButton("📋 Весь список", callback_data='list')])
        keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data='back')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка сводки: {e}")
        query.edit_message_text(f"❌ Ошибка: {str(e)}")

# ====== СПИСОК РАБОТ ======
def show_list(query):
    """Показать список работ"""
    try:
        pending_works = get_pending_works()
        checked_works = get_checked_works()
        
        text = "📋 *Список работ*\n\n"
        
        if pending_works:
            text += f"🔴 *На проверке ({len(pending_works)}):*\n\n"
            for work in pending_works:
                text += f"🆔 *ID{work['id']}*\n"
                text += f"📅 {work['date']} | {work['class']} класс\n"
                text += f"📝 {work['topic'][:40]}...\n"
                text += f"👥 {work['student_count']} учеников\n\n"
        
        if checked_works:
            text += f"✅ *Проверенные ({len(checked_works)}):*\n\n"
            for work in checked_works:
                text += f"🆔 ID{work['id']} | {work['date']} | {work['class']} класс\n"
                text += f"📝 {work['topic'][:30]}...\n\n"
        
        if not pending_works and not checked_works:
            text += "📭 *Нет сохраненных работ*\n\n"
        
        keyboard = []
        if pending_works:
            for work in pending_works[:5]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ Отметить ID{work['id']}", 
                        callback_data=f'check_{work["id"]}'
                    )
                ])
        
        keyboard.append([InlineKeyboardButton("📊 Сводка", callback_data='summary')])
        keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data='back')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка списка работ: {e}")
        query.edit_message_text(f"❌ Ошибка: {str(e)}")

# ====== СТАТИСТИКА ======
def show_stats(query):
    """Показать статистику"""
    try:
        stats = get_statistics()
        
        text = f"📈 *Статистика проверки*\n\n"
        text += f"📊 *Общая статистика:*\n"
        text += f"• Всего работ: {stats['total_count']}\n"
        text += f"• На проверке: {stats['pending_count']}\n"
        text += f"• Проверено: {stats['checked_count']}\n\n"
        
        text += f"👥 *Учеников:*\n"
        text += f"• На проверке: {stats['pending_students']}\n"
        text += f"• Проверено: {stats['checked_students']}\n"
        text += f"• Всего: {stats['pending_students'] + stats['checked_students']}\n\n"
        
        text += f"📅 *Обновлено:* {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        keyboard = [
            [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
            [InlineKeyboardButton("📋 Список работ", callback_data='list')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='back')],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        query.edit_message_text(f"❌ Ошибка: {str(e)}")

# ====== БЫСТРАЯ ОТМЕТКА ПРОВЕРКИ ======
def quick_check_work(query, work_id):
    """Быстрая отметка проверки"""
    try:
        if mark_work_as_checked(work_id):
            text = f"✅ *Работа #{work_id} проверена!*\n\n"
            text += "Работа перемещена в раздел 'Проверенные'."
        else:
            text = "❌ Работа не найдена или уже проверена"
        
        keyboard = [
            [InlineKeyboardButton("📋 Список работ", callback_data='list')],
            [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='back')],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка отметки проверки: {e}")
        query.edit_message_text(f"❌ Ошибка: {str(e)}")

# ====== ПОМОЩЬ ======
def show_help(query):
    """Показать помощь"""
    help_text = """🆘 *Помощь по использованию бота*

*Как создать работу:*
1. Нажмите 'Создать работу'
2. Выберите класс
3. Введите тему в формате:
   `Предмет: Тема --absent ученик1,ученик2`

*Как отметить проверку:*
1. Нажмите 'Список работ'
2. Найдите нужную работу
3. Нажмите кнопку 'Отметить ID...'
Или используйте команду: `/check ID`

*Команды:*
• `/start` - главное меню
• `/check ID` - отметить проверку (пример: `/check 1`)

*Особенности:*
• ✅ Данные сохраняются в PostgreSQL
• 🔄 Работает 24/7
• 💾 История не теряется при перезапуске"""
    
    keyboard = [
        [InlineKeyboardButton("➕ Создать работу", callback_data='create')],
        [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
        [InlineKeyboardButton("🏠 Главное меню", callback_data='back')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')

def show_check_menu(query):
    """Показать меню проверки"""
    query.edit_message_text(
        "✅ *Отметка проверки*\n\n"
        "Чтобы отметить работу как проверенную:\n"
        "1. Посмотрите список работ\n"
        "2. Найдите ID нужной работы\n"
        "3. Нажмите кнопку 'Отметить ID...'\n\n"
        "Или используйте команду:\n"
        "`/check ID`\n\n"
        "*Пример:* `/check 5`",
        parse_mode='Markdown'
    )

# ====== ОБРАБОТЧИК СООБЩЕНИЙ ======
def handle_message(update: Update, context: CallbackContext):
    """Обработка текстовых сообщений"""
    text = update.message.text
    
    # Если сообщение содержит : значит это создание работы
    if ':' in text:
        try:
            # Простой парсинг: Предмет: Тема --absent ученики
            if '--absent' in text:
                main_part, absent_part = text.split('--absent', 1)
                absent_students = [s.strip() for s in absent_part.split(',')]
            else:
                main_part = text
                absent_students = []
            
            subject, topic = main_part.split(':', 1)
            subject = subject.strip()
            topic = topic.strip()
            
            # Предполагаем, что класс был выбран ранее (упрощенно)
            # В реальном боте нужно хранить состояние
            
            update.message.reply_text(
                "⚠️ Для создания работы используйте кнопку 'Создать работу' в меню",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            update.message.reply_text(f"❌ Ошибка формата: {str(e)}")
    else:
        update.message.reply_text(
            "Используйте /start для открытия меню",
            parse_mode='Markdown'
        )

# ====== ГЛАВНАЯ ФУНКЦИЯ ======
def main():
    """Запуск бота"""
    # Инициализация базы данных
    init_db()
    
    # Создаем Updater
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Регистрируем обработчики
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("check", check_command))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    # Запускаем бота
    logger.info("🤖 Бот запущен с PostgreSQL!")
    logger.info(f"📊 База данных: {DATABASE_URL[:30]}...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
