import logging
import json
import random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = "7287684275:AAGEWRmemrLkWYAHu61SIQUd3QCVExv6cm0"

# Загрузка прогресса
try:
    with open('progress.json', 'r', encoding='utf-8') as f:
        progress = json.load(f)
except FileNotFoundError:
    progress = {}

# Кэш для вопросов
questions_cache = {}

def save_progress(chat_id=None):
    """Сохраняет прогресс только для указанного chat_id или всего словаря, если None."""
    if chat_id:
        with open('progress.json', 'w', encoding='utf-8') as f:
            filtered_progress = {chat_id: progress.get(chat_id, {})}
            json.dump(filtered_progress, f, ensure_ascii=False, indent=2)
    else:
        with open('progress.json', 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

def get_stats(chat_id):
    """Возвращает статистику пользователя."""
    chat_id = str(chat_id)
    if chat_id not in progress or 'total' not in progress[chat_id]:
        return "Начните викторину командой /start!"
    correct = progress[chat_id].get('correct', 0)
    total = progress[chat_id].get('total', 0)
    percent = (correct / total * 100) if total > 0 else 0
    return f"Правильных: {correct} из {total} ({percent:.1f}%)"

def load_questions(file_name, chat_id, context):
    """Загружает вопросы из файла с кэшированием."""
    if file_name in questions_cache:
        return questions_cache[file_name]
    
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            questions = json.load(f)
            questions_cache[file_name] = questions
            return questions
    except FileNotFoundError:
        context.bot.send_message(chat_id=chat_id, text=f"Ошибка: файл {file_name} не найден.")
        return []
    except json.JSONDecodeError as e:
        context.bot.send_message(chat_id=chat_id, text=f"Ошибка: {file_name} содержит неверный JSON: {e}")
        return []

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет случайный неотвеченный вопрос."""
    chat_id = str(update.effective_chat.id)
    questions = progress[chat_id].get('current_questions', [])
    answered = progress[chat_id].get('answered', [])
    
    available_questions = [i for i in range(len(questions)) if i not in answered]
    if not available_questions:
        keyboard = [[InlineKeyboardButton("Вернуться к блокам", callback_data="return_to_blocks")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Блок завершён! {get_stats(chat_id)}",
            reply_markup=reply_markup
        )
        save_progress(chat_id)
        return False
    
    question_index = random.choice(available_questions)
    question = questions[question_index]
    
    options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(question['options'])])
    full_message = f"{question['question']}\n\n{options_text}"
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(option, callback_data=f"{question_index}:{i}")]
        for i, option in enumerate(question['options'])
    ])
    
    await context.bot.send_message(chat_id=chat_id, text=full_message, reply_markup=markup)
    return question_index

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /start."""
    chat_id = str(update.effective_chat.id)
    if chat_id not in progress:
        progress[chat_id] = {
            'answered': [],
            'correct': 0,
            'total': 0,
            'current_block': None,
            'current_questions': [],
            'current_section': None
        }
    else:
        progress[chat_id].setdefault('answered', [])
        progress[chat_id].setdefault('correct', 0)
        progress[chat_id].setdefault('total', 0)
    save_progress(chat_id)
    keyboard = [
        [InlineKeyboardButton("Урология", callback_data="section_Урология")],
        [InlineKeyboardButton("УЗИ", callback_data="section_УЗИ")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=chat_id, text="Выбери раздел:", reply_markup=reply_markup)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /stats."""
    chat_id = str(update.effective_chat.id)
    await context.bot.send_message(chat_id=chat_id, text=get_stats(chat_id))

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /help."""
    chat_id = str(update.effective_chat.id)
    await context.bot.send_message(
        chat_id=chat_id,
        text="Это викторина по урологии и УЗИ!\n"
             "Команды:\n"
             "/start — начать выбор раздела\n"
             "/stats — посмотреть статистику\n"
             "/help — показать эту справку\n"
             "Введите / для выбора команд."
    )

async def show_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает доступные команды."""
    chat_id = str(update.effective_chat.id)
    keyboard = [
        [InlineKeyboardButton("/start", callback_data="command_start"),
         InlineKeyboardButton("/stats", callback_data="command_stats")],
        [InlineKeyboardButton("/help", callback_data="command_help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=chat_id, text="Выбери команду:", reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Общий обработчик callback-запросов."""
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat.id if query.message else query.from_user.id)
    data = query.data

    try:
        if data.startswith("section_"):
            # Обработка выбора раздела
            section = data.split("_")[1]
            progress[chat_id]['current_section'] = section
            keyboard = [
                [InlineKeyboardButton(f"Блок {i}", callback_data=f"block_{i}") for i in range(1, 6)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=chat_id, text=f"Выбери блок вопросов для раздела {section}:", reply_markup=reply_markup)
            save_progress(chat_id)

        elif data.startswith("block_"):
            # Обработка выбора блока
            block_num = int(data.split("_")[1])
            section = progress[chat_id].get('current_section')
            if not section:
                await context.bot.send_message(chat_id=chat_id, text="Сначала выберите раздел через /start.")
                return
            
            if section == "Урология":
                file_name = f"questions_{block_num}.json"
            elif section == "УЗИ":
                file_name = f"questions_{block_num + 5}.json"
            
            questions = load_questions(file_name, chat_id, context)
            if questions:
                progress[chat_id]['current_questions'] = questions
                progress[chat_id]['answered'] = []
                progress[chat_id]['current_block'] = block_num
                question_index = await send_question(update, context)
                if question_index is not False:
                    progress[chat_id]['answered'].append(question_index)
                    progress[chat_id]['total'] += 1
                    save_progress(chat_id)

        elif data == "return_to_blocks":
            # Обработка возвращения к блокам
            section = progress[chat_id].get('current_section')
            if not section:
                await context.bot.send_message(chat_id=chat_id, text="Сначала выберите раздел через /start.")
                return
            keyboard = [
                [InlineKeyboardButton(f"Блок {i}", callback_data=f"block_{i}") for i in range(1, 6)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=chat_id, text=f"Выбери новый блок вопросов для раздела {section}:", reply_markup=reply_markup)
            save_progress(chat_id)

        elif data.startswith("command_"):
            # Обработка команд через кнопки
            command = data.split("_")[1]
            if command == "start":
                await start(update, context)
            elif command == "stats":
                await stats(update, context)
            elif command == "help":
                await help_cmd(update, context)

        elif ":" in data:
            # Обработка ответа на вопрос
            start_time = time.time()
            question_index, answer_index = map(int, data.split(':'))
            questions = progress[chat_id]['current_questions']
            question = questions[question_index]
            
            # Проверка, что правильный ответ есть в списке вариантов
            if question['correct'] not in question['options']:
                logger.error(f"Правильный ответ '{question['correct']}' отсутствует в вариантах ответа: {question['options']}")
                await context.bot.send_message(chat_id=chat_id, text="Ошибка в данных вопроса: правильный ответ не найден. Обратитесь к администратору.")
                return
            
            correct_index = next(i for i, opt in enumerate(question['options']) if opt == question['correct'])
            
            response = ""
            if answer_index == correct_index:
                progress[chat_id]['correct'] += 1
                response = f"Правильно!\n\nПояснение: {question['explanation']}\n\n{get_stats(chat_id)}"
            else:
                response = f"Неправильно!\nПравильный ответ: {question['correct']}\n\nПояснение: {question['explanation']}\n\n{get_stats(chat_id)}"
            
            await context.bot.send_message(chat_id=chat_id, text=response)
            
            # Обновляем прогресс
            progress[chat_id]['answered'].append(question_index)
            progress[chat_id]['total'] += 1
            
            # Автоматически отправляем следующий вопрос
            question_index = await send_question(update, context)
            if question_index is not False:
                progress[chat_id]['answered'].append(question_index)
                progress[chat_id]['total'] += 1
                save_progress(chat_id)

            end_time = time.time()
            logger.info(f"Обработка callback-запроса {query.id} заняла {end_time - start_time:.2f} секунд")

    except Exception as e:
        logger.error(f"Неожиданная ошибка в handle_callback: {e}", exc_info=True)
        await context.bot.send_message(chat_id=chat_id, text=f"Ошибка: {str(e)}")

def main():
    """Запуск бота с использованием вебхуков."""
    application = Application.builder().token(TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/$'), show_commands))

    # Обработчик callback-запросов
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Настройка вебхука (замените YOUR_DOMAIN на ваш домен или IP после деплоя)
    application.run_webhook(
        listen="0.0.0.0",
        port=8443,
        url_path=TOKEN,
        webhook_url="https://my-telegram-bot-dnvk.onrender.com" + TOKEN
    )

if __name__ == "__main__":
    main()
