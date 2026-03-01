from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from datetime import datetime

async def propose_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /заявка - предложение брака"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type == 'private':
        await update.message.reply_text("Эта команда работает только в группах!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Использование: /заявка [ID пользователя]\n"
            "ID можно узнать, переслав сообщение пользователя в ЛС боту @getidsbot"
        )
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя!")
        return
    
    if target_id == user.id:
        await update.message.reply_text("❌ Нельзя жениться на самом себе!")
        return
    
    # Проверяем, что пользователь существует в чате
    try:
        target_member = await context.bot.get_chat_member(chat.id, target_id)
    except:
        await update.message.reply_text("❌ Пользователь не найден в этом чате!")
        return
    
    db = context.bot_data['db']
    
    # Проверяем, не в браке ли уже
    existing_marriage = await db.get_marriage(user.id, chat.id)
    if existing_marriage:
        await update.message.reply_text("❌ Ты уже состоишь в браке! Сначала разведись.")
        return
    
    existing_marriage_target = await db.get_marriage(target_id, chat.id)
    if existing_marriage_target:
        await update.message.reply_text("❌ Этот пользователь уже состоит в браке!")
        return
    
    # Сохраняем предложение в context.user_data
    context.user_data['proposal'] = {
        'from_user': user.id,
        'to_user': target_id,
        'chat_id': chat.id
    }
    
    # Создаем клавиатуру
    keyboard = [
        [
            InlineKeyboardButton("💍 Согласиться", callback_data="accept_marriage"),
            InlineKeyboardButton("💔 Отказаться", callback_data="decline_marriage")
        ]
    ]
    
    await update.message.reply_text(
        f"💍 *Предложение руки и сердца*\n\n"
        f"{user.first_name} предлагает {target_member.user.first_name} вступить в брак!\n\n"
        f"@{target_member.user.username}, ты согласен(а)?",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def marriage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ответов на предложение брака"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    proposal = context.user_data.get('proposal', {})
    
    if not proposal or user.id != proposal['to_user']:
        await query.edit_message_text("❌ Это предложение не для тебя!")
        return
    
    db = context.bot_data['db']
    
    if query.data == "accept_marriage":
        # Создаем брак
        success = await db.create_marriage(
            proposal['from_user'],
            proposal['to_user'],
            proposal['chat_id']
        )
        
        if success:
            # Получаем имена
            from_member = await context.bot.get_chat_member(
                proposal['chat_id'],
                proposal['from_user']
            )
            
            await query.edit_message_text(
                f"🎉 *Поздравляем!*\n\n"
                f"{from_member.user.first_name} и {user.first_name} теперь муж и жена!\n"
                f"Желаем счастья и много барбарисков! 🍒💕",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "❌ Что-то пошло не так. Возможно, кто-то из вас уже в браке."
            )
    else:
        await query.edit_message_text(
            f"💔 Предложение отклонено... Барбарис грустит 🥀"
        )
    
    # Очищаем предложение
    context.user_data.pop('proposal', None)

async def family_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /семья - информация о браке"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type == 'private':
        await update.message.reply_text("Эта команда работает только в группах!")
        return
    
    db = context.bot_data['db']
    marriage = await db.get_marriage(user.id, chat.id)
    
    if not marriage:
        await update.message.reply_text("💔 Ты пока не в браке. Используй /заявка, чтобы найти свою половинку!")
        return
    
    partner_id = marriage['user2_id'] if marriage['user1_id'] == user.id else marriage['user1_id']
    
    try:
        partner = await context.bot.get_chat_member(chat.id, partner_id)
        partner_name = partner.user.first_name
        
        # Считаем стаж
        days_married = (datetime.now() - marriage['married_date']).days
        years = days_married // 365
        months = (days_married % 365) // 30
        days = days_married % 30
        
        if years > 0:
            duration = f"{years} г. {months} мес. {days} дн."
        elif months > 0:
            duration = f"{months} мес. {days} дн."
        else:
            duration = f"{days} дн."
        
        await update.message.reply_text(
            f"💍 *Семья {user.first_name}*\n\n"
            f"👤 Супруг(а): {partner_name}\n"
            f"📅 Дата свадьбы: {marriage['married_date'].strftime('%d.%m.%Y')}\n"
            f"⏳ Стаж: {duration}\n\n"
            f"❤️ Счастья вашей семье!",
            parse_mode='Markdown'
        )
    except:
        await update.message.reply_text("❌ Не удалось получить информацию о браке")

async def divorce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /развод"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type == 'private':
        await update.message.reply_text("Эта команда работает только в группах!")
        return
    
    db = context.bot_data['db']
    marriage = await db.get_marriage(user.id, chat.id)
    
    if not marriage:
        await update.message.reply_text("💔 Ты и так не в браке!")
        return
    
    # Создаем клавиатуру для подтверждения
    keyboard = [
        [
            InlineKeyboardButton("✅ Развестись", callback_data="confirm_divorce"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_divorce")
        ]
    ]
    
    await update.message.reply_text(
        "⚠️ *Подтверждение развода*\n\n"
        "Ты действительно хочешь развестись? Это действие необратимо!",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def divorce_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик подтверждения развода"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_divorce":
        await query.edit_message_text("❌ Развод отменен. Мир в семье восстановлен! 🕊️")
        return
    
    user = query.from_user
    chat = query.message.chat
    db = context.bot_data['db']
    
    success = await db.divorce(user.id, chat.id)
    
    if success:
        await query.edit_message_text(
            "💔 *Развод оформлен*\n\n"
            "Барбарис грустит... Но жизнь продолжается! 🌈",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text("❌ Не удалось оформить развод")
