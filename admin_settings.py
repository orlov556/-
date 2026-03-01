from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, ConversationHandler, filters
from telegram.constants import ChatMemberStatus
import json
import config

# Состояния для ConversationHandler
(SET_WELCOME, SET_GOODBYE, ADD_BANNED_WORD, ADD_ALLOWED_LINK,
 SET_FLOOD_LIMIT, SET_FLOOD_SECONDS, SET_ADMIN_ROLE) = range(7)

async def chat_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /чат или /настройки - управление настройками чата (только в ЛС)"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type != 'private':
        await update.message.reply_text("❌ Эта команда работает только в личных сообщениях с ботом!")
        return
    
    # Проверяем, есть ли у пользователя чаты, где он админ
    # В реальном боте нужно хранить список чатов пользователя
    # Для примера используем заглушку
    await update.message.reply_text(
        "Выбери чат для настройки:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("➕ Добавить чат", callback_data="add_chat")
        ]])
    )

async def show_chat_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Показывает настройки конкретного чата"""
    query = update.callback_query
    db = context.bot_data['db']
    
    settings = await db.get_chat_settings(chat_id)
    
    # Получаем информацию о чате
    try:
        chat = await context.bot.get_chat(chat_id)
        chat_title = chat.title or "Безымянный чат"
    except:
        chat_title = "Недоступный чат"
    
    text = f"⚙️ *Настройки чата: {chat_title}*\n\n"
    
    # Формируем текст с текущими настройками
    status = lambda x: "✅ Включено" if x else "❌ Отключено"
    text += f"👋 Приветствие: {status(settings['welcome'])}\n"
    text += f"👋 Прощание: {status(settings['goodbye'])}\n"
    text += f"🔢 Капча: {status(settings['captcha'])}\n"
    text += f"🤬 Антимат: {status(settings['antimat'])}\n"
    text += f"🛡️ Антиспам: {status(settings['antispam'])}\n"
    text += f"🔗 Антиссылки: {status(settings['antilinks'])}\n"
    text += f"🎨 Ограничение медиа: {status(settings['media_limit'])}\n\n"
    
    text += f"📝 Текст приветствия:\n`{settings['welcome_text']}`\n\n"
    text += f"📝 Текст прощания:\n`{settings['goodbye_text']}`\n\n"
    text += f"📊 Лимит флуда: {settings['flood_limit']} сообщений за {settings['flood_seconds']} сек\n"
    
    if settings['banned_words']:
        text += f"\n🚫 Запрещенные слова: {', '.join(settings['banned_words'])}\n"
    if settings['allowed_links']:
        text += f"🔗 Разрешенные ссылки: {', '.join(settings['allowed_links'])}\n"
    
    # Создаем клавиатуру для управления настройками
    keyboard = [
        [InlineKeyboardButton("👋 Приветствие", callback_data=f"toggle_welcome_{chat_id}")],
        [InlineKeyboardButton("👋 Прощание", callback_data=f"toggle_goodbye_{chat_id}")],
        [InlineKeyboardButton("🔢 Капча", callback_data=f"toggle_captcha_{chat_id}")],
        [InlineKeyboardButton("🤬 Антимат", callback_data=f"toggle_antimat_{chat_id}")],
        [InlineKeyboardButton("🛡️ Антиспам", callback_data=f"toggle_antispam_{chat_id}")],
        [InlineKeyboardButton("🔗 Антиссылки", callback_data=f"toggle_antilinks_{chat_id}")],
        [InlineKeyboardButton("🎨 Медиа", callback_data=f"toggle_media_{chat_id}")],
        [InlineKeyboardButton("📝 Текст приветствия", callback_data=f"edit_welcome_{chat_id}")],
        [InlineKeyboardButton("📝 Текст прощания", callback_data=f"edit_goodbye_{chat_id}")],
        [InlineKeyboardButton("🚫 Запрещенные слова", callback_data=f"banned_words_{chat_id}")],
        [InlineKeyboardButton("🔗 Разрешенные ссылки", callback_data=f"allowed_links_{chat_id}")],
        [InlineKeyboardButton("📊 Лимиты флуда", callback_data=f"flood_limits_{chat_id}")],
        [InlineKeyboardButton("👥 Управление админами", callback_data=f"admins_{chat_id}")],
        [InlineKeyboardButton("◀️ Назад к чатам", callback_data="back_to_chats")]
    ]
    
    # Разбиваем на ряды по 2 кнопки
    rows = [keyboard[i:i+2] for i in range(0, len(keyboard), 2)]
    
    if query:
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(rows)
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(rows)
        )

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки настроек"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    db = context.bot_data['db']
    
    if data == "back_to_chats":
        # Возврат к списку чатов
        await query.edit_message_text(
            "Выбери чат для настройки:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("➕ Добавить чат", callback_data="add_chat")
            ]])
        )
        return
    
    # Парсим callback data
    parts = data.split('_')
    action = parts[0]
    
    if action in ["toggle", "edit", "banned", "allowed", "flood", "admins"]:
        chat_id = int(parts[-1])
        settings = await db.get_chat_settings(chat_id)
        
        if action == "toggle":
            setting = parts[1]
            if setting in ["welcome", "goodbye", "captcha", "antimat", "antispam", "antilinks", "media"]:
                settings[setting] = not settings[setting]
                await db.update_chat_settings(chat_id, settings)
                await show_chat_settings(update, context, chat_id)
        
        elif action == "edit":
            setting = parts[1]
            if setting == "welcome":
                context.user_data['editing_chat'] = chat_id
                context.user_data['editing_field'] = 'welcome_text'
                await query.edit_message_text(
                    "📝 Отправь новый текст приветствия.\n"
                    "Используй {name} для имени пользователя.\n\n"
                    "Пример: Добро пожаловать, {name}! 🍒"
                )
                return SET_WELCOME
            
            elif setting == "goodbye":
                context.user_data['editing_chat'] = chat_id
                context.user_data['editing_field'] = 'goodbye_text'
                await query.edit_message_text(
                    "📝 Отправь новый текст прощания.\n"
                    "Используй {name} для имени пользователя.\n\n"
                    "Пример: {name} покинул нас... 🥀"
                )
                return SET_GOODBYE
        
        elif action == "banned":
            await query.edit_message_text(
                "🚫 Управление запрещенными словами\n\n"
                "Текущие слова: " + ", ".join(settings['banned_words']) + "\n\n"
                "Отправь слово для добавления или /clear чтобы очистить список",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data=f"back_{chat_id}")
                ]])
            )
            context.user_data['banned_words_chat'] = chat_id
            return ADD_BANNED_WORD
        
        elif action == "allowed":
            await query.edit_message_text(
                "🔗 Управление разрешенными ссылками\n\n"
                "Текущие ссылки: " + ", ".join(settings['allowed_links']) + "\n\n"
                "Отправь домен для добавления (например, t.me) или /clear чтобы очистить список",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data=f"back_{chat_id}")
                ]])
            )
            context.user_data['allowed_links_chat'] = chat_id
            return ADD_ALLOWED_LINK
        
        elif action == "flood":
            keyboard = [
                [InlineKeyboardButton(f"{i} сообщ", callback_data=f"set_flood_limit_{i}_{chat_id}") 
                 for i in [3, 5, 10, 15]],
                [InlineKeyboardButton(f"{i} сек", callback_data=f"set_flood_seconds_{i}_{chat_id}") 
                 for i in [2, 3, 5, 10]],
                [InlineKeyboardButton("◀️ Назад", callback_data=f"back_{chat_id}")]
            ]
            await query.edit_message_text(
                f"📊 Текущие лимиты: {settings['flood_limit']} сообщений за {settings['flood_seconds']} сек\n\n"
                "Выбери новый лимит:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif action == "set":
            setting = parts[1]
            value = int(parts[2])
            chat_id = int(parts[3])
            
            if setting == "flood_limit":
                settings['flood_limit'] = value
            elif setting == "flood_seconds":
                settings['flood_seconds'] = value
            
            await db.update_chat_settings(chat_id, settings)
            await show_chat_settings(update, context, chat_id)
        
        elif action == "admins":
            # Показываем список админов чата
            await show_admins_list(update, context, chat_id)
        
        elif action == "back":
            chat_id = int(parts[1])
            await show_chat_settings(update, context, chat_id)

async def show_admins_list(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Показывает список администраторов чата"""
    query = update.callback_query
    db = context.bot_data['db']
    
    # В реальном боте нужно получать список админов из БД
    # Для примера показываем заглушку
    
    text = f"👥 *Администраторы чата*\n\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Назначить админа", callback_data=f"add_admin_{chat_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data=f"back_{chat_id}")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_welcome_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка текста приветствия"""
    text = update.message.text
    chat_id = context.user_data.get('editing_chat')
    
    if not chat_id:
        await update.message.reply_text("❌ Сессия истекла. Начни заново.")
        return ConversationHandler.END
    
    db = context.bot_data['db']
    settings = await db.get_chat_settings(chat_id)
    settings['welcome_text'] = text
    await db.update_chat_settings(chat_id, settings)
    
    await update.message.reply_text("✅ Текст приветствия обновлен!")
    
    # Возвращаемся к настройкам
    await show_chat_settings(update, context, chat_id)
    return ConversationHandler.END

async def set_goodbye_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка текста прощания"""
    text = update.message.text
    chat_id = context.user_data.get('editing_chat')
    
    if not chat_id:
        await update.message.reply_text("❌ Сессия истекла. Начни заново.")
        return ConversationHandler.END
    
    db = context.bot_data['db']
    settings = await db.get_chat_settings(chat_id)
    settings['goodbye_text'] = text
    await db.update_chat_settings(chat_id, settings)
    
    await update.message.reply_text("✅ Текст прощания обновлен!")
    
    # Возвращаемся к настройкам
    await show_chat_settings(update, context, chat_id)
    return ConversationHandler.END

async def add_banned_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление запрещенного слова"""
    text = update.message.text.strip().lower()
    chat_id = context.user_data.get('banned_words_chat')
    
    if text == '/clear':
        db = context.bot_data['db']
        settings = await db.get_chat_settings(chat_id)
        settings['banned_words'] = []
        await db.update_chat_settings(chat_id, settings)
        await update.message.reply_text("✅ Список запрещенных слов очищен!")
        return ConversationHandler.END
    
    if not chat_id:
        await update.message.reply_text("❌ Сессия истекла. Начни заново.")
        return ConversationHandler.END
    
    db = context.bot_data['db']
    settings = await db.get_chat_settings(chat_id)
    
    if text not in settings['banned_words']:
        settings['banned_words'].append(text)
        await db.update_chat_settings(chat_id, settings)
        await update.message.reply_text(f"✅ Слово '{text}' добавлено в черный список!")
    else:
        await update.message.reply_text(f"❌ Слово '{text}' уже в черном списке!")
    
    # Продолжаем диалог
    return ADD_BANNED_WORD
