import os
import logging
import sqlite3
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

if not TOKEN:
    logger.error("❌ Токен не найден! Добавьте переменную TOKEN в Render")
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

# ====== СОСТОЯНИЯ ДЛЯ СОЗДАНИЯ РАБОТЫ ======
SELECT_CLASS, ENTER_DETAILS, CONFIRM = range(3)

# ====== КОМАНДА /START ======
def start(update: Update, context: CallbackContext):
    """Команда /start - главное меню"""
    keyboard = [
        [InlineKeyboardButton("➕ Создать работу", callback_data='create')],
        [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
        [InlineKeyboardButton("📋 Список работ", callback_data='list')],
        [InlineKeyboardButton("✅ Отметить проверку", callback_data='check')],
        [InlineKeyboardButton("📈 Статистика", callback_data='stats')],
        [InlineKeyboardButton("🆘 Помощь", callback_data='help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "📚 *Бот для проверки работ*\n\n"
        "Выберите действие из меню ниже:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return ConversationHandler.END

# ====== СОЗДАНИЕ РАБОТЫ ======
def create_work_start(update: Update, context: CallbackContext):
    """Начало создания работы"""
    query = update.callback_query
    if query:
        query.answer()
    
    keyboard = []
    for class_num in STUDENTS_DATABASE.keys():
        keyboard.append([InlineKeyboardButton(f"{class_num} класс", callback_data=f'class_{class_num}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Отмена", callback_data='cancel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        query.edit_message_text(
            "🏫 *Выберите класс:*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        update.message.reply_text(
            "🏫 *Выберите класс:*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    return SELECT_CLASS

def select_class(update: Update, context: CallbackContext):
    """Выбор класса"""
    query = update.callback_query
    query.answer()
    
    if query.data == 'cancel':
        return cancel_creation(update, context)
    
    class_num = query.data.replace('class_', '')
    context.user_data['class'] = class_num
    
    # Показываем предметы
    keyboard = [
        [InlineKeyboardButton("Алгебра", callback_data='subject_Алгебра')],
        [InlineKeyboardButton("Математика", callback_data='subject_Математика')],
        [InlineKeyboardButton("Геометрия", callback_data='subject_Геометрия')],
        [InlineKeyboardButton("Другой предмет", callback_data='subject_other')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_classes')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        f"🏫 *{class_num} класс*\n\n"
        "📖 Выберите предмет:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return ENTER_DETAILS

def enter_subject(update: Update, context: CallbackContext):
    """Ввод предмета"""
    query = update.callback_query
    query.answer()
    
    if query.data == 'back_to_classes':
        return create_work_start(update, context)
    
    if query.data == 'subject_other':
        query.edit_message_text(
            "✏️ *Введите название предмета:*\n\n"
            "Например: Физика, Химия, История",
            parse_mode='Markdown'
        )
        return ENTER_DETAILS
    
    subject = query.data.replace('subject_', '')
    context.user_data['subject'] = subject
    
    query.edit_message_text(
        f"📝 *Введите тему работы:*\n\n"
        f"Класс: {context.user_data['class']}\n"
        f"Предмет: {subject}",
        parse_mode='Markdown'
    )
    return ENTER_DETAILS

def enter_topic(update: Update, context: CallbackContext):
    """Ввод темы работы"""
    if update.callback_query:
        query = update.callback_query
        query.answer()
        return
    
    text = update.message.text
    
    # Если это предмет (когда выбрали "Другой предмет")
    if 'subject' not in context.user_data:
        context.user_data['subject'] = text
        update.message.reply_text(
            f"📝 *Введите тему работы:*\n\n"
            f"Класс: {context.user_data['class']}\n"
            f"Предмет: {text}",
            parse_mode='Markdown'
        )
        return ENTER_DETAILS
    
    # Иначе это тема
    context.user_data['topic'] = text
    
    # Показываем подтверждение
    class_num = context.user_data['class']
    subject = context.user_data['subject']
    topic = context.user_data['topic']
    
    # Получаем список учеников
    students = STUDENTS_DATABASE.get(class_num, [])
    student_count = len(students)
    
    keyboard = [
        [InlineKeyboardButton("✅ Создать без отсутствующих", callback_data='create_no_absent')],
        [InlineKeyboardButton("👥 Указать отсутствующих", callback_data='add_absent')],
        [InlineKeyboardButton("🔙 Изменить", callback_data='back_to_subject')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        f"📋 *Подтвердите создание работы:*\n\n"
        f"🏫 Класс: {class_num}\n"
        f"📖 Предмет: {subject}\n"
        f"📝 Тема: {topic}\n"
        f"👥 Всего учеников: {student_count}\n\n"
        f"Выберите вариант:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return CONFIRM

def create_final(update: Update, context: CallbackContext):
    """Финальное создание работы"""
    query = update.callback_query
    query.answer()
    
    class_num = context.user_data['class']
    subject = context.user_data['subject']
    topic = context.user_data['topic']
    absent_students = context.user_data.get('absent_students', [])
    
    # Получаем список учеников
    all_students = STUDENTS_DATABASE.get(class_num, [])
    submitted_students = [s for s in all_students if s not in absent_students]
    student_count = len(submitted_students)
    total_students = len(all_students)
    
    # Сохраняем в базу данных
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
        student_count,
        total_students,
        json.dumps(submitted_students, ensure_ascii=False),
        json.dumps(absent_students, ensure_ascii=False),
        'pending'
    ))
    
    work_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Формируем пост для канала
    emoji = "📓" if subject.lower() in ["алгебра", "математика", "геометрия"] else "📚"
    date_str = datetime.now().strftime('%d.%m.%Y')
    
    post = f"{emoji} {date_str} | {class_num} КЛАСС | {topic}\n"
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
    
    percent = int((student_count / total_students) * 100) if total_students > 0 else 0
    
    post += f"\n📊 Статистика: {student_count}/{total_students} ({percent}%)\n"
    post += "⏳ Статус: В очереди на проверку\n"
    post += "────────────────────\n"
    post += f"#{class_num}класс #{subject.replace(' ', '')} #на_проверке"
    
    # Отправляем в канал
    try:
        context.bot.send_message(chat_id=CHANNEL_ID, text=post)
        channel_success = True
    except Exception as e:
        logger.error(f"Ошибка отправки в канал: {e}")
        channel_success = False
    
    # Отправляем подтверждение пользователю
    response = f"✅ *Работа создана!*\n\n"
    response += f"🆔 ID: {work_id}\n"
    response += f"🏫 Класс: {class_num}\n"
    response += f"📖 Предмет: {subject}\n"
    response += f"📝 Тема: {topic}\n"
    response += f"👥 Учеников: {student_count}/{total_students}\n"
    response += f"📊 Процент: {percent}%\n\n"
    
    if absent_students:
        response += f"❌ Отсутствовали: {', '.join(absent_students)}\n\n"
    
    if channel_success:
        response += "📤 Запись отправлена в канал."
    else:
        response += "⚠️ Не удалось отправить в канал."
    
    keyboard = [
        [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
        [InlineKeyboardButton("📋 Список работ", callback_data='list')],
        [InlineKeyboardButton("➕ Новая работа", callback_data='create')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(response, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Очищаем временные данные
    context.user_data.clear()
    
    return ConversationHandler.END

def cancel_creation(update: Update, context: CallbackContext):
    """Отмена создания"""
    query = update.callback_query
    query.answer()
    
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("➕ Создать работу", callback_data='create')],
        [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
        [InlineKeyboardButton("🏠 Главное меню", callback_data='menu')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        "❌ Создание работы отменено.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

# ====== СВОДКА И СТАТИСТИКА ======
def show_summary(update: Update, context: CallbackContext):
    """Показать сводку"""
    query = update.callback_query
    query.answer()
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Статистика
        cursor.execute("SELECT COUNT(*) FROM works WHERE status='pending'")
        pending = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM works WHERE status='checked'")
        checked = cursor.fetchone()[0] or 0
        
        # Последние работы
        cursor.execute('''
            SELECT id, date, class, topic, student_count 
            FROM works 
            WHERE status='pending' 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        works = cursor.fetchall()
        
        conn.close()
        
        text = f"📊 *Сводка по проверке*\n\n"
        text += f"⏳ На проверке: {pending} работ\n"
        text += f"✅ Проверено: {checked} работ\n"
        text += f"📚 Всего: {pending + checked} работ\n\n"
        
        if works:
            text += "*Последние работы:*\n"
            for work in works:
                text += f"• ID{work[0]}: {work[2]} класс - {work[3][:30]}...\n"
                text += f"  📅 {work[1]} | 👥 {work[4]} учеников\n\n"
        else:
            text += "🎉 *Все работы проверены!*\n\n"
        
        # Кнопки
        keyboard = []
        if works:
            for work in works[:3]:  # Кнопки для первых 3 работ
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ Проверить ID{work[0]}", 
                        callback_data=f'quick_check_{work[0]}'
                    )
                ])
        
        keyboard.append([InlineKeyboardButton("📋 Весь список", callback_data='list')])
        keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data='menu')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка сводки: {e}")
        query.edit_message_text(f"❌ Ошибка: {str(e)}")

def show_stats(update: Update, context: CallbackContext):
    """Показать статистику"""
    query = update.callback_query
    query.answer()
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM works")
        total = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM works WHERE status='pending'")
        pending = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM works WHERE status='checked'")
        checked = cursor.fetchone()[0] or 0
        
        # Статистика по классам
        cursor.execute('''
            SELECT class, COUNT(*), 
                   SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending_count
            FROM works 
            GROUP BY class
        ''')
        class_stats = cursor.fetchall()
        
        conn.close()
        
        text = f"📈 *Статистика проверки*\n\n"
        text += f"📊 *Общая:*\n"
        text += f"• Всего работ: {total}\n"
        text += f"• На проверке: {pending}\n"
        text += f"• Проверено: {checked}\n\n"
        
        if class_stats:
            text += f"🏫 *По классам:*\n"
            for stat in class_stats:
                text += f"• {stat[0]} класс: {stat[1]} работ ({stat[2]} на проверке)\n"
        
        text += f"\n📅 *Обновлено:* {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        keyboard = [
            [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
            [InlineKeyboardButton("📋 Список работ", callback_data='list')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='menu')],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        query.edit_message_text(f"❌ Ошибка: {str(e)}")

# ====== СПИСОК РАБОТ ======
def list_works(update: Update, context: CallbackContext):
    """Показать список работ"""
    query = update.callback_query
    query.answer()
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Работы на проверке
        cursor.execute('''
            SELECT id, date, class, topic, student_count 
            FROM works 
            WHERE status='pending' 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        pending_works = cursor.fetchall()
        
        # Проверенные работы
        cursor.execute('''
            SELECT id, date, class, topic 
            FROM works 
            WHERE status='checked' 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        checked_works = cursor.fetchall()
        
        conn.close()
        
        text = "📋 *Список работ*\n\n"
        
        if pending_works:
            text += f"🔴 *На проверке ({len(pending_works)}):*\n\n"
            for work in pending_works:
                text += f"🆔 *ID{work[0]}*\n"
                text += f"📅 {work[1]} | {work[2]} класс\n"
                text += f"📝 {work[3][:40]}...\n"
                text += f"👥 {work[4]} учеников\n\n"
        
        if checked_works:
            text += f"✅ *Проверенные ({len(checked_works)}):*\n\n"
            for work in checked_works:
                text += f"🆔 ID{work[0]} | {work[1]} | {work[2]} класс\n"
                text += f"📝 {work[3][:30]}...\n\n"
        
        if not pending_works and not checked_works:
            text += "📭 *Нет сохраненных работ*\n\n"
        
        # Кнопки для быстрой проверки
        keyboard = []
        if pending_works:
            for work in pending_works[:5]:  # Максимум 5 кнопок
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ Отметить ID{work[0]}", 
                        callback_data=f'quick_check_{work[0]}'
                    )
                ])
        
        keyboard.append([InlineKeyboardButton("📊 Сводка", callback_data='summary')])
        keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data='menu')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка списка работ: {e}")
        query.edit_message_text(f"❌ Ошибка: {str(e)}")

# ====== ОТМЕТКА ПРОВЕРКИ ======
def mark_as_checked(update: Update, context: CallbackContext):
    """Отметить работу как проверенную"""
    query = update.callback_query
    query.answer()
    
    try:
        work_id = int(query.data.replace('quick_check_', ''))
        
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
            text += "Работа перемещена в раздел 'Проверенные'."
        else:
            conn.close()
            text = "❌ Работа не найдена или уже проверена"
        
        keyboard = [
            [InlineKeyboardButton("📋 Список работ", callback_data='list')],
            [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='menu')],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка отметки проверки: {e}")
        query.edit_message_text(f"❌ Ошибка: {str(e)}")

# ====== КОМАНДА /CHECK ======
def check_command(update: Update, context: CallbackContext):
    """Команда /check для отметки проверки"""
    if not context.args:
        update.message.reply_text(
            "❌ Укажите ID работы:\n"
            "`/check 1`\n\n"
            "Чтобы узнать ID работы, используйте /start → 📋 Список работ",
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
            
            update.message.reply_text(
                f"✅ *Работа проверена!*\n\n"
                f"ID: {work_id}\n"
                f"Класс: {work[0]}\n"
                f"Тема: {work[1]}",
                parse_mode='Markdown'
            )
        else:
            conn.close()
            update.message.reply_text("❌ Работа не найдена или уже проверена")
        
    except ValueError:
        update.message.reply_text("❌ ID должен быть числом")
    except Exception as e:
        logger.error(f"Ошибка команды /check: {e}")
        update.message.reply_text(f"❌ Ошибка: {str(e)}")

# ====== ПОМОЩЬ ======
def show_help(update: Update, context: CallbackContext):
    """Показать помощь"""
    query = update.callback_query
    query.answer()
    
    help_text = """🆘 *Помощь по использованию бота*

*Основные функции:*
• *Создание работы* - добавление новой работы на проверку
• *Сводка* - обзор текущего статуса проверок
• *Список работ* - просмотр всех работ с возможностью быстрой отметки
• *Отметка проверки* - перемещение работы в 'Проверенные'
• *Статистика* - подробная статистика по проверкам

*Как создать работу:*
1. Нажмите 'Создать работу'
2. Выберите класс
3. Выберите предмет
4. Введите тему
5. Подтвердите создание

*Как отметить проверку:*
1. Нажмите 'Список работ'
2. Найдите нужную работу
3. Нажмите кнопку 'Отметить ID...'
Или используйте команду: `/check ID`

*Команды:*
• `/start` - главное меню
• `/check ID` - отметить проверку (пример: `/check 1`)
• `/help` - эта справка

*Поддержка:*
Бот работает 24/7 на Render.com"""
    
    keyboard = [
        [InlineKeyboardButton("➕ Создать работу", callback_data='create')],
        [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
        [InlineKeyboardButton("🏠 Главное меню", callback_data='menu')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')

# ====== ГЛАВНОЕ МЕНЮ ======
def main_menu(update: Update, context: CallbackContext):
    """Вернуться в главное меню"""
    query = update.callback_query
    query.answer()
    
    keyboard = [
        [InlineKeyboardButton("➕ Создать работу", callback_data='create')],
        [InlineKeyboardButton("📊 Сводка", callback_data='summary')],
        [InlineKeyboardButton("📋 Список работ", callback_data='list')],
        [InlineKeyboardButton("✅ Отметить проверку", callback_data='check_menu')],
        [InlineKeyboardButton("📈 Статистика", callback_data='stats')],
        [InlineKeyboardButton("🆘 Помощь", callback_data='help')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        "📚 *Бот для проверки работ*\n\n"
        "Выберите действие из меню ниже:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return ConversationHandler.END

def check_menu(update: Update, context: CallbackContext):
    """Меню для отметки проверки"""
    query = update.callback_query
    query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📋 Посмотреть список", callback_data='list')],
        [InlineKeyboardButton("🏠 Главное меню", callback_data='menu')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        "✅ *Отметка проверки*\n\n"
        "Чтобы отметить работу как проверенную:\n"
        "1. Посмотрите список работ\n"
        "2. Найдите ID нужной работы\n"
        "3. Нажмите кнопку 'Отметить ID...'\n\n"
        "Или используйте команду:\n"
        "`/check ID`\n\n"
        "*Пример:* `/check 5`",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ====== ОСНОВНАЯ ФУНКЦИЯ ======
def main():
    """Запуск бота"""
    # Инициализация базы данных
    init_db()
    
    # Создаем Updater
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # ConversationHandler для создания работы
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(create_work_start, pattern='^create$'),
            CallbackQueryHandler(create_work_start, pattern='^back_to_classes$'),
        ],
        states={
            SELECT_CLASS: [
                CallbackQueryHandler(select_class, pattern='^class_'),
                CallbackQueryHandler(cancel_creation, pattern='^cancel$'),
                CallbackQueryHandler(main_menu, pattern='^menu$'),
            ],
            ENTER_DETAILS: [
                CallbackQueryHandler(enter_subject, pattern='^subject_'),
                CallbackQueryHandler(enter_subject, pattern='^back_to_subject$'),
                CallbackQueryHandler(select_class, pattern='^back_to_classes$'),
                MessageHandler(Filters.text & ~Filters.command, enter_topic),
                CallbackQueryHandler(main_menu, pattern='^menu$'),
            ],
            CONFIRM: [
                CallbackQueryHandler(create_final, pattern='^create_no_absent$'),
                CallbackQueryHandler(create_final, pattern='^add_absent$'),
                CallbackQueryHandler(enter_subject, pattern='^back_to_subject$'),
                CallbackQueryHandler(main_menu, pattern='^menu$'),
            ],
        },
        fallbacks=[
            CommandHandler('start', start),
            CallbackQueryHandler(main_menu, pattern='^menu$'),
        ],
    )
    
    # Регистрируем обработчики
    dp.add_handler(conv_handler)
    dp.add_handler(CommandHandler('check', check_command))
    dp.add_handler(CommandHandler('help', lambda u, c: show_help(u, c)))
    
    # Обработчики кнопок
    dp.add_handler(CallbackQueryHandler(show_summary, pattern='^summary$'))
    dp.add_handler(CallbackQueryHandler(list_works, pattern='^list$'))
    dp.add_handler(CallbackQueryHandler(show_stats, pattern='^stats$'))
    dp.add_handler(CallbackQueryHandler(show_help, pattern='^help$'))
    dp.add_handler(CallbackQueryHandler(main_menu, pattern='^menu$'))
    dp.add_handler(CallbackQueryHandler(check_menu, pattern='^check_menu$'))
    dp.add_handler(CallbackQueryHandler(mark_as_checked, pattern='^quick_check_'))
    
    # Запускаем бота
    logger.info("🤖 Бот запущен!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
