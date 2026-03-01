from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from datetime import datetime
import config

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    welcome_text = f"""
🍒 *Добро пожаловать в мир Барбариса, {user.first_name}!*

Я — уютный бот для твоего чата. Помогу модерировать, играть в RP, жениться и просто весело проводить время.

*Что я умею:*
👮‍♂️ *Модерация* — защита от спама, мата, управление чатом
💎 *Экономика* — зарабатывай барбариски за активность
🎭 *RP команды* — обнимашки, поцелуйчики и не только
💍 *Браки* — создавай семьи с другими участниками
🎲 *Гадалка* — задавай вопросы и получай ответы

*Основные команды:*
/help — подробная помощь по всем командам
/profile — твой профиль
/balance — твой баланс
/top — топ богачей чата
/marry — система браков

Нажми на кнопку ниже, чтобы добавить меня в чат! 👇
    """
    
    keyboard = [[
        InlineKeyboardButton("➕ Добавить в чат", url=f"https://t.me/{context.bot.username}?startgroup=true")
    ]]
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
🍒 *Барбарис — полное руководство*

*👮‍♂️ Модерация (для админов)*
/chat — настройки чата (только в ЛС)
/mute [время] [причина] — замутить пользователя
/ban [причина] — забанить
/kick [причина] — кикнуть
/warn [причина] — выдать предупреждение

*💎 Экономика*
/balance — проверить баланс
/top — топ богачей чата
/premium — купить премиум (5000 барбарисков)

*🎭 RP команды*
/обнять [ответ на сообщение]
/поцеловать [ответ на сообщение]
/погладить [ответ на сообщение]
/укусить [ответ на сообщение]
/шлепнуть [ответ на сообщение]
*18+ команды (только премиум):*
/прижать_к_стене
/прошептать_на_ушко

*💍 Браки*
/заявка [ID] — отправить предложение
/согласиться — принять предложение
/отказаться — отклонить
/семья — информация о браке
/развод — развестись

*🎲 Разное*
!вер [вопрос] — спросить у Барбариса

*Статистика*
/profile — твой профиль
/стата — статистика чата

*Административные команды (только владелец бота)*
/setadmin [ID] [роль] — назначить админа чата
    """
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /profile"""
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
    
    # Проверяем брак
    marriage = await db.get_marriage(user.id, chat.id)
    marriage_status = "💔 Не в браке"
    if marriage:
        partner_id = marriage['user2_id'] if marriage['user1_id'] == user.id else marriage['user1_id']
        try:
            partner = await context.bot.get_chat_member(chat.id, partner_id)
            partner_name = partner.user.first_name
            marriage_status = f"💍 В браке с {partner_name} (с {marriage['married_date'].strftime('%d.%m.%Y')})"
        except:
            marriage_status = "💍 В браке"

    profile_text = f"""
🍒 *Профиль {user.first_name}*

📊 *Статистика:*
💬 Сообщений: {user_data['messages_count']}
💰 Барбарисков: {user_data['balance']}
⚠️ Предупреждений: {user_data['warns']}/{config.Config.MAX_WARNS}
👑 Премиум: {'Да' if user_data['is_premium'] else 'Нет'}

💕 *Личная жизнь:*
{marriage_status}

📅 В чате с: {user_data['join_date'].strftime('%d.%m.%Y')}
    """
    
    await update.message.reply_text(profile_text, parse_mode='Markdown')
