import os
import logging
import sqlite3
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ====== НАСТРОЙКИ ======
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
TOKEN = os.environ.get('TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '-1003810095854')

# Проверка токена
if not TOKEN:
    logger.error("❌ Токен не найден! Установите переменную окружения TOKEN")
    # Для Render: не завершаем работу, а ждем
    import time
    while not TOKEN:
        logger.warning("⏳ Ожидаю установку переменной TOKEN...")
        time.sleep(10)
        TOKEN = os.environ.get('TOKEN')

# ====== БАЗА ДАННЫХ ======
DB_FILE = "/tmp/homework.db"  # Для Render используем /tmp

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS works (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    logger.info("✅ База данных инициализирована")

# ====== БАЗА УЧЕНИКОВ ======
STUDENTS_DATABASE = {
    "7": ["Ваня А.", "Ангелина Гр.", "Ангелина Гт.", "Платон", "Миша", "Лев", "Ваня Ч."],
    "5": ["Алиса", "Джулия", "Ульяна", "Башир", "Ваня", "Вова"],
    "8": ["Диана", "Полина", "Настя", "Влада", "Амалия", "Соня", "Лиза", "Никита", "Роберт", "Егор", "Ульяна", "Стас"],
    "10": ["Денис", "Амелия", "Макар", "Яна", "Ева"]
}

# ====== КОМАНДЫ ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    keyboard = [
        [InlineKeyboardButton("➕ Создать работу", callback_data='new')],
        [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
        [InlineKeyboardButton("📋 Список работ", callback_data='list')],
        [InlineKeyboardButton("✅ Отметить проверку", callback_data='check')],
        [InlineKeyboardButton("📈 Статистика", callback_data='stats')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📚 *Бот для проверки работ*\n\n"
        "Работает 24/7 на Render.com\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'new':
        await create_work_menu(query)
    elif query.data == 'summary':
        await summary_command(query)
    elif query.data == 'list':
        await list_works(query)
    elif query.data == 'check':
        await check_menu(query)
    elif query.data == 'stats':
        await stats_command(query)
    elif query.data.startswith('class_'):
        await process_class_selection(query, context)
    elif query.data.startswith('check_'):
        await mark_as_checked(query)

async def create_work_menu(query):
    """Меню создания работы"""
    keyboard = []
    for class_num in STUDENTS_DATABASE.keys():
        keyboard.append([InlineKeyboardButton(f"{class_num} класс", callback_data=f'class_{class_num}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🏫 *Выберите класс:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def process_class_selection(query, context):
    """Обработка выбора класса"""
    class_num = query.data.replace('class_', '')
    context.user_data['class'] = class_num
    
    await query.edit_message_text(
        f"📝 *{class_num} класс*\n\n"
        f"Введите тему работы в формате:\n"
        f"`Предмет: Тема --absent ученик1,ученик2`\n\n"
        f"*Пример:*\n"
        f"`Алгебра: Контрольная работа --absent Ваня,Маша`\n\n"
        f"*Доступные ученики:*\n" + "\n".join(f"• {s}" for s in STUDENTS_DATABASE[class_num]),
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    if 'class' in context.user_data:
        await process_work_creation(update, context)
    else:
        await update.message.reply_text(
            "Используйте /start для начала работы",
            parse_mode='Markdown'
        )

async def process_work_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка создания работы"""
    try:
        text = update.message.text
        class_num = context.user_data['class']
        
        # Парсим сообщение
        if ':' in text:
            subject, rest = text.split(':', 1)
            subject = subject.strip()
            
            # Проверяем наличие --absent
            if '--absent' in rest:
                topic_part, absent_part = rest.split('--absent', 1)
                topic = topic_part.strip()
                absent_students = [s.strip() for s in absent_part.split(',')]
            else:
                topic = rest.strip()
                absent_students = []
        else:
            subject = "Не указан"
            topic = text
            absent_students = []
        
        # Получаем список всех учеников
        all_students = STUDENTS_DATABASE[class_num]
        submitted_students = [s for s in all_students if s not in absent_students]
        
        # Сохраняем в базу
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO works (date, class, subject, topic, student_count, total_students, 
                             submitted_students, absent_students, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().strftime('%d.%m.%Y'),
            class_num,
            subject,
            topic,
            len(submitted_students),
            len(all_students),
            json.dumps(submitted_students, ensure_ascii=False),
            json.dumps(absent_students, ensure_ascii=False),
            'pending'
        ))
        work_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Формируем пост для канала
        emoji = "📓" if subject.lower() in ["алгебра", "математика", "геометрия"] else "📚"
        post = f"{emoji} {datetime.now().strftime('%d.%m.%Y')} | {class_num} КЛАСС | {topic}\n"
        post += "────────────────────\n"
        
        if submitted_students:
            post += "✅ СДАЛИ:\n"
            for i, student in enumerate(submitted_students, 1):
                post += f"{i}. {student}\n"
        else:
            post += "✅ СДАЛИ: (нет)\n"
        
        post += "\n"
        
        if absent_students:
            post += "❌ НЕ СДАЛИ:\n"
            for student in absent_students:
                post += f"• {student}\n"
        else:
            post += "❌ НЕ СДАЛИ: (нет)\n"
        
        total = len(all_students)
        submitted = len(submitted_students)
        percent = int((submitted / total) * 100) if total > 0 else 0
        
        post += f"\n📊 Статистика: {submitted}/{total} ({percent}%)\n"
        post += "⏳ Статус: В очереди на проверку\n"
        post += "────────────────────\n"
        post += f"#{class_num}класс #{subject.replace(' ', '')} #на_проверке"
        
        # Отправляем в канал
        await context.bot.send_message(chat_id=CHANNEL_ID, text=post)
        
        # Ответ пользователю
        response = f"""✅ *Работа создана!*

🆔 ID: {work_id}
🏫 Класс: {class_num}
📖 Предмет: {subject}
📝 Тема: {topic}
👥 Учеников: {submitted}/{total}
📊 Процент: {percent}%

После проверки используйте:
`/check {work_id}`"""
        
        if absent_students:
            response += f"\n\n❌ Отсутствовали: {', '.join(absent_students)}"
        
        await update.message.reply_text(response, parse_mode='Markdown')
        
        # Очищаем контекст
        context.user_data.clear()
        
    except Exception as e:
        logger.error(f"Ошибка создания работы: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def summary_command(query):
    """Команда сводки"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM works WHERE status='pending'")
        pending = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM works WHERE status='checked'")
        checked = cursor.fetchone()[0] or 0
        
        cursor.execute('''
            SELECT id, class, topic, student_count 
            FROM works 
            WHERE status='pending' 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        works = cursor.fetchall()
        
        conn.close()
        
        text = f"📊 *Сводка*\n\n"
        text += f"⏳ На проверке: {pending} работ\n"
        text += f"✅ Проверено: {checked} работ\n"
        text += f"📚 Всего: {pending + checked} работ\n\n"
        
        if works:
            text += "*Последние работы:*\n"
            for work in works:
                text += f"• ID{work[0]}: {work[1]} класс - {work[2][:30]}...\n"
                text += f"  👥 {work[3]} учеников\n\n"
        
        keyboard = [[InlineKeyboardButton("🔄 Обновить", callback_data='summary')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка сводки: {e}")
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

async def list_works(query):
    """Список работ"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, date, class, topic, student_count 
            FROM works 
            WHERE status='pending' 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        works = cursor.fetchall()
        
        conn.close()
        
        text = "📋 *Работы на проверке:*\n\n"
        
        if works:
            for work in works:
                text += f"🆔 *ID{work[0]}*\n"
                text += f"📅 {work[1]} | {work[2]} класс\n"
                text += f"📝 {work[3][:40]}...\n"
                text += f"👥 {work[4]} учеников\n\n"
        else:
            text += "🎉 Все работы проверены!\n\n"
        
        # Кнопки для быстрой проверки
        keyboard = []
        if works:
            for work in works[:3]:  # Только 3 кнопки
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ Проверить ID{work[0]}", 
                        callback_data=f'check_{work[0]}'
                    )
                ])
        
        keyboard.append([InlineKeyboardButton("📊 Сводка", callback_data='summary')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка списка работ: {e}")
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

async def check_menu(query):
    """Меню отметки проверки"""
    await query.edit_message_text(
        "✅ *Отметка проверки*\n\n"
        "Введите ID работы в формате:\n"
        "`/check ID`\n\n"
        "*Пример:* `/check 5`\n\n"
        "Или выберите работу из списка:",
        parse_mode='Markdown'
    )

async def mark_as_checked(query):
    """Отметить работу как проверенную"""
    try:
        work_id = int(query.data.replace('check_', ''))
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE works SET status='checked' WHERE id=? AND status='pending'",
            (work_id,)
        )
        
        if cursor.rowcount > 0:
            cursor.execute("SELECT class, topic FROM works WHERE id=?", (work_id,))
            work = cursor.fetchone()
            
            conn.commit()
            conn.close()
            
            text = f"✅ *Работа проверена!*\n\n"
            text += f"🆔 ID: {work_id}\n"
            text += f"🏫 Класс: {work[0]}\n"
            text += f"📝 Тема: {work[1]}\n\n"
            text += "Работа перемещена в 'Проверенные'."
        else:
            conn.close()
            text = "❌ Работа не найдена или уже проверена"
        
        keyboard = [
            [InlineKeyboardButton("📋 Список работ", callback_data='list')],
            [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка отметки проверки: {e}")
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

async def stats_command(query):
    """Статистика"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM works")
        total = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM works WHERE status='pending'")
        pending = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM works WHERE status='checked'")
        checked = cursor.fetchone()[0] or 0
        
        # Статистика по классам
        cursor.execute('''
            SELECT class, COUNT(*), 
                   SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END)
            FROM works 
            GROUP BY class
        ''')
        class_stats = cursor.fetchall()
        
        conn.close()
        
        text = f"📈 *Статистика*\n\n"
        text += f"📊 Всего работ: {total}\n"
        text += f"⏳ На проверке: {pending}\n"
        text += f"✅ Проверено: {checked}\n\n"
        
        if class_stats:
            text += f"🏫 *По классам:*\n"
            for stat in class_stats:
                text += f"• {stat[0]} класс: {stat[1]} работ ({stat[2]} на проверке)\n"
        
        text += f"\n📅 Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        keyboard = [[InlineKeyboardButton("🔄 Обновить", callback_data='stats')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

# Команда /check для текстового ввода
async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /check"""
    if not context.args:
        await update.message.reply_text(
            "Укажите ID работы: `/check 5`",
            parse_mode='Markdown'
        )
        return
    
    try:
        work_id = int(context.args[0])
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE works SET status='checked' WHERE id=? AND status='pending'",
            (work_id,)
        )
        
        if cursor.rowcount > 0:
            cursor.execute("SELECT class, topic FROM works WHERE id=?", (work_id,))
            work = cursor.fetchone()
            
            conn.commit()
            conn.close()
            
            await update.message.reply_text(
                f"✅ *Работа проверена!*\n\n"
                f"ID: {work_id}\n"
                f"Класс: {work[0]}\n"
                f"Тема: {work[1]}",
                parse_mode='Markdown'
            )
        else:
            conn.close()
            await update.message.reply_text("❌ Работа не найдена или уже проверена")
        
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом")
    except Exception as e:
        logger.error(f"Ошибка команды /check: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# ====== ГЛАВНАЯ ФУНКЦИЯ ======
def main():
    """Запуск бота"""
    # Инициализация базы данных
    init_db()
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    logger.info("🤖 Бот запущен на Render.com")
    logger.info(f"📊 База данных: {DB_FILE}")
    logger.info("🔄 Бот работает 24/7")
    
    application.run_polling()

if __name__ == "__main__":
    main()