from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
from datetime import datetime, timedelta
import config

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /balance"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type == 'private':
        await update.message.reply_text("Эта команда работает только в группах!")
        return
    
    db = context.bot_data['db']
    user_data = await db.get_user(user.id, chat.id)
    
    if not user_data:
        await update.message.reply_text("Ты еще не активен в этом чате! Напиши что-нибудь 😊")
        return
    
    await update.message.reply_text(
        f"🍒 *Баланс {user.first_name}*\n\n"
        f"💰 Барбарисков: *{user_data['balance']}*\n"
        f"💬 Сообщений: *{user_data['messages_count']}*",
        parse_mode='Markdown'
    )

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /top - топ богачей"""
    chat = update.effective_chat
    
    if chat.type == 'private':
        await update.message.reply_text("Эта команда работает только в группах!")
        return
    
    db = context.bot_data['db']
    top_users = await db.get_top_users(chat.id, 10)
    
    if not top_users:
        await update.message.reply_text("В этом чате пока нет активных пользователей 😔")
        return
    
    text = "🏆 *Топ богачей чата*\n\n"
    
    for i, user in enumerate(top_users, 1):
        name = user['first_name'] or user['username'] or f"User_{user['user_id']}"
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
        text += f"{medal} *{i}.* {name} — *{user['balance']}* 🍒\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /premium - покупка премиума"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type == 'private':
        await update.message.reply_text("Эта команда работает только в группах!")
        return
    
    db = context.bot_data['db']
    user_data = await db.get_user(user.id, chat.id)
    
    if not user_data:
        await update.message.reply_text("Сначала напиши что-нибудь в чат!")
        return
    
    if user_data['is_premium'] and user_data['premium_until'] > datetime.now():
        days_left = (user_data['premium_until'] - datetime.now()).days
        await update.message.reply_text(
            f"👑 У тебя уже есть премиум!\n"
            f"Действует до: {user_data['premium_until'].strftime('%d.%m.%Y')}\n"
            f"Осталось дней: {days_left}"
        )
        return
    
    if user_data['balance'] < config.Config.PREMIUM_PRICE:
        await update.message.reply_text(
            f"❌ Недостаточно барбарисков!\n"
            f"Нужно: {config.Config.PREMIUM_PRICE}\n"
            f"У тебя: {user_data['balance']}"
        )
        return
    
    # Создаем клавиатуру для подтверждения
    keyboard = [
        [
            InlineKeyboardButton("✅ Купить", callback_data="buy_premium"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel")
        ]
    ]
    
    await update.message.reply_text(
        f"👑 *Покупка премиума*\n\n"
        f"Стоимость: *{config.Config.PREMIUM_PRICE}* 🍒\n"
        f"Длительность: *{config.Config.PREMIUM_DAYS} дней*\n\n"
        f"*Что даёт премиум:*\n"
        f"• Доступ ко всем 18+ RP командам\n"
        f"• Иконка 👑 в профиле\n"
        f"• Игнорирование антимата\n"
        f"• Возможность записывать голосовое приветствие\n\n"
        f"Подтверждаешь покупку?",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик покупки премиума"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("❌ Покупка отменена")
        return
    
    user = query.from_user
    chat = query.message.chat
    db = context.bot_data['db']
    
    user_data = await db.get_user(user.id, chat.id)
    
    if user_data['balance'] < config.Config.PREMIUM_PRICE:
        await query.edit_message_text("❌ Недостаточно средств для покупки!")
        return
    
    # Списываем средства и выдаем премиум
    await db.add_balance(user.id, chat.id, -config.Config.PREMIUM_PRICE)
    await db.set_premium(user.id, chat.id, config.Config.PREMIUM_DAYS)
    
    await query.edit_message_text(
        "🎉 *Поздравляю!* Ты стал обладателем премиума!\n\n"
        "👑 Тебе доступны все 18+ команды и другие плюшки!\n"
        "Используй /help для просмотра всех команд",
        parse_mode='Markdown'
    )
