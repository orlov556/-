import io
import re
import subprocess
import telebot
import os
import json
import random
import sqlite3
import uuid 
import time
import logging
import traceback
import asyncio
from datetime import datetime, timedelta
from telebot import types, util
from telebot.types import InlineQueryResultArticle, InputTextMessageContent
from telebot.types import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
from requests.exceptions import ReadTimeout, ConnectionError
from xxhash import xxh32

# ==================== КОНФИГУРАЦИЯ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ====================

# Токен бота - обязательно через переменную окружения!
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не найден в переменных окружения!")
    print("Добавь переменную BOT_TOKEN в настройках Railway")
    exit(1)

# Опционально: ID владельца и админа тоже можно через переменные
OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # Если не указано, будет 0
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Если не указано, будет 0

print(f"✅ Бот запускается с токеном: {BOT_TOKEN[:5]}...")
if OWNER_ID:
    print(f"✅ Владелец ID: {OWNER_ID}")
if ADMIN_ID:
    print(f"✅ Админ ID: {ADMIN_ID}")

# Загружаем RP-команды из файла
try:
    with open('rp_commands.json', 'r', encoding='utf-8') as f:
        RP_COMMANDS = json.load(f)['commands']
    print(f"✅ Загружено {len(RP_COMMANDS)} RP-команд")
except Exception as e:
    print(f"❌ Ошибка загрузки rp_commands.json: {e}")
    RP_COMMANDS = {}

# Настройки премиума
PREMIUM_CONFIG = {
    "free_commands": [
        "обнять", "поцеловать", "поздравить", "пожать руку",
        "дать пять", "погладить", "похвалить", "извиниться",
        "понюхать", "лизнуть", "потискать", "пригласить на чай"
    ],
    "daily_limit": 15,
    "probability_limit": 10,
    "premium_commands": [
        "отсосать", "самоотсос", "выебать", "трахнуть",
        "изнасиловать", "обкончать", "разорвать очко",
        "довести до сквирта", "оторвать член", "кастрировать",
        "уебать", "расстрелять", "убить", "сжечь", "взорвать",
        "ушатать", "повесить", "закопать", "переехать",
        "связать", "заставить", "унизить", "выпороть",
        "наказать", "забрать в рабство", "подрочить",
        "отдаться", "цыц", "цыц!", "отправить в дурку",
        "вьебать мозги", "записать на ноготочки", "подстричь налысо"
    ],
    "tariffs": {
        "month": {"days": 30, "stars": 50, "name": "🌟 Премиум на месяц"},
        "year": {"days": 365, "stars": 500, "name": "💎 Премиум на год"},
        "vip": {"days": 36500, "stars": 1000, "name": "👑 VIP навсегда"}
    }
}

# ==================== БАЗА ДАННЫХ ====================

def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            hashed_username TEXT PRIMARY KEY,
            user_id INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            nickname TEXT,
            description TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warns (
            user_id TEXT PRIMARY KEY,
            warn_count INTEGER,
            last_warn_time TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_data (
            chat_id TEXT,
            user_id TEXT,
            date TEXT,
            message_count INTEGER DEFAULT 0,
            last_activity TEXT,
            rp_used INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id, date)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            chat_id TEXT PRIMARY KEY,
            chat_title TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS low_admins (
            chat_id TEXT,
            username TEXT,
            PRIMARY KEY (chat_id, username)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rp_requests (
            request_id TEXT PRIMARY KEY,
            chat_id TEXT,
            sender_id INTEGER,
            sender_first_name TEXT,
            target_id INTEGER,
            command TEXT,
            phrase TEXT,
            created_at TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS marriages (
            chat_id TEXT,
            spouse1_id INTEGER,
            spouse2_id INTEGER,
            created_at TEXT,
            PRIMARY KEY (chat_id, spouse1_id, spouse2_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS marriage_requests (
            request_id TEXT PRIMARY KEY,
            chat_id TEXT,
            proposer_id INTEGER,
            proposer_first_name TEXT,
            target_id INTEGER,
            created_at TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            type TEXT DEFAULT 'free',
            expires_at TIMESTAMP,
            stars_paid INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_renewal TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rp_usage (
            user_id INTEGER,
            date DATE,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, date)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS probability_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            question TEXT,
            result INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print('✅ База данных инициализирована')

init_db()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def sha(text):
    return xxh32(str(text)).hexdigest()

def read_users():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT hashed_username, user_id FROM users')
    users = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return users

def write_users(hashed_username, user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO users (hashed_username, user_id) VALUES (?, ?)', (hashed_username, user_id))
    conn.commit()
    conn.close()

def get_nickname(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT nickname FROM user_profiles WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_nickname(user_id, nickname):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO user_profiles (user_id) VALUES (?)', (user_id,))
    cursor.execute('UPDATE user_profiles SET nickname = ? WHERE user_id = ?', (nickname, user_id))
    conn.commit()
    conn.close()

def remove_nickname(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE user_profiles SET nickname = NULL WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_description(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT description FROM user_profiles WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_description(user_id, description):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO user_profiles (user_id) VALUES (?)', (user_id,))
    cursor.execute('UPDATE user_profiles SET description = ? WHERE user_id = ?', (description, user_id))
    conn.commit()
    conn.close()

def remove_description(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE user_profiles SET description = NULL WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_user_subscription(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT type, expires_at FROM subscriptions WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if not result:
        return {'type': 'free', 'expires': None}
    expires = datetime.fromisoformat(result[1]) if result[1] else None
    return {'type': result[0], 'expires': expires}

def set_user_subscription(user_id, sub_type, days, stars_paid):
    expires = datetime.now() + timedelta(days=days)
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO subscriptions (user_id, type, expires_at, stars_paid, created_at, last_renewal)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            type = ?,
            expires_at = ?,
            stars_paid = stars_paid + ?,
            last_renewal = CURRENT_TIMESTAMP
    ''', (user_id, sub_type, expires.isoformat(), stars_paid, sub_type, expires.isoformat(), stars_paid))
    conn.commit()
    conn.close()

def check_rp_limit(user_id):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT count FROM rp_usage WHERE user_id = ? AND date = ?', (user_id, today))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def increment_rp_usage(user_id):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO rp_usage (user_id, date, count)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, date) DO UPDATE SET
            count = count + 1
    ''', (user_id, today))
    conn.commit()
    conn.close()

def check_probability_limit(user_id):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM probability_history WHERE user_id = ? AND date(created_at) = ?', (user_id, today))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def save_probability_question(user_id, username, question, result):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO probability_history (user_id, username, question, result)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, question, result))
    conn.commit()
    conn.close()

def get_probability_history(user_id, limit=5):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT question, result, created_at FROM probability_history 
        WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
    ''', (user_id, limit))
    results = cursor.fetchall()
    conn.close()
    return results

def read_warns():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, warn_count, last_warn_time FROM warns')
    warns = {row[0]: {'warn_count': row[1], 'last_warn_time': row[2]} for row in cursor.fetchall()}
    conn.close()
    return warns

def save_warns(warns):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM warns')
    for user_id, info in warns.items():
        cursor.execute('INSERT INTO warns (user_id, warn_count, last_warn_time) VALUES (?, ?, ?)',
                       (user_id, info['warn_count'], info['last_warn_time']))
    conn.commit()
    conn.close()

def read_la():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id, username FROM low_admins')
    la = {}
    for chat_id, username in cursor.fetchall():
        if chat_id not in la:
            la[chat_id] = []
        la[chat_id].append(username)
    conn.close()
    return la

def write_la(la):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM low_admins')
    for chat_id, usernames in la.items():
        for username in usernames:
            cursor.execute('INSERT INTO low_admins (chat_id, username) VALUES (?, ?)', (chat_id, username))
    conn.commit()
    conn.close()

def save_rp_request(request_id, chat_id, sender_id, target_id, command, phrase, sender_first_name):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('INSERT INTO rp_requests (request_id, chat_id, sender_id, sender_first_name, target_id, command, phrase, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                   (request_id, str(chat_id), sender_id, sender_first_name, target_id, command, phrase, created_at))
    conn.commit()
    conn.close()

def get_rp_request(request_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id, sender_id, sender_first_name, target_id, command, phrase FROM rp_requests WHERE request_id = ?', (request_id,))
    result = cursor.fetchone()
    conn.close()
    return result if result else None

def save_marriage_request(request_id, chat_id, proposer_id, target_id, proposer_first_name):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('INSERT INTO marriage_requests (request_id, chat_id, proposer_id, proposer_first_name, target_id, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                   (request_id, str(chat_id), proposer_id, proposer_first_name, target_id, created_at))
    conn.commit()
    conn.close()

def get_marriage_request(request_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id, proposer_id, proposer_first_name, target_id FROM marriage_requests WHERE request_id = ?', (request_id,))
    result = cursor.fetchone()
    conn.close()
    return result if result else None

def delete_marriage_request(request_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM marriage_requests WHERE request_id = ?', (request_id,))
    conn.commit()
    conn.close()

def is_married(chat_id, user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM marriages WHERE chat_id = ? AND (spouse1_id = ? OR spouse2_id = ?)', (str(chat_id), user_id, user_id))
    result = cursor.fetchone()
    conn.close()
    return bool(result)

def get_spouse(chat_id, user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT spouse1_id, spouse2_id FROM marriages WHERE chat_id = ? AND (spouse1_id = ? OR spouse2_id = ?)', (str(chat_id), user_id, user_id))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[1] if result[0] == user_id else result[0]
    return None

def register_marriage(chat_id, user1_id, user2_id):
    min_id, max_id = sorted([user1_id, user2_id])
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('INSERT OR IGNORE INTO marriages (chat_id, spouse1_id, spouse2_id, created_at) VALUES (?, ?, ?, ?)',
                   (str(chat_id), min_id, max_id, created_at))
    conn.commit()
    conn.close()

def dissolve_marriage(chat_id, user_id):
    spouse_id = get_spouse(chat_id, user_id)
    if spouse_id:
        min_id, max_id = sorted([user_id, spouse_id])
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM marriages WHERE chat_id = ? AND spouse1_id = ? AND spouse2_id = ?',
                       (str(chat_id), min_id, max_id))
        conn.commit()
        conn.close()
        return spouse_id
    return None

def get_all_marriages(chat_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT spouse1_id, spouse2_id, created_at FROM marriages WHERE chat_id = ?', (str(chat_id),))
    results = cursor.fetchall()
    conn.close()
    return results

def get_user_daily_stats(chat_id, user_id):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT message_count FROM user_data WHERE chat_id = ? AND user_id = ? AND date = ?',
                   (str(chat_id), str(user_id), today))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_user_weekly_stats(chat_id, user_id):
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(message_count) FROM user_data WHERE chat_id = ? AND user_id = ? AND date >= ?',
                   (str(chat_id), str(user_id), week_ago))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else 0

def get_user_monthly_stats(chat_id, user_id):
    month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(message_count) FROM user_data WHERE chat_id = ? AND user_id = ? AND date >= ?',
                   (str(chat_id), str(user_id), month_ago))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else 0

def get_user_all_time_stats(chat_id, user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(message_count) FROM user_data WHERE chat_id = ? AND user_id = ?',
                   (str(chat_id), str(user_id)))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else 0

def get_daily_stats(chat_id):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, message_count FROM user_data WHERE chat_id = ? AND date = ?',
                   (str(chat_id), today))
    stats = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return stats

def get_weekly_stats(chat_id):
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, SUM(message_count) FROM user_data WHERE chat_id = ? AND date >= ? GROUP BY user_id',
                   (str(chat_id), week_ago))
    stats = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return stats

def get_monthly_stats(chat_id):
    month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, SUM(message_count) FROM user_data WHERE chat_id = ? AND date >= ? GROUP BY user_id',
                   (str(chat_id), month_ago))
    stats = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return stats

def get_all_time_stats(chat_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, SUM(message_count) FROM user_data WHERE chat_id = ? GROUP BY user_id',
                   (str(chat_id),))
    stats = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return stats

def add_chat_to_db(chat_id, chat_title):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO chats (chat_id, chat_title) VALUES (?, ?)', (str(chat_id), chat_title))
    conn.commit()
    conn.close()

def get_all_chats():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id FROM chats')
    chats = [row[0] for row in cursor.fetchall()]
    conn.close()
    return chats

def save_last_target(chat_id, user_id, target_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO user_data (chat_id, user_id, date, message_count, last_activity) VALUES (?, ?, ?, 0, ?)',
                   (str(chat_id), str(user_id), datetime.now().strftime('%Y-%m-%d'), None))
    cursor.execute('UPDATE user_data SET last_mentioned_target = ? WHERE chat_id = ? AND user_id = ? AND date = ?',
                   (str(target_id), str(chat_id), str(user_id), datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()

def get_last_target(chat_id, user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT last_mentioned_target FROM user_data WHERE chat_id = ? AND user_id = ? AND date = ? LIMIT 1',
                   (str(chat_id), str(user_id), datetime.now().strftime('%Y-%m-%d')))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else None

def get_uptime():
    try:
        result = subprocess.run(['uptime'], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except:
        return ""

def get_profile_addition(chat_id, user_id):
    spouse_id = get_spouse(chat_id, user_id)
    if spouse_id:
        return f"\n💍 В браке"
    return ""

def format_time_ago(datetime_str):
    if not datetime_str:
        return "Нет данных"
    try:
        last_activity_dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        delta = now - last_activity_dt
        if delta.total_seconds() < 60:
            return "только что"
        elif delta.total_seconds() < 3600:
            minutes = int(delta.total_seconds() / 60)
            return f"{minutes} минут назад"
        elif delta.total_seconds() < 86400:
            hours = int(delta.total_seconds() / 3600)
            return f"{hours} часов назад"
        else:
            days = delta.days
            return f"{days} дней назад"
    except:
        return "Неизвестно"

def warn_user(message, user_id):
    user_warns = read_warns()
    if str(user_id) not in user_warns:
        user_warns[str(user_id)] = {'warn_count': 1, 'last_warn_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        bot.reply_to(message, f"{get_name(message)}, Ая-яй, вредим значит? Так нельзя. Пока что просто предупреждаю. Максимум 3 преда, потом - забаню.", parse_mode='HTML')
    else:
        user_warns[str(user_id)]['warn_count'] += 1
        user_warns[str(user_id)]['last_warn_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        bot.reply_to(message, f"{get_name(message)}, Ты опять вредишь? Напоминаю что максимум 3 преда, потом - забаню.", parse_mode='HTML')
    
    if user_warns[str(user_id)]['warn_count'] >= 3:
        bot.reply_to(message, "Я предупреждал...", parse_mode='HTML')
        target = get_target(message)
        if target:
            bot.ban_chat_member(message.chat.id, target)
    
    save_warns(user_warns)

def remove_warn(user_id):
    user_warns = read_warns()
    if str(user_id) in user_warns:
        user_warns[str(user_id)]['warn_count'] -= 1
        if user_warns[str(user_id)]['warn_count'] <= 0:
            del user_warns[str(user_id)]
        save_warns(user_warns)
        return True
    return False

# ==================== НАСТРОЙКИ БОТА ====================

# Логирование
logging.basicConfig(level=logging.INFO)
log_stream = io.StringIO()
logging.basicConfig(stream=log_stream, level=logging.ERROR)

# Известные ошибки
known_errs = {
    'A request to the Telegram API was unsuccessful. Error code: 400. Description: Bad Request: not enough rights to restrict/unrestrict chat member': 'Увы, но у бота не хватает прав для этого.'
}

def catch_error(message, e, err_type=None):
    if not err_type:
        e = str(e)
        print(f"❌ Ошибка: {e}")
        if e in known_errs:
            bot.send_message(message.chat.id, known_errs[e])
        else:
            logging.error(traceback.format_exc())
            err = log_stream.getvalue()
            if ADMIN_ID:
                try:
                    bot.send_message(ADMIN_ID, '❌ Критическая ошибка:\n\n' + telebot.formatting.hcode(err), parse_mode='HTML')
                    bot.send_message(message.chat.id, '❌ Произошла ошибка. Информация отправлена администратору.')
                except:
                    bot.send_message(message.chat.id, '❌ Критическая ошибка:\n\n' + telebot.formatting.hcode(err), parse_mode='HTML')
            else:
                bot.send_message(message.chat.id, '❌ Критическая ошибка:\n\n' + telebot.formatting.hcode(err), parse_mode='HTML')
            log_stream.truncate(0)
            log_stream.seek(0)
    elif err_type == 'no_user':
        bot.send_message(message.chat.id, '❓ А кому это адресовано?')

def retry_bot_call(message, func, *args, **kwargs):
    for attempt in range(3):
        try:
            return func(*args, **kwargs)
        except (ReadTimeout, ConnectionError) as e:
            if attempt < 2:
                time.sleep(1)
            else:
                return None

def get_admins(message):
    try:
        chat = retry_bot_call(message, bot.get_chat, message.chat.id)
        if not chat or chat.type == 'private':
            return []
        admins = retry_bot_call(message, bot.get_chat_administrators, chat_id=message.chat.id)
        if not admins:
            return None
        return [a.user.id for a in admins if a.status == 'creator' or a.can_restrict_members]
    except Exception as e:
        catch_error(message, e)
        return None

def is_anon(message):
    return message.from_user.username in ['Channel_Bot', 'GroupAnonymousBot']

def have_rights(message, set_la=False):
    if message.from_user.id == OWNER_ID:
        return True
    la = read_la()
    if message.from_user.id in get_admins(message):
        return True
    if is_anon(message):
        return True
    if str(message.chat.id) in la and not set_la:
        if str(message.from_user.username) in la[str(message.chat.id)]:
            return True
    bot.reply_to(message, '❌ Недостаточно прав!')
    return False

def get_target(message):
    try:
        users = read_users()
        spl = message.text.split()
        if (len(spl) > 1 and spl[1][0] == '@') or (len(spl) > 2 and spl[2][0] == '@'):
            for i in spl:
                if i[0] == '@':
                    username = i[1:]
                    break
            hashed_username = sha(username.lower())
            return users.get(hashed_username)
        elif message.reply_to_message:
            return message.reply_to_message.from_user.id
        return None
    except:
        return None

def get_name(message):
    try:
        text = message.text.split()
        if len(text) > 1 and text[1].startswith('@'):
            username = text[1][1:]
            users = read_users()
            hashed_username = sha(username.lower())
            if hashed_username in users:
                user_id = users[hashed_username]
                return get_user_link_sync(user_id, message.chat.id)
            return f"@{username}"
        if len(text) > 2 and text[2].startswith('@'):
            username = text[2][1:]
            users = read_users()
            hashed_username = sha(username.lower())
            if hashed_username in users:
                user_id = users[hashed_username]
                return get_user_link_sync(user_id, message.chat.id)
            return f"@{username}"
        target_user = message.reply_to_message.from_user
        display_name = get_nickname(target_user.id) or target_user.first_name
        return f'<a href="tg://user?id={target_user.id}">{display_name}</a>'
    except:
        return "пользователь"

def get_time(message):
    formats = {'s': [1, 'секунд'], 'm': [60, 'минут'], 'h': [3600, 'часов'], 'd': [86400, 'дней']}
    text = message.text.split()[1:]
    for i in text:
        for f in formats:
            if f in i:
                try:
                    num = int(i[:-1])
                    return [num, num * formats[f][0], formats[f][1]]
                except:
                    pass
    return None

def get_user_link_sync(user_id, chat_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        display_name = get_nickname(user_id) or member.user.first_name
        if member.user.username:
            return f'<a href="https://t.me/{member.user.username.lstrip("@")}">{display_name}</a>'
        return display_name
    except:
        return f"Пользователь {user_id}"

def analytic(message):
    if message.from_user.username:
        hashed = sha(message.from_user.username.lower())
        write_users(hashed, message.from_user.id)

# ==================== ИНИЦИАЛИЗАЦИЯ БОТА ====================

bot = telebot.TeleBot(BOT_TOKEN)
print(f'✅ Бот запущен как @{bot.get_me().username}')

# ==================== ОБРАБОТЧИКИ КОМАНД ====================

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.reply_to(message, "👋 Привет, я Барбариска — чат-бот для модерации и RP!\n\n📌 .хелп — список команд")

@bot.message_handler(commands=['list'])
def handle_list(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Только для владельца")
        return
    chats = get_all_chats()
    if not chats:
        bot.send_message(message.chat.id, "Бот не добавлен ни в один чат.")
        return
    text = f"📋 Список чатов ({len(chats)}):\n"
    for chat_id in chats:
        try:
            chat = bot.get_chat(int(chat_id))
            title = chat.title or "Private"
            text += f"- {title} (ID: {chat_id})\n"
        except:
            text += f"- ID: {chat_id}\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_chat_members(message):
    bot_id = bot.get_me().id
    for user in message.new_chat_members:
        if user.id == bot_id:
            chat_title = bot.get_chat(message.chat.id).title
            add_chat_to_db(message.chat.id, chat_title)
        if user.id == OWNER_ID:
            bot.send_message(message.chat.id, "👑 Добро пожаловать, создатель!")

# ==================== ТОПЫ ====================

@bot.message_handler(func=lambda m: m.text and m.text.upper() in ['ТОП ДЕНЬ', 'ТОП ДНЯ'])
def handle_top_day(message):
    chat_id = str(message.chat.id)
    stats = get_daily_stats(chat_id)
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    text = "📊 Топ за сегодня:\n"
    if not sorted_stats:
        text = "Статистика пуста."
    else:
        for i, (user_id, count) in enumerate(sorted_stats):
            user_link = get_user_link_sync(int(user_id), message.chat.id)
            text += f"{i+1}. {user_link}: {count}\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML', disable_notification=True)

@bot.message_handler(func=lambda m: m.text and m.text.upper() in ['ТОП НЕДЕЛЯ', 'ТОП НЕДЕЛИ'])
def handle_top_week(message):
    chat_id = str(message.chat.id)
    stats = get_weekly_stats(chat_id)
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    text = "📊 Топ за неделю:\n"
    if not sorted_stats:
        text = "Статистика пуста."
    else:
        for i, (user_id, count) in enumerate(sorted_stats):
            user_link = get_user_link_sync(int(user_id), message.chat.id)
            text += f"{i+1}. {user_link}: {count}\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML', disable_notification=True)

@bot.message_handler(func=lambda m: m.text and m.text.upper() in ['ТОП МЕСЯЦ', 'ТОП МЕСЯЦА'])
def handle_top_month(message):
    chat_id = str(message.chat.id)
    stats = get_monthly_stats(chat_id)
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    text = "📊 Топ за месяц:\n"
    if not sorted_stats:
        text = "Статистика пуста."
    else:
        for i, (user_id, count) in enumerate(sorted_stats):
            user_link = get_user_link_sync(int(user_id), message.chat.id)
            text += f"{i+1}. {user_link}: {count}\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML', disable_notification=True)

@bot.message_handler(func=lambda m: m.text and m.text.upper() in ['ТОП', 'ТОП ВСЯ'])
def handle_top_all_time(message):
    chat_id = str(message.chat.id)
    stats = get_all_time_stats(chat_id)
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    text = "📊 Топ за всё время:\n"
    if not sorted_stats:
        text = "Статистика пуста."
    else:
        for i, (user_id, count) in enumerate(sorted_stats):
            user_link = get_user_link_sync(int(user_id), message.chat.id)
            text += f"{i+1}. {user_link}: {count}\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML', disable_notification=True)

# ==================== ПРОФИЛЬ ====================

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'КТО Я')
def whoami_command(message):
    user_id = message.from_user.id
    chat_id = str(message.chat.id)
    
    display_name = get_nickname(user_id) or message.from_user.first_name
    username = f'<a href="tg://user?id={user_id}">{display_name}</a>'
    
    daily = get_user_daily_stats(chat_id, user_id)
    weekly = get_user_weekly_stats(chat_id, user_id)
    monthly = get_user_monthly_stats(chat_id, user_id)
    all_time = get_user_all_time_stats(chat_id, user_id)
    
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT last_activity FROM user_data WHERE chat_id = ? AND user_id = ? LIMIT 1',
                   (chat_id, str(user_id)))
    result = cursor.fetchone()
    last_active = format_time_ago(result[0]) if result and result[0] else "Нет данных"
    conn.close()
    
    owner_text = " 👑 Владелец" if user_id == OWNER_ID else ""
    beta_text = ""  # Можно добавить бета-тестеров позже
    desc_text = f"\n📝 {get_description(user_id)}" if get_description(user_id) else ""
    marriage_text = get_profile_addition(chat_id, user_id)
    
    sub = get_user_subscription(user_id)
    premium_text = " 💎 Премиум" if sub['type'] != 'free' and sub['expires'] and sub['expires'] > datetime.now() else ""
    
    text = (f"Ты {username}{owner_text}{beta_text}{premium_text}{desc_text}{marriage_text}\n\n"
            f"Последний актив: {last_active}\n"
            f"Стата (д|н|м|вся): {daily}|{weekly}|{monthly}|{all_time}")
    
    bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith('КТО ТЫ'))
def whois_command(message):
    try:
        target_id = None
        if message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
        else:
            spl = message.text.split()
            for part in spl:
                if part.startswith('@'):
                    username = part[1:]
                    hashed = sha(username.lower())
                    users = read_users()
                    if hashed in users:
                        target_id = users[hashed]
                        break
        
        if not target_id:
            bot.reply_to(message, "❓ Укажи пользователя: ответь на сообщение или напиши @username")
            return
        
        chat_id = str(message.chat.id)
        member = bot.get_chat_member(message.chat.id, target_id)
        display_name = get_nickname(target_id) or member.user.first_name
        username = f'<a href="tg://user?id={target_id}">{display_name}</a>'
        
        daily = get_user_daily_stats(chat_id, target_id)
        weekly = get_user_weekly_stats(chat_id, target_id)
        monthly = get_user_monthly_stats(chat_id, target_id)
        all_time = get_user_all_time_stats(chat_id, target_id)
        
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute('SELECT last_activity FROM user_data WHERE chat_id = ? AND user_id = ? LIMIT 1',
                       (chat_id, str(target_id)))
        result = cursor.fetchone()
        last_active = format_time_ago(result[0]) if result and result[0] else "Нет данных"
        conn.close()
        
        owner_text = " 👑 Владелец" if target_id == OWNER_ID else ""
        desc_text = f"\n📝 {get_description(target_id)}" if get_description(target_id) else ""
        marriage_text = get_profile_addition(chat_id, target_id)
        
        sub = get_user_subscription(target_id)
        premium_text = " 💎 Премиум" if sub['type'] != 'free' and sub['expires'] and sub['expires'] > datetime.now() else ""
        
        text = (f"Это {username}{owner_text}{premium_text}{desc_text}{marriage_text}\n\n"
                f"Последний актив: {last_active}\n"
                f"Стата (д|н|м|вся): {daily}|{weekly}|{monthly}|{all_time}")
        
        bot.reply_to(message, text, parse_mode='HTML')
    except Exception as e:
        catch_error(message, e)

# ==================== НИКИ И ОПИСАНИЯ ====================

@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith('+НИК '))
def set_nick_command(message):
    nick = message.text[5:].strip()
    if nick:
        set_nickname(message.from_user.id, nick)
        bot.reply_to(message, f"✅ Ник установлен: {nick}")
    else:
        bot.reply_to(message, "❓ Укажи ник после +ник")

@bot.message_handler(func=lambda m: m.text and m.text.upper() == '-НИК')
def remove_nick_command(message):
    remove_nickname(message.from_user.id)
    bot.reply_to(message, "✅ Ник сброшен")

@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith('+ОПИСАНИЕ '))
def set_desc_command(message):
    desc = message.text[10:].strip()
    if desc:
        set_description(message.from_user.id, desc)
        bot.reply_to(message, f"✅ Описание установлено: {desc}")
    else:
        bot.reply_to(message, "❓ Укажи описание после +описание")

@bot.message_handler(func=lambda m: m.text and m.text.upper() == '-ОПИСАНИЕ')
def remove_desc_command(message):
    remove_description(message.from_user.id)
    bot.reply_to(message, "✅ Описание сброшено")

# ==================== ПРЕМИУМ ====================

@bot.message_handler(commands=['premium'])
def premium_command(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for key, tariff in PREMIUM_CONFIG['tariffs'].items():
        btn = types.InlineKeyboardButton(
            f"{tariff['name']} — {tariff['stars']} ⭐",
            callback_data=f"buy_{key}"
        )
        markup.add(btn)
    
    free_info = (
        f"🎁 Бесплатный тариф:\n"
        f"• {len(PREMIUM_CONFIG['free_commands'])} базовых RP-команд\n"
        f"• {PREMIUM_CONFIG['daily_limit']} RP-действий в день\n"
        f"• {PREMIUM_CONFIG['probability_limit']} !вероятность в день\n\n"
        f"💎 Премиум:\n"
        f"• Все {len(RP_COMMANDS)} RP-команд\n"
        f"• Безлимитное использование\n"
        f"• Эксклюзивные 18+ команды\n"
        f"• Безлимит !вероятность"
    )
    
    bot.send_message(
        message.chat.id,
        f"🌟 Премиум-доступ\n\n{free_info}",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def buy_premium_callback(call):
    tariff_key = call.data.replace('buy_', '')
    tariff = PREMIUM_CONFIG['tariffs'].get(tariff_key)
    
    if not tariff:
        bot.answer_callback_query(call.id, "❌ Тариф не найден")
        return
    
    prices = [types.LabeledPrice(label=tariff['name'], amount=tariff['stars'])]
    
    bot.send_invoice(
        call.message.chat.id,
        title=tariff['name'],
        description=f"Доступ на {tariff['days']} дней ко всем RP-командам",
        invoice_payload=f"premium_{tariff_key}_{tariff['days']}_{tariff['stars']}",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="premium"
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout_query(pre_checkout_q):
    bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def successful_payment(message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split('_')
    tariff_key = parts[1]
    days = int(parts[2])
    stars = int(parts[3])
    
    set_user_subscription(
        message.from_user.id,
        'premium' if days < 365 else 'vip',
        days,
        stars
    )
    
    bot.send_message(
        message.chat.id,
        f"✅ Премиум активирован на {days} дней!\n"
        f"✨ Тебе доступны все {len(RP_COMMANDS)} RP-команд без лимитов!"
    )

@bot.message_handler(commands=['my_sub'])
def my_subscription(message):
    sub = get_user_subscription(message.from_user.id)
    
    if sub['type'] == 'free':
        rp_used = check_rp_limit(message.from_user.id)
        prob_used = check_probability_limit(message.from_user.id)
        text = (
            f"🎁 Твой тариф: Бесплатный\n"
            f"📊 RP сегодня: {rp_used}/{PREMIUM_CONFIG['daily_limit']}\n"
            f"📊 !вероятность сегодня: {prob_used}/{PREMIUM_CONFIG['probability_limit']}\n\n"
            f"💎 Купи премиум: /premium"
        )
    else:
        expires = sub['expires']
        if expires and expires > datetime.now():
            days_left = (expires - datetime.now()).days
            text = (
                f"💎 Твой тариф: {sub['type'].upper()}\n"
                f"⏳ Осталось дней: {days_left}\n"
                f"✨ Доступны все RP-команды без лимитов"
            )
        else:
            text = "❌ Срок подписки истёк. /premium"
    
    bot.reply_to(message, text)

# ==================== ВЕРОЯТНОСТЬ ====================

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith('!вероятность'))
def probability_command(message):
    try:
        text = message.text[12:].strip()
        if not text:
            bot.reply_to(message, "❓ Пример: !вероятность Андрей лох?")
            return
        
        user_id = message.from_user.id
        
        sub = get_user_subscription(user_id)
        is_premium = sub['type'] != 'free' and sub['expires'] and sub['expires'] > datetime.now()
        
        if not is_premium:
            used_today = check_probability_limit(user_id)
            if used_today >= PREMIUM_CONFIG['probability_limit']:
                bot.reply_to(
                    message,
                    f"❌ Сегодняшний лимит ({PREMIUM_CONFIG['probability_limit']}) исчерпан!\n"
                    f"Купи премиум для безлимита: /premium"
                )
                return
        
        probability = random.randint(0, 100)
        
        username = message.from_user.username or f"id{user_id}"
        save_probability_question(user_id, username, text, probability)
        
        if probability < 10:
            emoji = "😱"
            comment = "Абсолютно невероятно!"
        elif probability < 30:
            emoji = "🤔"
            comment = "Маловероятно"
        elif probability < 50:
            emoji = "😐"
            comment = "50 на 50"
        elif probability < 70:
            emoji = "😏"
            comment = "Скорее да"
        elif probability < 90:
            emoji = "😎"
            comment = "Очень вероятно"
        else:
            emoji = "🔥"
            comment = "Неизбежно!"
        
        response = f"🎲 <b>Вопрос:</b> {text}\n\n📊 <b>Ответ:</b> {probability}%\n{emoji} {comment}"
        bot.reply_to(message, response, parse_mode='HTML')
        
    except Exception as e:
        catch_error(message, e)

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith('!вер'))
def probability_short_command(message):
    text = message.text[4:].strip()
    message.text = f"!вероятность {text}"
    probability_command(message)

@bot.message_handler(commands=['вероятность_стата'])
def probability_stats_command(message):
    history = get_probability_history(message.from_user.id)
    
    if not history:
        bot.reply_to(message, "📊 У тебя пока нет истории запросов.")
        return
    
    text = "📊 Твои последние запросы:\n\n"
    for question, result, created in history:
        time_str = datetime.strptime(created, '%Y-%m-%d %H:%M:%S').strftime('%H:%M')
        text += f"• {question[:30]}... → {result}% ({time_str})\n"
    
    bot.reply_to(message, text)

# ==================== RP-КОМАНДЫ ====================

@bot.message_handler(func=lambda message: True)
def handle_rp_commands(message):
    if not message.text:
        return
    
    analytic(message)
    
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)
    date = datetime.now().strftime('%Y-%m-%d')
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT message_count FROM user_data WHERE chat_id = ? AND user_id = ? AND date = ?',
                   (chat_id, user_id, date))
    result = cursor.fetchone()
    if result:
        cursor.execute('UPDATE user_data SET message_count = ?, last_activity = ? WHERE chat_id = ? AND user_id = ? AND date = ?',
                       (result[0] + 1, current_time, chat_id, user_id, date))
    else:
        cursor.execute('INSERT INTO user_data (chat_id, user_id, date, message_count, last_activity) VALUES (?, ?, ?, ?, ?)',
                       (chat_id, user_id, date, 1, current_time))
    conn.commit()
    conn.close()
    
    text = message.text.lower().strip()
    command = None
    for cmd in RP_COMMANDS.keys():
        if text.startswith(cmd):
            command = cmd
            break
    
    if not command:
        return
    
    user_id_num = message.from_user.id
    
    sub = get_user_subscription(user_id_num)
    is_premium = sub['type'] != 'free' and sub['expires'] and sub['expires'] > datetime.now()
    
    if command in PREMIUM_CONFIG['premium_commands'] and not is_premium:
        bot.reply_to(
            message,
            f"❌ Команда '{command}' только для премиум!\nКупить: /premium"
        )
        return
    
    if not is_premium:
        used_today = check_rp_limit(user_id_num)
        if used_today >= PREMIUM_CONFIG['daily_limit']:
            bot.reply_to(
                message,
                f"❌ Сегодняшний лимит ({PREMIUM_CONFIG['daily_limit']}) исчерпан!\n"
                f"Завтра будет новый день или купи премиум: /premium"
            )
            return
        increment_rp_usage(user_id_num)
    
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        target_name = get_name(message)
    else:
        target_name = f'<a href="tg://user?id={user_id_num}">{message.from_user.first_name}</a>'
    
    sender_name = get_nickname(user_id_num) or message.from_user.first_name
    
    cmd_data = RP_COMMANDS[command]
    
    if random.random() < 0.3:
        response = cmd_data['reject'].format(sender=sender_name, target=target_name)
    else:
        response = cmd_data['accept'].format(sender=sender_name, target=target_name)
        if 'random_parts' in cmd_data and '{random_part}' in response:
            response = response.replace('{random_part}', random.choice(cmd_data['random_parts']))
    
    bot.reply_to(message, response, parse_mode='HTML')

# ==================== МОДЕРАЦИЯ ====================

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'ВАРН')
def warn_command(message):
    try:
        if have_rights(message):
            if message.reply_to_message:
                user_id = message.reply_to_message.from_user.id
                warn_user(message, user_id)
            else:
                bot.reply_to(message, "❓ Команда должна быть ответом на сообщение")
    except:
        pass

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'СНЯТЬ ВАРН')
def unwarn_command(message):
    try:
        if have_rights(message):
            if message.reply_to_message:
                user_id = message.reply_to_message.from_user.id
                if remove_warn(user_id):
                    bot.reply_to(message, f"✅ Предупреждение снято")
                else:
                    bot.reply_to(message, "❌ У пользователя нет предупреждений")
            else:
                bot.reply_to(message, "❓ Команда должна быть ответом на сообщение")
    except:
        pass

@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith('МУТ'))
def mute_command(message):
    try:
        if have_rights(message):
            target = get_target(message)
            time_val = get_time(message)
            
            if not target:
                if message.reply_to_message and message.reply_to_message.from_user.id == OWNER_ID:
                    bot.reply_to(message, "🤫 Я заклеил ему рот")
                    return
                catch_error(message, None, 'no_user')
                return
            
            if target == OWNER_ID:
                bot.reply_to(message, "🤫 Я заклеил ему рот")
                return
            
            if time_val:
                bot.restrict_chat_member(message.chat.id, target, until_date=message.date + time_val[1])
                bot.reply_to(message, f"🤫 Замучен на {time_val[0]} {time_val[2]}")
            else:
                bot.restrict_chat_member(message.chat.id, target, until_date=message.date)
                bot.reply_to(message, f"🤫 Замучен")
    except Exception as e:
        catch_error(message, e)

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'РАЗМУТ')
def unmute_command(message):
    try:
        if have_rights(message):
            target = get_target(message)
            if target:
                bot.restrict_chat_member(
                    message.chat.id, target,
                    can_send_messages=True,
                    can_send_other_messages=True,
                    can_send_polls=True,
                    can_add_web_page_previews=True
                )
                bot.reply_to(message, "✅ Размучен")
            else:
                catch_error(message, None, 'no_user')
    except Exception as e:
        catch_error(message, e)

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'КИК')
def kick_command(message):
    try:
        if have_rights(message):
            target = get_target(message)
            if target:
                bot.ban_chat_member(message.chat.id, target)
                bot.unban_chat_member(message.chat.id, target)
                bot.reply_to(message, "👢 Кикнут")
            else:
                catch_error(message, None, 'no_user')
    except Exception as e:
        catch_error(message, e)

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'БАН')
def ban_command(message):
    try:
        if have_rights(message):
            target = get_target(message)
            
            if not target:
                if message.reply_to_message and message.reply_to_message.from_user.id == OWNER_ID:
                    bot.ban_chat_member(message.chat.id, OWNER_ID)
                    bot.unban_chat_member(message.chat.id, OWNER_ID)
                    bot.reply_to(message, "🔨 Изгнан")
                    return
                catch_error(message, None, 'no_user')
                return
            
            if target == OWNER_ID:
                bot.ban_chat_member(message.chat.id, target)
                bot.unban_chat_member(message.chat.id, target)
                bot.reply_to(message, "🔨 Изгнан")
            else:
                bot.ban_chat_member(message.chat.id, target)
                bot.reply_to(message, "🔨 Забанен навсегда")
    except Exception as e:
        catch_error(message, e)

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'РАЗБАН')
def unban_command(message):
    try:
        if have_rights(message):
            target = get_target(message)
            if target:
                bot.unban_chat_member(message.chat.id, target)
                bot.reply_to(message, "✅ Разбанен")
            else:
                catch_error(message, None, 'no_user')
    except Exception as e:
        catch_error(message, e)

@bot.message_handler(func=lambda m: m.text and m.text.upper() == '-СМС')
def delete_message_command(message):
    try:
        if have_rights(message) and message.reply_to_message:
            bot.delete_message(message.chat.id, message.reply_to_message.id)
            bot.delete_message(message.chat.id, message.id)
    except Exception as e:
        catch_error(message, e)

@bot.message_handler(func=lambda m: m.text and m.text.upper() == '+ЧАТ')
def open_chat_command(message):
    try:
        if have_rights(message):
            bot.set_chat_permissions(message.chat.id, types.ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            ))
            bot.reply_to(message, "✅ Чат открыт")
    except Exception as e:
        catch_error(message, e)

@bot.message_handler(func=lambda m: m.text and m.text.upper() == '-ЧАТ')
def close_chat_command(message):
    try:
        if have_rights(message):
            bot.set_chat_permissions(message.chat.id, types.ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            ))
            try:
                bot.restrict_chat_member(message.chat.id, OWNER_ID,
                    can_send_messages=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True)
            except:
                pass
            bot.reply_to(message, "🔇 Чат закрыт")
    except Exception as e:
        catch_error(message, e)

@bot.message_handler(func=lambda m: m.text and m.text.upper() in ['ПИН', 'ЗАКРЕП'])
def pin_command(message):
    try:
        if have_rights(message) and message.reply_to_message:
            bot.pin_chat_message(message.chat.id, message.reply_to_message.id)
            bot.reply_to(message, "📌 Закреплено")
    except:
        pass

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'АНПИН')
def unpin_command(message):
    try:
        if have_rights(message) and message.reply_to_message:
            bot.unpin_chat_message(message.chat.id, message.reply_to_message.id)
            bot.reply_to(message, "📌 Откреплено")
    except:
        pass

@bot.message_handler(func=lambda m: m.text and m.text.upper() == '+АДМИН')
def promote_command(message):
    try:
        if message.from_user.id == OWNER_ID and message.reply_to_message:
            user_id = message.reply_to_message.from_user.id
            bot.promote_chat_member(
                message.chat.id, user_id,
                can_manage_chat=True,
                can_change_info=True,
                can_delete_messages=True,
                can_restrict_members=True,
                can_invite_users=True,
                can_pin_messages=True
            )
            bot.reply_to(message, "👑 Админ назначен")
    except:
        pass

@bot.message_handler(func=lambda m: m.text and m.text.upper() == '-АДМИН')
def demote_command(message):
    try:
        if message.from_user.id == OWNER_ID and message.reply_to_message:
            user_id = message.reply_to_message.from_user.id
            bot.promote_chat_member(
                message.chat.id, user_id,
                can_manage_chat=False,
                can_change_info=False,
                can_delete_messages=False,
                can_restrict_members=False,
                can_invite_users=False,
                can_pin_messages=False
            )
            bot.reply_to(message, "👤 Админ снят")
    except:
        pass

# ==================== БРАКИ ====================

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'БРАК')
def marry_command(message):
    try:
        if not message.reply_to_message:
            bot.reply_to(message, "❓ Ответь на сообщение того, с кем хочешь вступить в брак")
            return
        
        target_id = message.reply_to_message.from_user.id
        proposer_id = message.from_user.id
        
        if proposer_id == target_id:
            bot.reply_to(message, "❌ Нельзя жениться на себе")
            return
        
        if is_married(message.chat.id, proposer_id):
            bot.reply_to(message, "❌ Ты уже в браке")
            return
        
        if is_married(message.chat.id, target_id):
            bot.reply_to(message, "❌ Этот пользователь уже в браке")
            return
        
        request_id = str(uuid.uuid4())
        save_marriage_request(request_id, message.chat.id, proposer_id, target_id, message.from_user.first_name)
        
        proposer_link = get_user_link_sync(proposer_id, message.chat.id)
        target_link = get_user_link_sync(target_id, message.chat.id)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("💍 Согласиться", callback_data=f"marriage_agree_{request_id}"),
            types.InlineKeyboardButton("❌ Отказаться", callback_data=f"marriage_reject_{request_id}")
        )
        
        bot.send_message(message.chat.id, f"{proposer_link} предлагает брак {target_link}!", parse_mode='HTML', reply_markup=markup)
    except Exception as e:
        catch_error(message, e)

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'РАЗВОД')
def divorce_command(message):
    try:
        user_id = message.from_user.id
        spouse_id = dissolve_marriage(message.chat.id, user_id)
        if spouse_id:
            bot.reply_to(message, f"💔 Развод оформлен")
        else:
            bot.reply_to(message, "❌ Ты не в браке")
    except Exception as e:
        catch_error(message, e)

@bot.message_handler(func=lambda m: m.text and m.text.upper() in ['БРАКИ', 'СПИСОК БРАКОВ'])
def list_marriages_command(message):
    try:
        marriages = get_all_marriages(message.chat.id)
        if not marriages:
            bot.reply_to(message, "💔 В этом чате нет браков")
            return
        
        text = "💍 Список браков:\n"
        for i, (sp1, sp2, created_str) in enumerate(marriages, 1):
            link1 = get_user_link_sync(sp1, message.chat.id)
            link2 = get_user_link_sync(sp2, message.chat.id)
            created = datetime.strptime(created_str, '%Y-%m-%d %H:%M:%S')
            days = (datetime.now() - created).days
            text += f"{i}. {link1} 💍 {link2} ({days} дн.)\n"
        
        bot.send_message(message.chat.id, text, parse_mode='HTML')
    except Exception as e:
        catch_error(message, e)

@bot.callback_query_handler(func=lambda call: call.data.startswith('marriage_'))
def handle_marriage_callback(call):
    try:
        parts = call.data.split('_')
        if len(parts) != 3:
            bot.answer_callback_query(call.id, "❌ Неверный формат")
            return
        
        action, request_id = parts[1], parts[2]
        request = get_marriage_request(request_id)
        
        if not request:
            bot.answer_callback_query(call.id, "❌ Запрос устарел")
            return
        
        chat_id, proposer_id, proposer_name, target_id = request
        
        if call.from_user.id != target_id:
            bot.answer_callback_query(call.id, "❌ Только адресат может ответить")
            return
        
        proposer_link = get_user_link_sync(proposer_id, int(chat_id))
        target_link = get_user_link_sync(target_id, int(chat_id))
        
        if action == 'agree':
            if is_married(int(chat_id), proposer_id) or is_married(int(chat_id), target_id):
                response = "❌ Один из вас уже в браке"
            else:
                register_marriage(int(chat_id), proposer_id, target_id)
                response = f"💍 Брак заключен между {proposer_link} и {target_link}!"
        else:
            response = f"💔 {target_link} отказался от предложения {proposer_link}"
        
        if call.message:
            bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='HTML')
        
        delete_marriage_request(request_id)
        bot.answer_callback_query(call.id, "✅ Готово")
    except Exception as e:
        logging.error(f"Marriage callback error: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка")

# ==================== ПРОЧИЕ КОМАНДЫ ====================

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'КАКАЯ НАГРУЗКА')
def uptime_command(message):
    uptime = get_uptime()
    bot.reply_to(message, f"📊 uptime:\n{uptime}")

@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith('РАНДОМ '))
def random_command(message):
    try:
        parts = message.text.upper().replace('РАНДОМ ', '').split()
        if len(parts) >= 2:
            min_val = int(parts[0])
            max_val = int(parts[1])
            if min_val > max_val:
                bot.reply_to(message, "❌ Минимум больше максимума")
            elif min_val == max_val:
                bot.reply_to(message, f"🤔 Это просто {min_val}")
            else:
                result = random.randint(min_val, max_val)
                bot.reply_to(message, f"🎲 Случайное число: {result}")
    except:
        pass

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'ПИНГ')
def ping_command(message):
    bot.reply_to(message, "ПОНГ 🏓")

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'КИНГ')
def king_command(message):
    bot.reply_to(message, "КОНГ 🦍")

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'БОТ')
def bot_check_command(message):
    bot.reply_to(message, "✅ На месте")

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'ЧТО С БОТОМ')
def what_bot_command(message):
    bot.reply_to(message, "😴 Отдыхаю...")

@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith('БАРБАРИС СКАЖИ '))
def say_command(message):
    text = message.text[14:]
    user = message.from_user.first_name
    user_id = message.from_user.id
    bot.send_message(message.chat.id, f"[{user}](tg://user?id={user_id}) сказал: {text}", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith('БАРБАРИС, СКАЖИ '))
def say_comma_command(message):
    text = message.text[15:]
    user = message.from_user.first_name
    user_id = message.from_user.id
    bot.send_message(message.chat.id, f"[{user}](tg://user?id={user_id}) сказал: {text}", parse_mode='Markdown')

# ==================== ПОМОЩЬ ====================

@bot.message_handler(func=lambda m: m.text and m.text.upper() == '.ХЕЛП')
def help_command(message):
    try:
        user_id = message.from_user.id
        sub = get_user_subscription(user_id)
        is_premium = sub['type'] != 'free' and sub['expires'] and sub['expires'] > datetime.now()
        
        help_text = "<b>📚 Помощь по командам</b>\n\n"
        
        help_text += """<blockquote expandable><b>🛡️ Модерация</b>
Бан / Разбан - Блокировка
Кик - Изгнание
Мут [2m/2h] / Размут - Запрет сообщений
Варн / Снять варн - Предупреждения
-смс - Удалить сообщение
+чат / -чат - Открыть/закрыть чат
Пин / Анпин - Закрепить/открепить
+админ / -админ - Выдача прав (только владелец)</blockquote>\n"""
        
        help_text += """<blockquote expandable><b>📊 Статистика</b>
Топ дня / Топ недели / Топ месяца / Топ вся - Рейтинги
Кто я - Свой профиль
Кто ты @user - Профиль пользователя
+ник / -ник - Установить ник
+описание / -описание - Установить описание</blockquote>\n"""
        
        help_text += """<blockquote expandable><b>🎮 Развлечения</b>
Рандом a b - Случайное число
!вероятность [вопрос] - Узнать вероятность
!вер - Сокращённая версия
Брак / Развод - Браки
Барбарис, скажи ... - Повторялка
Пинг / Кинг / Бот - Проверка
Какая нагрузка - Статус сервера</blockquote>\n"""
        
        help_text_rp = "<blockquote expandable><b>💕 RP-команды</b>\n"
        
        if is_premium:
            for cmd in sorted(RP_COMMANDS.keys())[:30]:
                desc = RP_COMMANDS[cmd].get('description', cmd)
                help_text_rp += f"• <code>{cmd}</code>: {desc}\n"
            help_text_rp += f"\n✨ Всего команд: {len(RP_COMMANDS)}"
        else:
            for cmd in sorted(PREMIUM_CONFIG['free_commands']):
                desc = RP_COMMANDS[cmd].get('description', cmd)
                help_text_rp += f"• <code>{cmd}</code>: {desc}\n"
            
            rp_used = check_rp_limit(user_id)
            left = PREMIUM_CONFIG['daily_limit'] - rp_used
            
            help_text_rp += f"\n📊 Сегодня RP: {rp_used}/{PREMIUM_CONFIG['daily_limit']}\n"
            help_text_rp += f"💎 Ещё {len(PREMIUM_CONFIG['premium_commands'])} команд в премиуме\n"
            help_text_rp += f"👉 /premium - открыть премиум"
        
        help_text_rp += "</blockquote>"
        
        help_text += "<blockquote><b>💰 Премиум</b>\n/premium - Купить доступ\n/my_sub - Статус подписки</blockquote>"
        
        bot.reply_to(message, help_text, parse_mode='HTML')
        bot.send_message(message.chat.id, help_text_rp, parse_mode='HTML')
    except Exception as e:
        catch_error(message, e)

# ==================== INLINE RP ====================

@bot.inline_handler(lambda query: True)
def handle_inline_query(query):
    try:
        text = query.query.strip().lower()
        if not text:
            return
        
        command = None
        for cmd in sorted(RP_COMMANDS.keys(), key=len, reverse=True):
            if text.startswith(cmd):
                command = cmd
                break
        
        if not command:
            return
        
        sender_id = query.from_user.id
        sender_name = get_nickname(sender_id) or query.from_user.first_name
        
        request_text = RP_COMMANDS[command]['request'].format(sender=sender_name)
        
        request_id = str(uuid.uuid4())
        save_rp_request(request_id, 0, sender_id, 0, command, text[len(command):].strip(), query.from_user.first_name)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Принять", callback_data=f"rp_accept_{request_id}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"rp_reject_{request_id}")
        )
        
        results = [
            types.InlineQueryResultArticle(
                id=request_id,
                title=command.capitalize(),
                input_message_content=types.InputTextMessageContent(
                    request_text,
                    parse_mode='HTML'
                ),
                description=text[len(command):].strip()[:50] or f"RP: {command}",
                reply_markup=markup
            )
        ]
        bot.answer_inline_query(query.id, results, cache_time=1)
    except Exception as e:
        print(f"Inline error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('rp_'))
def handle_rp_callback(call):
    try:
        _, action, request_id = call.data.split('_', 2)
        
        request = get_rp_request(request_id)
        if not request:
            bot.answer_callback_query(call.id, "❌ Запрос устарел")
            return
        
        chat_id, sender_id, sender_name, target_id, command, phrase = request
        
        if call.from_user.id != target_id and target_id != 0:
            bot.answer_callback_query(call.id, "❌ Только адресат может ответить")
            return
        
        sender_display = get_nickname(sender_id) or sender_name
        target_display = get_nickname(call.from_user.id) or call.from_user.first_name
        target_link = f'<a href="tg://user?id={call.from_user.id}">{target_display}</a>'
        
        if command in RP_COMMANDS:
            if action == 'accept':
                response = RP_COMMANDS[command]['accept'].format(sender=sender_display, target=target_link)
                if '{random_part}' in response and 'random_parts' in RP_COMMANDS[command]:
                    response = response.replace('{random_part}', random.choice(RP_COMMANDS[command]['random_parts']))
            else:
                response = RP_COMMANDS[command]['reject'].format(sender=sender_display, target=target_link)
            
            if phrase:
                response += f"\n💬 {phrase}"
        
        if call.message:
            bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='HTML')
        elif call.inline_message_id:
            bot.edit_message_text(response, inline_message_id=call.inline_message_id, parse_mode='HTML')
        
        bot.answer_callback_query(call.id, "✅ Готово")
    except Exception as e:
        logging.error(f"RP callback error: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка")

# ==================== ЗАПУСК ====================

if __name__ == '__main__':
    print("🚀 Бот запущен...")
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(5)
