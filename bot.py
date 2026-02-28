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
from datetime import datetime, timedelta
from telebot import types, util
import logging
import traceback
import asyncio
from difflib import get_close_matches
from threading import Thread

########## НАСТРОЙКА ЛОГОВ ##########
log_stream = io.StringIO()
logging.basicConfig(stream=log_stream, level=logging.ERROR)

########## ПРОВЕРКА ФАЙЛА КОНФИГУРАЦИИ ##########
if not os.path.exists('db.json'):
    db = {'token': 'None', 'admin_id_for_errors': None, 'owner_id': None, 'beta_testers': []}
    js = json.dumps(db, indent=2)
    with open('db.json', 'w') as outfile:
        outfile.write(js)
    print('ВНИМАНИЕ: Файл db.json создан. Введи токен в "None", свой ID администратора в "admin_id_for_errors", ID владельца в "owner_id" и IDs бета-тестеров в "beta_testers" (db.json)')
    exit()

########## ЗАГРУЗКА RP КОМАНД ##########
try:
    with open('rp_commands.json', 'r', encoding='utf-8') as f:
        rp_data = json.load(f)['commands']
    print(f"✅ Загружено {len(rp_data)} RP-команд")
except Exception as e:
    print(f"❌ Ошибка загрузки RP-команд: {e}")
    rp_data = {}

########## ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ##########
def init_sqlite_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # Пользователи
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            hashed_username TEXT PRIMARY KEY,
            user_id INTEGER
        )
    ''')
    
    # Низкие админы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS low_admins (
            chat_id TEXT,
            username TEXT,
            PRIMARY KEY (chat_id, username)
        )
    ''')
    
    # Предупреждения
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warns (
            user_id TEXT PRIMARY KEY,
            warn_count INTEGER,
            last_warn_time TEXT
        )
    ''')
    
    # Статистика сообщений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_data (
            chat_id TEXT,
            user_id TEXT,
            date TEXT,
            message_count INTEGER DEFAULT 0,
            last_activity TEXT,
            last_mentioned_target TEXT,
            PRIMARY KEY (chat_id, user_id, date)
        )
    ''')
    
    # Чаты
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            chat_id TEXT PRIMARY KEY,
            chat_title TEXT
        )
    ''')
    
    # Профили пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            nickname TEXT,
            description TEXT,
            subscription_type TEXT DEFAULT 'free',
            subscription_expires TIMESTAMP
        )
    ''')
    
    # RP запросы
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
    
    # Браки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS marriages (
            chat_id TEXT,
            spouse1_id INTEGER,
            spouse2_id INTEGER,
            created_at TEXT,
            PRIMARY KEY (chat_id, spouse1_id, spouse2_id)
        )
    ''')
    
    # Запросы на брак
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
    
    # Подписки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            type TEXT DEFAULT 'free',
            expires_at TIMESTAMP,
            stars_paid INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Статистика RP использования
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rp_usage (
            user_id INTEGER,
            date DATE,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, date)
        )
    ''')
    
    # Настройки чатов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_settings (
            chat_id INTEGER PRIMARY KEY,
            welcome_message TEXT,
            rules TEXT,
            anti_swear BOOLEAN DEFAULT 0,
            auto_moderation BOOLEAN DEFAULT 1,
            mute_time INTEGER DEFAULT 60
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

init_sqlite_db()

########## РАБОТА С БАЗОЙ ДАННЫХ ##########
def read_db():
    with open('db.json', 'r') as openfile:
        return json.load(openfile)

def write_db(db):
    js = json.dumps(db, indent=2)
    with open('db.json', 'w') as outfile:
        outfile.write(js)

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

def add_chat_to_db(chat_id, chat_title):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO chats (chat_id, chat_title) VALUES (?, ?)', (str(chat_id), chat_title))
    conn.commit()
    conn.close()
    print(f"✅ Чат сохранен: {chat_title} ({chat_id})")

def get_all_chats():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id FROM chats')
    chats = [row[0] for row in cursor.fetchall()]
    conn.close()
    return chats

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

def get_user_subscription(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT type, expires_at FROM subscriptions WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return {'type': 'free', 'expires': None}
    
    return {
        'type': result[0],
        'expires': datetime.fromisoformat(result[1]) if result[1] else None
    }

def set_user_subscription(user_id, sub_type, days, stars_paid):
    expires = datetime.now() + timedelta(days=days)
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO subscriptions (user_id, type, expires_at, stars_paid)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            type = ?,
            expires_at = ?,
            stars_paid = stars_paid + ?
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
        INSERT INTO rp_usage (user_id, date, count) VALUES (?, ?, 1)
        ON CONFLICT(user_id, date) DO UPDATE SET count = count + 1
    ''', (user_id, today))
    conn.commit()
    conn.close()

def save_rp_request(request_id, chat_id, sender_id, sender_first_name, target_id, command, phrase):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO rp_requests (request_id, chat_id, sender_id, sender_first_name, target_id, command, phrase, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (request_id, str(chat_id), sender_id, sender_first_name, target_id, command, phrase, created_at))
    conn.commit()
    conn.close()

def get_rp_request(request_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id, sender_id, sender_first_name, target_id, command, phrase FROM rp_requests WHERE request_id = ?', (request_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def save_marriage_request(request_id, chat_id, proposer_id, proposer_first_name, target_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO marriage_requests (request_id, chat_id, proposer_id, proposer_first_name, target_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (request_id, str(chat_id), proposer_id, proposer_first_name, target_id, created_at))
    conn.commit()
    conn.close()

def get_marriage_request(request_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id, proposer_id, proposer_first_name, target_id FROM marriage_requests WHERE request_id = ?', (request_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def delete_marriage_request(request_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM marriage_requests WHERE request_id = ?', (request_id,))
    conn.commit()
    conn.close()

def is_married(chat_id, user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM marriages WHERE chat_id = ? AND (spouse1_id = ? OR spouse2_id = ?)', 
                  (str(chat_id), user_id, user_id))
    result = cursor.fetchone()
    conn.close()
    return bool(result)

def get_spouse(chat_id, user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT spouse1_id, spouse2_id FROM marriages WHERE chat_id = ? AND (spouse1_id = ? OR spouse2_id = ?)',
                  (str(chat_id), user_id, user_id))
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

########## ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ##########
from xxhash import xxh32

def sha(text):
    text = str(text)
    return xxh32(text).hexdigest()

def get_uptime():
    try:
        result = subprocess.run(['uptime'], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except:
        return "Не удалось получить нагрузку"

def get_admins(message):
    try:
        if message.chat.type == 'private':
            return []
        admins = bot.get_chat_administrators(chat_id=message.chat.id)
        true_admins = []
        for i in admins:
            if i.status == 'creator' or i.can_restrict_members == True:
                true_admins.append(i.user.id)
        return true_admins
    except Exception as e:
        return []

def have_rights(message, set_la=False):
    db = read_db()
    owner_id = db['owner_id']
    if message.from_user.id == owner_id:
        return True
    if message.from_user.id in get_admins(message):
        return True
    return False

def analytic(message):
    if message.from_user.username:
        hashed = sha(message.from_user.username.lower())
        write_users(hashed, message.from_user.id)

def get_user_link_sync(user_id, chat_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        display_name = get_nickname(user_id) or member.user.first_name
        display_name = display_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        if member.user.username:
            username = member.user.username.lstrip('@')
            return f'<a href="https://t.me/{username}">{display_name}</a>'
        else:
            return f'<a href="tg://user?id={user_id}">{display_name}</a>'
    except:
        return f"Пользователь {user_id}"

def get_name(message):
    try:
        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
            display_name = get_nickname(target_user.id) or target_user.first_name
            display_name = display_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            return f'<a href="tg://user?id={target_user.id}">{display_name}</a>'
        return "пользователь"
    except:
        return "пользователь"

def get_target(message):
    if message.reply_to_message:
        return message.reply_to_message.from_user.id
    return None

def format_time_ago(datetime_str):
    if not datetime_str:
        return "Нет данных"
    try:
        last = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        delta = now - last
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

########## АВТОИСПРАВЛЕНИЕ КОМАНД ##########
ALL_COMMANDS = {
    # Модерация
    'бан': 'бан', 'разбан': 'разбан', 'кик': 'кик', 'мут': 'мут', 'размут': 'размут',
    'варн': 'варн', 'снять варн': 'снять варн', '-смс': '-смс', '+чат': '+чат', '-чат': '-чат',
    'пин': 'пин', 'закреп': 'закреп', 'анпин': 'анпин', '+админ': '+админ', '-админ': '-админ',
    
    # Статистика
    'кто я': 'кто я', 'кто ты': 'кто ты', 'топ дня': 'топ дня', 'топ недели': 'топ недели',
    'топ месяца': 'топ месяца', 'топ вся': 'топ вся',
    
    # Браки
    'брак': 'брак', 'развод': 'развод', 'браки': 'браки', 'список браков': 'список браков',
    
    # Игры
    '!вероятность': '!вероятность', '!вер': '!вер', 'рандом': 'рандом',
    'пинг': 'пинг', 'кинг': 'кинг', 'бот': 'бот', 'какая нагрузка': 'какая нагрузка',
    
    # RP команды
    'обнять': 'обнять', 'поцеловать': 'поцеловать', 'поздравить': 'поздравить',
    'пожать руку': 'пожать руку', 'дать пять': 'дать пять', 'погладить': 'погладить',
    'похвалить': 'похвалить', 'извиниться': 'извиниться', 'понюхать': 'понюхать',
    'лизнуть': 'лизнуть', 'потискать': 'потискать', 'пригласить на чай': 'пригласить на чай',
    'потрогать': 'потрогать', 'ущипнуть': 'ущипнуть', 'щекотать': 'щекотать',
    'пощупать': 'пощупать', 'подарить': 'подарить', 'выпить': 'выпить',
    'покормить': 'покормить', 'кусь': 'кусь', 'прижать': 'прижать'
}

# Добавляем все RP команды из файла
for cmd in rp_data.keys():
    ALL_COMMANDS[cmd] = cmd

def suggest_command(user_input):
    user_input_lower = user_input.lower().strip()
    
    if user_input_lower in ALL_COMMANDS:
        return user_input_lower
    
    matches = get_close_matches(user_input_lower, ALL_COMMANDS.keys(), n=1, cutoff=0.6)
    
    return matches[0] if matches else None

########## ЖИВЫЕ ОТВЕТЫ ##########
def get_live_response(command, sender_name, target_name):
    responses = {
        'обнять': [
            f"{sender_name} 🤗 крепко-крепко обнял {target_name}!",
            f"{sender_name} заключил {target_name} в тёплые объятия 🥰",
            f"{sender_name} обнимает {target_name} и не отпускает!",
            f"{sender_name} подарил {target_name} обнимашки на счастье 💫"
        ],
        'поцеловать': [
            f"{sender_name} 😘 нежно поцеловал {target_name} в щёчку",
            f"{sender_name} чмокнул {target_name} прямо в носик!",
            f"{sender_name} подарил {target_name} сладкий поцелуй 💋",
            f"{sender_name} засмущал {target_name} нежным поцелуем"
        ],
        'поздравить': [
            f"{sender_name} 🎉 от всей души поздравляет {target_name}!",
            f"{sender_name} кричит {target_name}: С ПРАЗДНИКОМ! 🎊",
            f"{sender_name} осыпает {target_name} поздравлениями и конфетти 🎨",
            f"{sender_name} желает {target_name} всего самого наилучшего ✨"
        ],
        'погладить': [
            f"{sender_name} 👐 нежно гладит {target_name} по голове",
            f"{sender_name} погладил {target_name} и тот замурлыкал 😸",
            f"{sender_name} гладит {target_name}, успокаивая",
            f"{sender_name} подарил {target_name} приятные поглаживания"
        ]
    }
    
    if command in responses:
        return random.choice(responses[command])
    return None

########## ЗАГРУЗКА КОНФИГА ##########
db_config = read_db()
BOT_TOKEN = db_config['token']
OWNER_ID = db_config['owner_id']
ADMIN_ID = db_config['admin_id_for_errors']

print(f"✅ Бот запускается с токеном: {BOT_TOKEN[:10]}...")
print(f"✅ Идентификатор владельца: {OWNER_ID}")
print(f"✅ Идентификатор администратора: {ADMIN_ID}")

bot = telebot.TeleBot(BOT_TOKEN)

########## ОБРАБОТЧИК ДОБАВЛЕНИЯ В ЧАТ ##########
@bot.message_handler(content_types=['new_chat_members'])
def welcome_to_chat(message):
    bot_id = bot.get_me().id
    
    for user in message.new_chat_members:
        if user.id == bot_id:
            chat_title = message.chat.title or "чат"
            admin_name = message.from_user.first_name or "Администратор"
            admin_username = message.from_user.username or "администратор"
            
            add_chat_to_db(message.chat.id, chat_title)
            
            welcome_text = (
                f"╔══════════════════════════════╗\n"
                f"║   🍬 <b>BARBARIS BOT</b> 🍬   ║\n"
                f"╠══════════════════════════════╣\n"
                f"║ Всем привет! Меня зовут      ║\n"
                f"║ <b>Барбариска</b>!            ║\n"
                f"╠══════════════════════════════╣\n"
                f"║ Спасибо, @{admin_username},  ║\n"
                f"║ что пригласили меня в        ║\n"
                f"║ <b>«{chat_title}»</b>           ║\n"
                f"╠══════════════════════════════╣\n"
                f"║ 🛡️ Буду следить за порядком  ║\n"
                f"║ 💕 Играть в RP-игры          ║\n"
                f"║ 📊 Считать статистику        ║\n"
                f"║ 💍 Сватать и женить          ║\n"
                f"╠══════════════════════════════╣\n"
                f"║ <b>Мои команды:</b>            ║\n"
                f"║ • .хелп - все команды        ║\n"
                f"║ • кто я - мой профиль        ║\n"
                f"║ • обнять @ник - обнимашки    ║\n"
                f"╚══════════════════════════════╝\n\n"
                f"👇 <b>Напиши .хелп, чтобы узнать больше!</b>"
            )
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📋 Все команды", callback_data="show_help"),
                types.InlineKeyboardButton("🛡️ Модерация", callback_data="help_moderation"),
                types.InlineKeyboardButton("💕 RP команды", callback_data="help_rp"),
                types.InlineKeyboardButton("📊 Статистика", callback_data="help_stats")
            )
            
            bot.send_message(
                message.chat.id,
                welcome_text,
                parse_mode='HTML',
                reply_markup=markup
            )
            
            try:
                admin_text = (
                    f"✅ <b>Бот добавлен в чат!</b>\n\n"
                    f"📌 Чат: {chat_title}\n"
                    f"🆔 ID: {message.chat.id}\n\n"
                    f"Теперь ты можешь управлять мной в этом чате!\n"
                    f"Используй команду /admin для настроек."
                )
                bot.send_message(message.from_user.id, admin_text, parse_mode='HTML')
            except:
                pass
            
            break

########## СТАРТ ##########
@bot.message_handler(commands=['start'])
def start_message(message):
    analytic(message)
    
    bot_username = "Barbariska_robot"
    add_to_chat_url = f"https://t.me/{bot_username}?startgroup=true"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Добавить в чат", url=add_to_chat_url),
        types.InlineKeyboardButton("📋 Команды", callback_data="show_help"),
        types.InlineKeyboardButton("💎 Премиум", callback_data="show_premium"),
        types.InlineKeyboardButton("🛡️ Модерация", callback_data="help_moderation"),
        types.InlineKeyboardButton("💕 RP команды", callback_data="help_rp"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="help_stats"),
        types.InlineKeyboardButton("💍 Браки", callback_data="help_marriage"),
        types.InlineKeyboardButton("🎲 Игры", callback_data="help_games")
    )
    
    welcome_text = (
        "╔══════════════════════════════╗\n"
        "║   🍬 <b>BARBARIS BOT</b> 🍬   ║\n"
        "╠══════════════════════════════╣\n"
        "║ Твой верный помощник в чате! ║\n"
        "║                              ║\n"
        "║ ✅ Модерация                  ║\n"
        "║ ✅ RP команды ({}) шт         ║\n"
        "║ ✅ Статистика и браки         ║\n"
        "║ ✅ Игры и развлечения         ║\n"
        "╚══════════════════════════════╝\n\n"
        "👇 <b>Выбери действие:</b>"
    ).format(len(rp_data))
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='HTML',
        reply_markup=markup
    )

########## ПОМОЩЬ ##########
@bot.message_handler(commands=['help'])
@bot.message_handler(func=lambda message: message.text and message.text.lower() == '.хелп')
def help_command(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛡️ Модерация", callback_data="help_moderation"),
        types.InlineKeyboardButton("💕 RP команды", callback_data="help_rp"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="help_stats"),
        types.InlineKeyboardButton("💍 Браки", callback_data="help_marriage"),
        types.InlineKeyboardButton("🎲 Игры", callback_data="help_games"),
        types.InlineKeyboardButton("💎 Премиум", callback_data="show_premium"),
        types.InlineKeyboardButton("➕ Добавить в чат", url=f"https://t.me/Barbariska_robot?startgroup=true"),
        types.InlineKeyboardButton("🔙 Закрыть", callback_data="close")
    )
    
    help_text = (
        "╔══════════════════════════════╗\n"
        "║   🍬 <b>BARBARIS BOT</b> 🍬   ║\n"
        "╠══════════════════════════════╣\n"
        "║ 📋 <b>СПИСОК КОМАНД</b>       ║\n"
        "╠══════════════════════════════╣\n"
        "║ 🛡️ <b>Модерация:</b>           ║\n"
        "║   Бан, Кик, Мут, Варн        ║\n"
        "║                              ║\n"
        "║ 💕 <b>RP команды:</b> {} шт!    ║\n"
        "║   обнять, поцеловать и др.   ║\n"
        "║                              ║\n"
        "║ 📊 <b>Статистика:</b>           ║\n"
        "║   кто я, топ дня/недели      ║\n"
        "║                              ║\n"
        "║ 💍 <b>Браки:</b>                ║\n"
        "║   брак, развод, список браков║\n"
        "║                              ║\n"
        "║ 🎲 <b>Игры:</b>                 ║\n"
        "║   !вероятность, рандом        ║\n"
        "╚══════════════════════════════╝\n\n"
        "👇 <b>Выбери категорию:</b>"
    ).format(len(rp_data))
    
    bot.send_message(
        message.chat.id,
        help_text,
        parse_mode='HTML',
        reply_markup=markup
    )

########## ПАНЕЛЬ АДМИНИСТРАТОРА ##########
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if not have_rights(message):
        bot.reply_to(message, "❌ Эта команда только для админов!")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("⚙️ Настройки чата", callback_data="admin_settings"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        types.InlineKeyboardButton("🚫 Антимат", callback_data="admin_antiswear"),
        types.InlineKeyboardButton("👋 Приветствие", callback_data="admin_welcome"),
        types.InlineKeyboardButton("📜 Правила", callback_data="admin_rules"),
        types.InlineKeyboardButton("🔙 Закрыть", callback_data="close")
    )
    
    bot.send_message(
        message.chat.id,
        "🛡️ <b>Панель администратора</b>\n\nВыбери, что хочешь настроить:",
        parse_mode='HTML',
        reply_markup=markup
    )

########## ПРЕМИУМ ##########
@bot.message_handler(commands=['premium'])
def premium_command(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💎 Премиум на месяц - 50 ⭐", callback_data="buy_month"),
        types.InlineKeyboardButton("👑 VIP навсегда - 1000 ⭐", callback_data="buy_vip")
    )
    
    sub = get_user_subscription(message.from_user.id)
    
    if sub['type'] != 'free':
        expires = sub['expires'].strftime('%d.%m.%Y') if sub['expires'] else 'никогда'
        status = f"✅ Твой статус: <b>{sub['type'].upper()}</b> до {expires}"
    else:
        status = "🎁 Твой статус: <b>Бесплатный</b>"
    
    text = (
        f"╔══════════════════════════════╗\n"
        f"║   💎 <b>ПРЕМИУМ ДОСТУП</b>    ║\n"
        f"╠══════════════════════════════╣\n"
        f"║ {status}          ║\n"
        f"╠══════════════════════════════╣\n"
        f"║ 🎁 <b>Бесплатно:</b>            ║\n"
        f"║ • 15 RP команд в день        ║\n"
        f"║ • Только базовые команды     ║\n"
        f"╠══════════════════════════════╣\n"
        f"║ 💎 <b>Премиум (50 ⭐/мес):</b>   ║\n"
        f"║ • Безлимитные RP команды     ║\n"
        f"║ • Все {len(rp_data)} команд              ║\n"
        f"║ • 18+ контент                ║\n"
        f"╠══════════════════════════════╣\n"
        f"║ 👑 <b>VIP (1000 ⭐ навсегда):</b>║\n"
        f"║ • Пожизненный доступ         ║\n"
        f"║ • Особый статус в профиле    ║\n"
        f"╚══════════════════════════════╝"
    ).format(len(rp_data))
    
    bot.send_message(
        message.chat.id,
        text,
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.message_handler(commands=['my_sub'])
def my_subscription(message):
    sub = get_user_subscription(message.from_user.id)
    
    if sub['type'] == 'free':
        used = check_rp_limit(message.from_user.id)
        left = 15 - used
        text = (
            f"🎁 <b>Твой тариф: Бесплатный</b>\n\n"
            f"📊 Использовано RP сегодня: {used}/15\n"
            f"⏳ Осталось: {left}\n\n"
            f"Купи премиум: /premium"
        )
    else:
        expires = sub['expires'].strftime('%d.%m.%Y') if sub['expires'] else 'никогда'
        text = (
            f"💎 <b>Твой тариф: {sub['type'].upper()}</b>\n\n"
            f"⏳ Действует до: {expires}\n"
            f"✨ Доступны все RP-команды без лимитов"
        )
    
    bot.reply_to(message, text, parse_mode='HTML')

########## ОБРАБОТЧИКИ КОМАНД ##########
@bot.message_handler(commands=['list'])
def handle_list(message):
    db = read_db()
    if message.from_user.id != db['owner_id']:
        bot.reply_to(message, "❌ Эта команда только для владельца бота.")
        return
    
    chats = get_all_chats()
    if not chats:
        bot.send_message(message.chat.id, "Бот не добавлен ни в один чат.")
        return
    
    text = f"📋 <b>Список чатов ({len(chats)}):</b>\n\n"
    for chat_id in chats:
        try:
            chat = bot.get_chat(int(chat_id))
            title = chat.title or "Private Chat"
            text += f"• {title} (ID: {chat_id})\n"
        except:
            text += f"• Chat ID: {chat_id} (недоступен)\n"
    
    bot.send_message(message.chat.id, text, parse_mode='HTML')

########## ТОПЫ ##########
@bot.message_handler(func=lambda message: message.text and message.text.upper() in ['ТОП ДЕНЬ', 'ТОП ДНЯ'])
def handle_top_day(message):
    chat_id = str(message.chat.id)
    daily_stats = get_daily_stats(chat_id)
    sorted_stats = sorted(daily_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    
    if not sorted_stats:
        bot.send_message(message.chat.id, "📊 Статистика за сегодня пока пуста.")
        return
    
    text = "📅 <b>Топ за сегодня:</b>\n\n"
    for i, (user_id, count) in enumerate(sorted_stats, 1):
        user_link = get_user_link_sync(int(user_id), message.chat.id)
        text += f"{i}. {user_link} — {count} сообщ.\n"
    
    bot.send_message(message.chat.id, text, parse_mode='HTML', disable_web_page_preview=True)

@bot.message_handler(func=lambda message: message.text and message.text.upper() in ['ТОП НЕДЕЛЯ', 'ТОП НЕДЕЛИ'])
def handle_top_week(message):
    chat_id = str(message.chat.id)
    weekly_stats = get_weekly_stats(chat_id)
    sorted_stats = sorted(weekly_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    
    if not sorted_stats:
        bot.send_message(message.chat.id, "📊 Статистика за неделю пока пуста.")
        return
    
    text = "📆 <b>Топ за неделю:</b>\n\n"
    for i, (user_id, count) in enumerate(sorted_stats, 1):
        user_link = get_user_link_sync(int(user_id), message.chat.id)
        text += f"{i}. {user_link} — {count} сообщ.\n"
    
    bot.send_message(message.chat.id, text, parse_mode='HTML', disable_web_page_preview=True)

@bot.message_handler(func=lambda message: message.text and message.text.upper() in ['ТОП МЕСЯЦ', 'ТОП МЕСЯЦА'])
def handle_top_month(message):
    chat_id = str(message.chat.id)
    monthly_stats = get_monthly_stats(chat_id)
    sorted_stats = sorted(monthly_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    
    if not sorted_stats:
        bot.send_message(message.chat.id, "📊 Статистика за месяц пока пуста.")
        return
    
    text = "📅 <b>Топ за месяц:</b>\n\n"
    for i, (user_id, count) in enumerate(sorted_stats, 1):
        user_link = get_user_link_sync(int(user_id), message.chat.id)
        text += f"{i}. {user_link} — {count} сообщ.\n"
    
    bot.send_message(message.chat.id, text, parse_mode='HTML', disable_web_page_preview=True)

@bot.message_handler(func=lambda message: message.text and message.text.upper() in ['ТОП', 'ТОП ВСЯ'])
def handle_top_all_time(message):
    chat_id = str(message.chat.id)
    all_time_stats = get_all_time_stats(chat_id)
    sorted_stats = sorted(all_time_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    
    if not sorted_stats:
        bot.send_message(message.chat.id, "📊 Статистика за всё время пока пуста.")
        return
    
    text = "🏆 <b>Топ за всё время:</b>\n\n"
    for i, (user_id, count) in enumerate(sorted_stats, 1):
        user_link = get_user_link_sync(int(user_id), message.chat.id)
        text += f"{i}. {user_link} — {count} сообщ.\n"
    
    bot.send_message(message.chat.id, text, parse_mode='HTML', disable_web_page_preview=True)

########## КТО Я ##########
@bot.message_handler(func=lambda message: message.text and message.text.upper() == 'КТО Я')
def who_am_i(message):
    user_id = message.from_user.id
    chat_id = str(message.chat.id)
    
    sub = get_user_subscription(user_id)
    sub_text = "💎 Премиум" if sub['type'] != 'free' else "🎁 Бесплатный"
    
    display_name = get_nickname(user_id) or message.from_user.first_name
    display_name = display_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    daily = get_user_daily_stats(chat_id, user_id)
    weekly = get_user_weekly_stats(chat_id, user_id)
    all_time = get_user_all_time_stats(chat_id, user_id)
    
    description = get_description(user_id)
    desc_text = f"\n📝 {description}" if description else ""
    
    spouse_id = get_spouse(chat_id, user_id)
    spouse_text = ""
    if spouse_id:
        spouse_link = get_user_link_sync(spouse_id, message.chat.id)
        spouse_text = f"\n💍 В браке с: {spouse_link}"
    
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT last_activity FROM user_data WHERE chat_id = ? AND user_id = ? LIMIT 1',
                  (chat_id, user_id))
    result = cursor.fetchone()
    last_active = format_time_ago(result[0]) if result and result[0] else "Нет данных"
    conn.close()
    
    text = (
        f"👤 <b>{display_name}</b>\n"
        f"{sub_text}{desc_text}{spouse_text}\n\n"
        f"⏱️ Последний актив: {last_active}\n"
        f"📊 Статистика (д|н|всё): {daily} | {weekly} | {all_time}"
    )
    
    bot.reply_to(message, text, parse_mode='HTML')

########## ВЕРОЯТНОСТЬ ##########
@bot.message_handler(func=lambda message: message.text and message.text.lower().startswith('!вероятность'))
def probability_command(message):
    try:
        text = message.text[12:].strip()
        
        if not text:
            bot.reply_to(message, "❓ Пример: !вероятность Андрей лох?")
            return
        
        prob = random.randint(0, 100)
        
        if prob < 10:
            emoji = "😱"
            comment = "Ни за что!"
        elif prob < 30:
            emoji = "🤔"
            comment = "Вряд ли"
        elif prob < 50:
            emoji = "😐"
            comment = "50 на 50"
        elif prob < 70:
            emoji = "😏"
            comment = "Вероятно"
        elif prob < 90:
            emoji = "😎"
            comment = "Очень вероятно"
        else:
            emoji = "🔥"
            comment = "Абсолютно точно!"
        
        response = (
            f"🎲 <b>Вопрос:</b> {text}\n\n"
            f"📊 <b>Вероятность:</b> {prob}%\n"
            f"{emoji} <i>{comment}</i>"
        )
        
        bot.reply_to(message, response, parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, "❌ Что-то пошло не так. Попробуй ещё раз.")

@bot.message_handler(func=lambda message: message.text and message.text.lower().startswith('!вер'))
def probability_short_command(message):
    text = message.text[4:].strip()
    fake_message = message
    fake_message.text = f"!вероятность {text}"
    probability_command(fake_message)

########## РАНДОМ ##########
@bot.message_handler(func=lambda message: message.text and message.text.lower().startswith('рандом'))
def random_command(message):
    try:
        parts = message.text.split()
        if len(parts) >= 3:
            a = int(parts[1])
            b = int(parts[2])
            if a > b:
                a, b = b, a
            result = random.randint(a, b)
            bot.reply_to(message, f"🎲 Случайное число от {a} до {b}: <b>{result}</b>", parse_mode='HTML')
        else:
            bot.reply_to(message, "❓ Пример: рандом 1 100")
    except:
        bot.reply_to(message, "❌ Неправильный формат. Пример: рандом 1 100")

########## ПИНГ ##########
@bot.message_handler(func=lambda message: message.text and message.text.upper() == 'ПИНГ')
def ping_command(message):
    bot.reply_to(message, "🏓 ПОНГ")

@bot.message_handler(func=lambda message: message.text and message.text.upper() == 'КИНГ')
def king_command(message):
    bot.reply_to(message, "👑 КОНГ")

@bot.message_handler(func=lambda message: message.text and message.text.upper() == 'БОТ')
def bot_command(message):
    bot.reply_to(message, "✅ На месте!")

@bot.message_handler(func=lambda message: message.text and message.text.upper() == 'КАКАЯ НАГРУЗКА')
def load_command(message):
    uptime = get_uptime()
    bot.reply_to(message, f"📊 <b>Нагрузка:</b>\n{uptime}", parse_mode='HTML')

########## БРАКИ ##########
@bot.message_handler(func=lambda message: message.text and message.text.upper() == 'БРАК')
def marriage_propose(message):
    if not message.reply_to_message:
        bot.reply_to(message, "❓ Команда должна быть ответом на сообщение пользователя.")
        return
    
    proposer_id = message.from_user.id
    target_id = message.reply_to_message.from_user.id
    chat_id = message.chat.id
    
    if proposer_id == target_id:
        bot.reply_to(message, "❌ Нельзя вступить в брак с самим собой.")
        return
    
    if is_married(chat_id, proposer_id):
        bot.reply_to(message, "❌ Вы уже состоите в браке в этом чате.")
        return
    
    if is_married(chat_id, target_id):
        bot.reply_to(message, "❌ Этот пользователь уже состоит в браке.")
        return
    
    request_id = str(uuid.uuid4())
    save_marriage_request(request_id, chat_id, proposer_id, message.from_user.first_name, target_id)
    
    proposer_link = get_user_link_sync(proposer_id, chat_id)
    target_link = get_user_link_sync(target_id, chat_id)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Согласиться", callback_data=f"marriage_agree_{request_id}"),
        types.InlineKeyboardButton("❌ Отказаться", callback_data=f"marriage_reject_{request_id}")
    )
    
    bot.send_message(
        chat_id,
        f"💍 {proposer_link} хочет вступить в брак с {target_link}!",
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text and message.text.upper() == 'РАЗВОД')
def marriage_divorce(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    spouse_id = dissolve_marriage(chat_id, user_id)
    if spouse_id:
        spouse_link = get_user_link_sync(spouse_id, chat_id)
        bot.reply_to(message, f"💔 Развод оформлен. Сожалеем, {spouse_link}.", parse_mode='HTML')
    else:
        bot.reply_to(message, "❌ Вы не состоите в браке в этом чате.")

@bot.message_handler(func=lambda message: message.text and message.text.upper() in ['БРАКИ', 'СПИСОК БРАКОВ'])
def marriage_list(message):
    marriages = get_all_marriages(message.chat.id)
    
    if not marriages:
        bot.reply_to(message, "💔 В этом чате нет зарегистрированных браков.")
        return
    
    text = "💍 <b>Список браков в чате:</b>\n\n"
    for i, (sp1, sp2, created_str) in enumerate(marriages, 1):
        link1 = get_user_link_sync(sp1, message.chat.id)
        link2 = get_user_link_sync(sp2, message.chat.id)
        created_dt = datetime.strptime(created_str, '%Y-%m-%d %H:%M:%S')
        days = (datetime.now() - created_dt).days
        text += f"{i}. {link1} 💕 {link2} ({days} дн.)\n"
    
    bot.send_message(message.chat.id, text, parse_mode='HTML')

########## НИКИ И ОПИСАНИЯ ##########
@bot.message_handler(func=lambda message: message.text and message.text.upper().startswith('+НИК '))
def set_nick(message):
    nick = message.text[5:].strip()
    if nick:
        set_nickname(message.from_user.id, nick)
        bot.reply_to(message, f"✅ Ник установлен: {nick}")
    else:
        bot.reply_to(message, "❓ Укажите ник после +ник")

@bot.message_handler(func=lambda message: message.text and message.text.upper() == '-НИК')
def remove_nick(message):
    set_nickname(message.from_user.id, None)
    bot.reply_to(message, "✅ Ник сброшен")

@bot.message_handler(func=lambda message: message.text and message.text.upper().startswith('+ОПИСАНИЕ '))
def set_desc(message):
    desc = message.text[10:].strip()
    if desc:
        set_description(message.from_user.id, desc)
        bot.reply_to(message, f"✅ Описание установлено: {desc}")
    else:
        bot.reply_to(message, "❓ Укажите описание после +описание")

@bot.message_handler(func=lambda message: message.text and message.text.upper() == '-ОПИСАНИЕ')
def remove_desc(message):
    set_description(message.from_user.id, None)
    bot.reply_to(message, "✅ Описание сброшено")

########## БАРБАРИС СКАЖИ ##########
@bot.message_handler(func=lambda message: message.text and message.text.upper().startswith('БАРБАРИС СКАЖИ '))
def barbaris_say(message):
    text = message.text[14:].strip()
    user_link = get_user_link_sync(message.from_user.id, message.chat.id)
    bot.send_message(message.chat.id, f"{user_link} заставил меня сказать: {text}", parse_mode='HTML')

@bot.message_handler(func=lambda message: message.text and message.text.upper().startswith('БАРБАРИС, СКАЖИ '))
def barbaris_say_comma(message):
    text = message.text[15:].strip()
    user_link = get_user_link_sync(message.from_user.id, message.chat.id)
    bot.send_message(message.chat.id, f"{user_link} заставил меня сказать: {text}", parse_mode='HTML')

########## МОДЕРАЦИЯ ##########
@bot.message_handler(func=lambda message: message.text and message.text.upper() == 'БАН')
def ban_command(message):
    if not have_rights(message):
        bot.reply_to(message, "❌ Недостаточно прав!")
        return
    
    target = get_target(message)
    if not target:
        bot.reply_to(message, "❌ Нужно ответить на сообщение пользователя.")
        return
    
    try:
        bot.ban_chat_member(message.chat.id, target)
        bot.reply_to(message, f"🔨 Пользователь забанен.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda message: message.text and message.text.upper() == 'КИК')
def kick_command(message):
    if not have_rights(message):
        bot.reply_to(message, "❌ Недостаточно прав!")
        return
    
    target = get_target(message)
    if not target:
        bot.reply_to(message, "❌ Нужно ответить на сообщение пользователя.")
        return
    
    try:
        bot.ban_chat_member(message.chat.id, target)
        bot.unban_chat_member(message.chat.id, target)
        bot.reply_to(message, f"👢 Пользователь кикнут.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda message: message.text and message.text.upper() == 'МУТ')
def mute_command(message):
    if not have_rights(message):
        bot.reply_to(message, "❌ Недостаточно прав!")
        return
    
    target = get_target(message)
    if not target:
        bot.reply_to(message, "❌ Нужно ответить на сообщение пользователя.")
        return
    
    try:
        bot.restrict_chat_member(message.chat.id, target, until_date=message.date + 3600)
        bot.reply_to(message, f"🔇 Пользователь замьючен на 1 час.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

########## УНИВЕРСАЛЬНЫЙ ХЕНДЛЕР (АВТОИСПРАВЛЕНИЕ) ##########
@bot.message_handler(func=lambda message: True)
def universal_handler(message):
    analytic(message)
    
    if not message.text:
        return
    
    # Пропускаем уже обработанные команды
    if message.text.startswith('/') or message.text.startswith('!'):
        return
    
    original = message.text
    suggested = suggest_command(original)
    
    if not suggested:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📋 Список команд", callback_data="show_help")
        )
        
        bot.reply_to(
            message,
            f"❓ <b>Неизвестная команда</b>\n\n"
            f"Я не знаю <code>{original[:30]}</code>\n"
            f"Нажми кнопку, чтобы посмотреть все команды",
            parse_mode='HTML',
            reply_markup=markup
        )
        return
    
    if suggested != original.lower().strip():
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(f"✅ Выполнить: {suggested}", callback_data=f"do_{suggested}")
        )
        
        bot.reply_to(
            message,
            f"🤔 <b>Возможно, ты имел в виду:</b>\n\n"
            f"<code>{suggested}</code>",
            parse_mode='HTML',
            reply_markup=markup
        )
        return

########## ОБРАБОТЧИКИ CALLBACK ##########
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "show_help":
        bot.answer_callback_query(call.id)
        help_command(call.message)
    
    elif call.data == "show_premium":
        bot.answer_callback_query(call.id)
        premium_command(call.message)
    
    elif call.data == "help_moderation":
        text = (
            "🛡️ <b>Команды модерации:</b>\n\n"
            "🔨 <b>Бан</b> - заблокировать навсегда\n"
            "👢 <b>Кик</b> - выгнать из чата\n"
            "🔇 <b>Мут</b> - запретить писать\n"
            "🔊 <b>Размут</b> - снять mute\n"
            "⚠️ <b>Варн</b> - предупреждение\n"
            "✅ <b>Снять варн</b> - убрать предупреждение\n"
            "❌ <b>-смс</b> - удалить сообщение\n"
            "📌 <b>Пин</b> - закрепить сообщение\n"
            "🔓 <b>+чат</b> - открыть чат\n"
            "🔒 <b>-чат</b> - закрыть чат\n\n"
            "<i>Используй команды в ответ на сообщение пользователя</i>"
        )
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )
    
    elif call.data == "help_rp":
        text = f"💕 <b>RP команды (всего {len(rp_data)}):</b>\n\n"
        commands = sorted(list(rp_data.keys()))[:20]
        for cmd in commands:
            text += f"• <code>{cmd}</code>\n"
        text += f"\nи ещё {len(rp_data)-20} команд...\n\n"
        text += "<i>Используй команду с @ник или в ответ на сообщение</i>"
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )
    
    elif call.data == "help_stats":
        text = (
            "📊 <b>Команды статистики:</b>\n\n"
            "👤 <b>кто я</b> - мой профиль\n"
            "👥 <b>кто ты @ник</b> - профиль другого\n"
            "📅 <b>топ дня</b> - топ за сегодня\n"
            "📆 <b>топ недели</b> - топ за неделю\n"
            "📅 <b>топ месяца</b> - топ за месяц\n"
            "🏆 <b>топ вся</b> - топ за всё время\n\n"
            "➕ <b>+ник</b> - установить ник\n"
            "➖ <b>-ник</b> - сбросить ник\n"
            "➕ <b>+описание</b> - установить описание\n"
            "➖ <b>-описание</b> - сбросить описание"
        )
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )
    
    elif call.data == "help_marriage":
        text = (
            "💍 <b>Команды браков:</b>\n\n"
            "💍 <b>брак</b> - предложить брак (в ответ)\n"
            "💔 <b>развод</b> - развестись\n"
            "📋 <b>браки</b> - список браков в чате\n"
            "📋 <b>список браков</b> - то же самое"
        )
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )
    
    elif call.data == "help_games":
        text = (
            "🎲 <b>Игры и развлечения:</b>\n\n"
            "🎲 <b>!вероятность [текст]</b> - узнать вероятность\n"
            "🎲 <b>!вер [текст]</b> - короткая версия\n"
            "🔢 <b>рандом A B</b> - случайное число\n"
            "🏓 <b>пинг</b> - проверить связь\n"
            "👑 <b>кинг</b> - игра в слова\n"
            "🤖 <b>бот</b> - онлайн ли?\n"
            "📊 <b>какая нагрузка</b> - статус сервера\n"
            "🗣️ <b>Барбарис, скажи [текст]</b> - повторялка"
        )
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )
    
    elif call.data == "buy_month":
        bot.answer_callback_query(call.id, "Покупка премиум на месяц...")
        prices = [types.LabeledPrice(label="Премиум на месяц", amount=50)]
        bot.send_invoice(
            call.message.chat.id,
            title="💎 Премиум на месяц",
            description="30 дней безлимитных RP-команд",
            invoice_payload="premium_month_30_50",
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="premium"
        )
    
    elif call.data == "buy_vip":
        bot.answer_callback_query(call.id, "Покупка VIP навсегда...")
        prices = [types.LabeledPrice(label="VIP навсегда", amount=1000)]
        bot.send_invoice(
            call.message.chat.id,
            title="👑 VIP навсегда",
            description="Пожизненный доступ ко всем командам",
            invoice_payload="premium_vip_36500_1000",
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="vip"
        )
    
    elif call.data.startswith("do_"):
        cmd = call.data[3:]
        bot.answer_callback_query(call.id, f"Выполняю: {cmd}")
        # Здесь можно вызвать соответствующую команду
    
    elif call.data.startswith("marriage_"):
        parts = call.data.split('_')
        if len(parts) >= 3:
            action = parts[1]
            request_id = parts[2]
            request = get_marriage_request(request_id)
            
            if not request:
                bot.answer_callback_query(call.id, "❌ Запрос устарел")
                return
            
            chat_id, proposer_id, proposer_name, target_id = request
            
            if call.from_user.id != target_id:
                bot.answer_callback_query(call.id, "❌ Это не твой запрос")
                return
            
            if action == "agree":
                register_marriage(chat_id, proposer_id, target_id)
                text = f"💍 Брак заключен!"
                bot.answer_callback_query(call.id, "✅ Поздравляем!")
            else:
                text = f"💔 Предложение отклонено"
                bot.answer_callback_query(call.id, "❌ Отказ")
            
            delete_marriage_request(request_id)
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
    
    elif call.data == "close":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)

########## ОБРАБОТЧИК ПЛАТЕЖЕЙ ##########
@bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout_query(pre_checkout_q):
    bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def successful_payment(message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split('_')
    
    if len(parts) >= 4:
        days = int(parts[2])
        stars = int(parts[3])
        sub_type = 'premium' if days < 365 else 'vip'
        
        set_user_subscription(message.from_user.id, sub_type, days, stars)
        
        bot.send_message(
            message.chat.id,
            f"✅ <b>Спасибо за покупку!</b>\n\n"
            f"Премиум активирован на {days} дней!\n"
            f"Тебе доступны все RP-команды без лимитов.",
            parse_mode='HTML'
        )

########## ЗАПУСК ##########
if __name__ == "__main__":
    print("🚀 Бот запускается...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        time.sleep(5)
