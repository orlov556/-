from telegram import Update, ChatMember
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.constants import ChatMemberStatus
from datetime import datetime, timedelta
import re
import config
from utils import ProfanityFilter

profanity_filter = ProfanityFilter()

async def check_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE, required_role: str = 'moderator') -> bool:
    """Проверяет права пользователя в чате"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type == 'private':
        return False
    
    db = context.bot_data['db']
    
    # Владелец бота имеет все права
    if user.id == config.Config.OWNER_ID:
        return True
    
    # Проверяем роль в БД
    role = await db.get_admin_role(user.id, chat.id)
    
    role_hierarchy = {
        'owner': 4,
        'head_admin': 3,
        'admin': 2,
        'moderator': 1,
        'user': 0
    }
    
    required_level = role_hierarchy.get(required_role, 1)
    user_level = role_hierarchy.get(role, 0)
    
    return user_level >= required_level

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /mute"""
    if not await check_permissions(update, context, 'moderator'):
        await update.message.reply_text("❌ У тебя нет прав на эту команду!")
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Ответь на сообщение пользователя, которого хочешь замутить!")
        return
    
    user_to_mute = update.message.reply_to_message.from_user
    chat = update.effective_chat
    
    # Проверяем, что пользователь не админ
    chat_member = await context.bot.get_chat_member(chat.id, user_to_mute.id)
    if chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        await update.message.reply_text("❌ Нельзя замутить администратора!")
        return
    
    # Парсим время
    args = context.args
    mute_time = 60  # 1 час по умолчанию
    reason = "Нарушение правил"
    
    if args:
        time_str = args[0]
        # Парсим время (1h, 30m, 1d)
        match = re.match(r'(\d+)([mhd])', time_str)
        if match:
            value, unit = match.groups()
            value = int(value)
            if unit == 'm':
                mute_time = value * 60
            elif unit == 'h':
                mute_time = value * 3600
            elif unit == 'd':
                mute_time = value * 86400
        
        if len(args) > 1:
            reason = ' '.join(args[1:])
    
    until_date = datetime.now() + timedelta(seconds=mute_time)
    
    try:
        await context.bot.restrict_chat_member(
            chat.id,
            user_to_mute.id,
            until_date=until_date,
            permissions=ChatMember(can_send_messages=False)
        )
        
        # Логируем в чат
        log_text = f"""
🔇 *Пользователь был замучен*
👤 *Нарушитель:* {user_to_mute.full_name} (@{user_to_mute.username})
🛡️ *Модератор:* {update.effective_user.full_name}
⏱️ *Время:* {time_str if args else '1 час'}
📝 *Причина:* {reason}
        """
        
        await update.message.reply_text(log_text, parse_mode='Markdown')
        
        # Сохраняем в БД
        db = context.bot_data['db']
        await db.add_punishment(
            user_to_mute.id, chat.id, 'mute',
            update.effective_user.id, reason,
            timedelta(seconds=mute_time), until_date
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /ban"""
    if not await check_permissions(update, context, 'admin'):
        await update.message.reply_text("❌ У тебя нет прав на эту команду!")
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Ответь на сообщение пользователя, которого хочешь забанить!")
        return
    
    user_to_ban = update.message.reply_to_message.from_user
    chat = update.effective_chat
    
    # Проверяем, что пользователь не админ
    chat_member = await context.bot.get_chat_member(chat.id, user_to_ban.id)
    if chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        await update.message.reply_text("❌ Нельзя забанить администратора!")
        return
    
    reason = ' '.join(context.args) if context.args else "Нарушение правил"
    
    try:
        await context.bot.ban_chat_member(chat.id, user_to_ban.id)
        
        log_text = f"""
⛔ *Пользователь был забанен*
👤 *Нарушитель:* {user_to_ban.full_name} (@{user_to_ban.username})
🛡️ *Модератор:* {update.effective_user.full_name}
📝 *Причина:* {reason}
        """
        
        await update.message.reply_text(log_text, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /warn"""
    if not await check_permissions(update, context, 'moderator'):
        await update.message.reply_text("❌ У тебя нет прав на эту команду!")
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Ответь на сообщение пользователя, которого хочешь предупредить!")
        return
    
    user_to_warn = update.message.reply_to_message.from_user
    chat = update.effective_chat
    db = context.bot_data['db']
    
    reason = ' '.join(context.args) if context.args else "Нарушение правил"
    
    # Добавляем предупреждение
    await db.add_warning(user_to_warn.id, chat.id, update.effective_user.id, reason)
    
    # Проверяем количество предупреждений
    warns_count = await db.get_user_warns(user_to_warn.id, chat.id)
    
    warn_text = f"""
⚠️ *Предупреждение*
👤 *Пользователь:* {user_to_warn.full_name}
📝 *Причина:* {reason}
🔢 *Предупреждений:* {warns_count}/{config.Config.MAX_WARNS}
🛡️ *Модератор:* {update.effective_user.full_name}
    """
    
    await update.message.reply_text(warn_text, parse_mode='Markdown')
    
    # Если достигнут лимит - мут
    if warns_count >= config.Config.MAX_WARNS:
        until_date = datetime.now() + timedelta(hours=24)
        await context.bot.restrict_chat_member(
            chat.id,
            user_to_warn.id,
            until_date=until_date,
            permissions=ChatMember(can_send_messages=False)
        )
        
        await update.message.reply_text(
            f"🚫 {user_to_warn.full_name} получил 3 предупреждения и был замучен на 24 часа!",
            parse_mode='Markdown'
        )

async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка сообщений на мат, спам и ссылки"""
    if not update.message or not update.message.text:
        return
    
    chat = update.effective_chat
    if chat.type == 'private':
        return
    
    user = update.effective_user
    db = context.bot_data['db']
    
    # Получаем настройки чата
    settings = await db.get_chat_settings(chat.id)
    
    # Проверяем премиум статус
    user_data = await db.get_user(user.id, chat.id)
    is_premium = user_data and user_data['is_premium'] and user_data['premium_until'] > datetime.now()
    
    # Антимат
    if settings['antimat'] and not is_premium:
        if profanity_filter.contains_profanity(update.message.text):
            await update.message.delete()
            await context.bot.send_message(
                chat.id,
                f"🚫 {user.first_name}, пожалуйста, не матерись! Барбарис расстроен 🥀"
            )
            return
    
    # Антиспам
    if settings['antispam']:
        # Здесь можно реализовать более сложную логику антиспама
        pass
    
    # Антиссылки
    if settings['antilinks'] and not is_premium:
        link_pattern = r'https?://\S+|www\.\S+'
        if re.search(link_pattern, update.message.text):
            # Проверяем белый список
            allowed = any(link in update.message.text for link in settings['allowed_links'])
            if not allowed:
                await update.message.delete()
                await context.bot.send_message(
                    chat.id,
                    f"🚫 {user.first_name}, ссылки запрещены в этом чате!"
                )
                return
    
    # Обновляем активность пользователя
    await db.update_user_activity(
        user.id, chat.id,
        user.username,
        user.first_name,
        user.last_name
    )
