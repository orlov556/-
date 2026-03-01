import asyncpg
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import json

class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(self.dsn)

    async def close(self):
        await self.pool.close()

    # Инициализация таблиц
    async def init_db(self):
        async with self.pool.acquire() as conn:
            # Таблица чатов
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id BIGINT PRIMARY KEY,
                    settings JSONB DEFAULT '{
                        "welcome": true,
                        "goodbye": true,
                        "captcha": false,
                        "antimat": true,
                        "antispam": true,
                        "antilinks": false,
                        "media_limit": false,
                        "welcome_text": "Добро пожаловать в чат, {name}! Будь как дома, читай правила и не спамь барбарисом 🍒",
                        "goodbye_text": "{name} покинул нас... Барбарис грустит 🥀",
                        "banned_words": [],
                        "allowed_links": [],
                        "flood_limit": 5,
                        "flood_seconds": 3
                    }'::jsonb,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Таблица пользователей
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT,
                    chat_id BIGINT,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    balance INT DEFAULT 0,
                    warns INT DEFAULT 0,
                    is_premium BOOLEAN DEFAULT FALSE,
                    premium_until TIMESTAMP,
                    messages_count INT DEFAULT 0,
                    join_date TIMESTAMP DEFAULT NOW(),
                    last_message TIMESTAMP,
                    PRIMARY KEY (user_id, chat_id)
                )
            ''')
            
            # Таблица администраторов чатов
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS chat_admins (
                    user_id BIGINT,
                    chat_id BIGINT,
                    role TEXT CHECK (role IN ('owner', 'head_admin', 'admin', 'moderator')),
                    assigned_by BIGINT,
                    assigned_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (user_id, chat_id)
                )
            ''')
            
            # Таблица браков
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS marriages (
                    id SERIAL PRIMARY KEY,
                    user1_id BIGINT,
                    user2_id BIGINT,
                    chat_id BIGINT,
                    married_date TIMESTAMP DEFAULT NOW(),
                    divorced BOOLEAN DEFAULT FALSE,
                    divorced_date TIMESTAMP,
                    UNIQUE(user1_id, user2_id, chat_id)
                )
            ''')
            
            # Таблица предупреждений
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS warnings (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    chat_id BIGINT,
                    moderator_id BIGINT,
                    reason TEXT,
                    date TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Таблица наказаний
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS punishments (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    chat_id BIGINT,
                    type TEXT CHECK (type IN ('mute', 'ban', 'kick')),
                    moderator_id BIGINT,
                    reason TEXT,
                    duration INTERVAL,
                    until TIMESTAMP,
                    active BOOLEAN DEFAULT TRUE,
                    date TIMESTAMP DEFAULT NOW()
                )
            ''')

    # Методы для работы с чатами
    async def get_chat_settings(self, chat_id: int) -> dict:
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                'SELECT settings FROM chats WHERE chat_id = $1',
                chat_id
            )
            if not result:
                # Создаем настройки по умолчанию
                default_settings = {
                    'welcome': True,
                    'goodbye': True,
                    'captcha': False,
                    'antimat': True,
                    'antispam': True,
                    'antilinks': False,
                    'media_limit': False,
                    'welcome_text': 'Добро пожаловать в чат, {name}! Будь как дома, читай правила и не спамь барбарисом 🍒',
                    'goodbye_text': '{name} покинул нас... Барбарис грустит 🥀',
                    'banned_words': [],
                    'allowed_links': [],
                    'flood_limit': 5,
                    'flood_seconds': 3
                }
                await conn.execute(
                    'INSERT INTO chats (chat_id, settings) VALUES ($1, $2)',
                    chat_id, json.dumps(default_settings)
                )
                return default_settings
            return json.loads(result['settings'])

    async def update_chat_settings(self, chat_id: int, settings: dict):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE chats SET settings = $1 WHERE chat_id = $2',
                json.dumps(settings), chat_id
            )

    # Методы для работы с пользователями
    async def get_user(self, user_id: int, chat_id: int) -> dict:
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                'SELECT * FROM users WHERE user_id = $1 AND chat_id = $2',
                user_id, chat_id
            )
            return dict(result) if result else None

    async def update_user_activity(self, user_id: int, chat_id: int, username: str, first_name: str, last_name: str = None):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (user_id, chat_id, username, first_name, last_name, last_message)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (user_id, chat_id) DO UPDATE
                SET username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_message = NOW(),
                    messages_count = users.messages_count + 1,
                    balance = users.balance + 1
            ''', user_id, chat_id, username, first_name, last_name)

    # Методы для экономики
    async def add_balance(self, user_id: int, chat_id: int, amount: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE users SET balance = balance + $1 WHERE user_id = $2 AND chat_id = $3',
                amount, user_id, chat_id
            )

    async def get_top_users(self, chat_id: int, limit: int = 10) -> List[dict]:
        async with self.pool.acquire() as conn:
            results = await conn.fetch('''
                SELECT user_id, username, first_name, balance 
                FROM users 
                WHERE chat_id = $1 
                ORDER BY balance DESC 
                LIMIT $2
            ''', chat_id, limit)
            return [dict(r) for r in results]

    # Методы для премиума
    async def set_premium(self, user_id: int, chat_id: int, days: int):
        async with self.pool.acquire() as conn:
            until = datetime.now() + timedelta(days=days)
            await conn.execute('''
                UPDATE users 
                SET is_premium = TRUE, premium_until = $1 
                WHERE user_id = $2 AND chat_id = $3
            ''', until, user_id, chat_id)

    # Методы для браков
    async def create_marriage(self, user1_id: int, user2_id: int, chat_id: int) -> bool:
        async with self.pool.acquire() as conn:
            # Проверяем, не женаты ли уже
            existing = await conn.fetchval('''
                SELECT id FROM marriages 
                WHERE ((user1_id = $1 AND user2_id = $2) OR (user1_id = $2 AND user2_id = $1))
                AND chat_id = $3 AND divorced = FALSE
            ''', user1_id, user2_id, chat_id)
            
            if existing:
                return False
            
            await conn.execute('''
                INSERT INTO marriages (user1_id, user2_id, chat_id)
                VALUES ($1, $2, $3)
            ''', user1_id, user2_id, chat_id)
            return True

    async def get_marriage(self, user_id: int, chat_id: int) -> dict:
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow('''
                SELECT * FROM marriages 
                WHERE (user1_id = $1 OR user2_id = $1) 
                AND chat_id = $2 AND divorced = FALSE
            ''', user_id, chat_id)
            return dict(result) if result else None

    async def divorce(self, user_id: int, chat_id: int) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute('''
                UPDATE marriages 
                SET divorced = TRUE, divorced_date = NOW()
                WHERE (user1_id = $1 OR user2_id = $1) 
                AND chat_id = $2 AND divorced = FALSE
            ''', user_id, chat_id)
            return result

    # Методы для предупреждений и наказаний
    async def add_warning(self, user_id: int, chat_id: int, moderator_id: int, reason: str):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO warnings (user_id, chat_id, moderator_id, reason)
                VALUES ($1, $2, $3, $4)
            ''', user_id, chat_id, moderator_id, reason)
            
            await conn.execute('''
                UPDATE users SET warns = warns + 1 
                WHERE user_id = $1 AND chat_id = $2
            ''', user_id, chat_id)

    async def get_user_warns(self, user_id: int, chat_id: int) -> int:
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                'SELECT warns FROM users WHERE user_id = $1 AND chat_id = $2',
                user_id, chat_id
            )
            return result or 0

    # Методы для админских ролей
    async def set_admin_role(self, user_id: int, chat_id: int, role: str, assigned_by: int):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO chat_admins (user_id, chat_id, role, assigned_by)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, chat_id) DO UPDATE
                SET role = EXCLUDED.role, assigned_by = EXCLUDED.assigned_by, assigned_at = NOW()
            ''', user_id, chat_id, role, assigned_by)

    async def get_admin_role(self, user_id: int, chat_id: int) -> str:
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                'SELECT role FROM chat_admins WHERE user_id = $1 AND chat_id = $2',
                user_id, chat_id
            )
            return result or 'user'
