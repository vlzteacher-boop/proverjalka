import os
import logging
import sqlite3
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

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
    logger.error("❌ Токен не найден!")
    exit(1)

# ====== БАЗА ДАННЫХ ======
DB_FILE = "homework.db"

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
        [InlineKeyboardButton("🆘 Помощь", callback_data='help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📚 *Бот для проверки работ*\n\n"
        "Работает 24/7 на Render.com\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'new':
        await show_class_selection(query)
    elif query.data == 'summary':
        await show_summary(query)
    elif query.data == 'list':
        await show_list(query)
    elif query.data == 'check':
        await show_check_menu(query)
    elif query.data == 'stats':
        await show_stats(query)
    elif query.data == 'help':
        await show_help(query)
    elif query.data.startswith('class_'):
        await handle_class_selection(query, context)
    elif query.data.startswith('check_'):
        await mark_as_checked(query)
    elif query.data == 'back':
        await start_from_button(query)

async def start_from_button(query):
    """Старт из кнопки"""
    keyboard = [
        [InlineKeyboardButton("➕ Создать работу", callback_data='new')],
        [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
        [InlineKeyboardButton("📋 Список работ", callback_data='list')],
        [InlineKeyboardButton("✅ Отметить проверку", callback_data='check')],
        [InlineKeyboardButton("📈 Статистика", callback_data='stats')],
        [InlineKeyboardButton("🆘 Помощь", callback_data='help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📚 *Бот для проверки работ*\n\n"
        "Работает 24/7 на Render.com\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_class_selection(query):
    """Показать выбор класса"""
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

async def handle_class_selection(query, context):
    """Обработка выбора класса"""
    class_num = query.data.replace('class_', '')
    context.user_data['class'] = class_num
    
    await query.edit_message_text(
        f"📝 *{class_num} класс*\n\n"
        f"Введите тему работы в формате:\n"
        f"`Предмет: Тема`\n\n"
        f"*Пример:*\n"
        f"`Алгебра: Контрольная работа`\n\n"
        f"Для указания отсутствующих добавьте в конце:\n"
        f"`--absent Имя1, Имя2`\n\n"
        f"*Полный пример:*\n"
        f"`Алгебра: Тест --absent Ваня, Маша`",
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
        if '--absent' in text:
            main_part, absent_part = text.split('--absent', 1)
            absent_students = [s.strip() for s in absent_part.split(',')]
        else:
            main_part = text
            absent_students = []
        
        # Разделяем предмет и тему
        if ':' in main_part:
            subject, topic = main_part.split(':', 1)
            subject = subject.strip()
            topic = topic.strip()
        else:
            subject = "Не указан"
            topic = main_part.strip()
        
        # Получаем список всех учеников
        all_students = STUDENTS_DATABASE.get(class_num, [])
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
        await update.message.reply_text(f"❌ Ошибка: {str(e)}\n\nПопробуйте еще раз: /start")

async def show_summary(query):
    """Показать сводку"""
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
        
        keyboard = [
            [InlineKeyboardButton("✅ Отметить проверку", callback_data='check')],
            [InlineKeyboardButton("📋 Список работ", callback_data='list')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка сводки: {e}")
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

async def show_list(query):
    """Показать список работ"""
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
            for work in works[:3]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ Проверить ID{work[0]}", 
                        callback_data=f'check_{work[0]}'
                    )
                ])
        
        keyboard.append([InlineKeyboardButton("📊 Сводка", callback_data='summary')])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка списка работ: {e}")
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

async def show_check_menu(query):
    """Показать меню проверки"""
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
            [InlineKeyboardButton("🔙 Назад", callback_data='back')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка отметки проверки: {e}")
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

async def show_stats(query):
    """Показать статистику"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM works")
        total = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM works WHERE status='pending'")
        pending = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM works WHERE status='checked'")
        checked = cursor.fetchone()[0] or 0
        
        conn.close()
        
        text = f"📈 *Статистика*\n\n"
        text += f"📊 Всего работ: {total}\n"
        text += f"⏳ На проверке: {pending}\n"
        text += f"✅ Проверено: {checked}\n\n"
        
        text += f"📅 Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        keyboard = [
            [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
            [InlineKeyboardButton("📋 Список работ", callback_data='list')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

async def show_help(query):
    """Показать помощь"""
    help_text = """🆘 *Помощь*

*Как создать работу:*
1. Нажмите "Создать работу"
2. Выберите класс
3. Введите в формате:
   `Предмет: Тема --absent Имя1, Имя2`

*Примеры:*
• `Алгебра: Контрольная`
• `Математика: Тест --absent Ваня, Маша`
• `Геометрия: Задачи`

*Команды:*
• `/check ID` - отметить работу как проверенную
• `/start` - главное меню

*Быстрые действия через кнопки:*
• Создание работы
• Просмотр сводки
• Отметка проверки
• Статистика

*Поддержка:*
Бот работает 24/7 на Render.com"""
    
    keyboard = [
        [InlineKeyboardButton("➕ Создать работу", callback_data='new')],
        [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')

# Команда /check
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
    
    application.run_polling()

if __name__ == "__main__":
    main()
