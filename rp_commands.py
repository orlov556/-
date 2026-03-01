from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, filters
from datetime import datetime
from utils import RPGenerator, get_random_gif
import config

rp_generator = RPGenerator()

async def rp_command(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, is_adult: bool = False):
    """Базовый обработчик для RP команд"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type == 'private':
        await update.message.reply_text("RP команды работают только в группах!")
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(
            f"❌ Ответь на сообщение пользователя, чтобы {action} его!"
        )
        return
    
    target_user = update.message.reply_to_message.from_user
    
    if target_user.id == user.id:
        await update.message.reply_text("❌ Нельзя применить эту команду к себе!")
        return
    
    # Проверка на премиум для 18+ команд
    if is_adult:
        db = context.bot_data['db']
        user_data = await db.get_user(user.id, chat.id)
        
        if not user_data or not user_data['is_premium'] or user_data['premium_until'] < datetime.now():
            await update.message.reply_text(
                "❌ Эта команда доступна только премиум-пользователям!\n"
                f"Купить премиум: /premium ({config.Config.PREMIUM_PRICE} 🍒)"
            )
            return
    
    # Получаем текст действия
    action_text = rp_generator.get_action_text(
        action,
        f"*{user.first_name}*",
        f"*{target_user.first_name}*"
    )
    
    if not action_text:
        await update.message.reply_text("❌ Неизвестная команда")
        return
    
    # Пробуем получить гифку
    gif_url = await get_random_gif(action, config.Config.TENOR_API_KEY)
    
    if gif_url:
        await update.message.reply_animation(
            animation=gif_url,
            caption=action_text,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(action_text, parse_mode='Markdown')

# Обработчики для каждой команды
async def hug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await rp_command(update, context, 'обнять', False)

async def kiss_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await rp_command(update, context, 'поцеловать', False)

async def pet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await rp_command(update, context, 'погладить', False)

async def bite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await rp_command(update, context, 'укусить', False)

async def slap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await rp_command(update, context, 'шлепнуть', False)

async def wall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await rp_command(update, context, 'прижать_к_стене', True)

async def whisper_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await rp_command(update, context, 'прошептать_на_ушко', True)
