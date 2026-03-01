#!/usr/bin/env python3
"""
Барбарис - уютный Telegram бот для модерации, RP и экономики
Аналог IrisBot с расширенным функционалом
"""

import logging
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)
from telegram import Update

import config
from database import Database
from handlers.start import start_command, help_command, profile_command
from handlers.moderation import (
    mute_command, ban_command, warn_command, check_message
)
from handlers.economy import balance_command, top_command, premium_command, premium_callback
from handlers.rp_commands import (
    hug_command, kiss_command, pet_command, bite_command,
    slap_command, wall_command, whisper_command
)
from handlers.marriage import (
    propose_command, marriage_callback, family_command,
    divorce_command, divorce_callback
)
from handlers.admin_settings import (
    chat_settings_command, settings_callback,
    set_welcome_text, set_goodbye_text, add_banned_word, add_allowed_link,
    SET_WELCOME, SET_GOODBYE, ADD_BANNED_WORD, ADD_ALLOWED_LINK
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def error_handler(update: Update, context):
    """Обработчик ошибок"""
    logger.error(f"Update {update} caused error {context.error}")

async def post_init(application: Application):
    """Действия после инициализации бота"""
    # Подключаемся к БД
    db = Database(config.Config.DATABASE_URL)
    await db.connect()
    await db.init_db()
    application.bot_data['db'] = db
    logger.info("Бот успешно запущен!")

async def post_shutdown(application: Application):
    """Действия при остановке бота"""
    db = application.bot_data.get('db')
    if db:
        await db.close()
    logger.info("Бот остановлен")

def main():
    """Основная функция запуска бота"""
    # Создаем приложение
    application = (
        Application.builder()
        .token(config.Config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Регистрируем обработчики команд
    # Основные команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile_command))
    
    # Экономика
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("top", top_command))
    application.add_handler(CommandHandler("premium", premium_command))
    
    # Модерация
    application.add_handler(CommandHandler("mute", mute_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("warn", warn_command))
    
    # RP команды
    application.add_handler(CommandHandler("обнять", hug_command))
    application.add_handler(CommandHandler("поцеловать", kiss_command))
    application.add_handler(CommandHandler("погладить", pet_command))
    application.add_handler(CommandHandler("укусить", bite_command))
    application.add_handler(CommandHandler("шлепнуть", slap_command))
    application.add_handler(CommandHandler("прижать_к_стене", wall_command))
    application.add_handler(CommandHandler("прошептать_на_ушко", whisper_command))
    
    # Браки
    application.add_handler(CommandHandler("заявка", propose_command))
    application.add_handler(CommandHandler("семья", family_command))
    application.add_handler(CommandHandler("развод", divorce_command))
    
    # Настройки чата (только в ЛС)
    application.add_handler(CommandHandler(["чат", "настройки"], chat_settings_command))
    
    # ConversationHandler для настроек
    settings_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(settings_callback, pattern="^(edit_welcome_|edit_goodbye_)")],
        states={
            SET_WELCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_welcome_text)],
            SET_GOODBYE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_goodbye_text)],
            ADD_BANNED_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_banned_word)],
            ADD_ALLOWED_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_allowed_link)],
        },
        fallbacks=[],
        per_message=False
    )
    application.add_handler(settings_conv)
    
    # Callback обработчики
    application.add_handler(CallbackQueryHandler(premium_callback, pattern="^(buy_premium|cancel)$"))
    application.add_handler(CallbackQueryHandler(marriage_callback, pattern="^(accept_marriage|decline_marriage)$"))
    application.add_handler(CallbackQueryHandler(divorce_callback, pattern="^(confirm_divorce|cancel_divorce)$"))
    application.add_handler(CallbackQueryHandler(settings_callback, pattern="^((?!buy_premium|accept_marriage|confirm_divorce).)*$"))
    
    # Обработчик сообщений для модерации
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_message))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)

    # Запускаем бота
    logger.info("Запуск бота Барбарис...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
