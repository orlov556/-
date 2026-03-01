import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    DATABASE_URL = os.getenv('DATABASE_URL')
    OWNER_ID = int(os.getenv('OWNER_ID', 0))
    ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id]
    TENOR_API_KEY = os.getenv('TENOR_API_KEY', '')
    
    # Настройки по умолчанию
    DEFAULT_WELCOME = "Добро пожаловать в чат, {name}! Будь как дома, читай правила и не спамь барбарисом 🍒"
    DEFAULT_GOODBYE = "{name} покинул нас... Барбарис грустит 🥀"
    
    # Лимиты
    MAX_WARNS = 3
    ANTIFLOOD_MESSAGES = 5
    ANTIFLOOD_SECONDS = 3
    CAPTCHA_TIMEOUT = 300  # 5 минут
    
    # Экономика
    MONEY_PER_MESSAGE = 1
    PREMIUM_PRICE = 5000
    PREMIUM_DAYS = 30
    
    @classmethod
    def validate(cls):
        """Проверяет обязательные переменные окружения"""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не установлен!")
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL не установлен!")
        if not cls.OWNER_ID:
            raise ValueError("OWNER_ID не установлен!")
