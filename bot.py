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
from telebot import types
import logging
from difflib import get_close_matches
from xxhash import xxh32

########## НАСТРОЙКА ЛОГОВ ##########
logging.basicConfig(level=logging.INFO)
log_stream = io.StringIO()

########## ПРОВЕРКА КОНФИГА ##########
if not os.path.exists('db.json'):
    db = {'token': 'None', 'admin_id_for_errors': None, 'owner_id': None, 'beta_testers': []}
    with open('db.json', 'w') as f:
        json.dump(db, f, indent=2)
    print('❌ Создан db.json. Вставь токен!')
    exit()

with open('db.json', 'r') as f:
    db_config = json.load(f)
    BOT_TOKEN = db_config['token']
    OWNER_ID = db_config['owner_id']

########## ЗАГРУЗКА RP КОМАНД ##########
try:
    with open('rp_commands.json', 'r', encoding='utf-8') as f:
        rp_data = json.load(f)['commands']
    print(f"✅ Загружено RP команд: {len(rp_data)}")
except Exception as e:
    print(f"❌ Ошибка загрузки RP: {e}")
    rp_data = {}

########## БАЗА ДАННЫХ ##########
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (hashed TEXT PRIMARY KEY, user_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS warns (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0, time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stats (chat_id TEXT, user_id TEXT, date TEXT, msgs INTEGER DEFAULT 0, last TEXT, PRIMARY KEY (chat_id, user_id, date))''')
    c.execute('''CREATE TABLE IF NOT EXISTS chats (chat_id TEXT PRIMARY KEY, title TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS profiles (user_id INTEGER PRIMARY KEY, nick TEXT, bio TEXT, sub TEXT DEFAULT 'free', sub_end TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS rp_usage (user_id INTEGER, date DATE, count INTEGER DEFAULT 0, PRIMARY KEY (user_id, date))''')
    c.execute('''CREATE TABLE IF NOT EXISTS marriages (chat_id TEXT, u1 INTEGER, u2 INTEGER, time TEXT, PRIMARY KEY (chat_id, u1, u2))''')
    c.execute('''CREATE TABLE IF NOT EXISTS marry_req (id TEXT PRIMARY KEY, chat_id TEXT, from_id INTEGER, from_name TEXT, to_id INTEGER, time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_settings (chat_id INTEGER PRIMARY KEY, welcome TEXT, rules TEXT, antiswear INTEGER DEFAULT 0, antiflood INTEGER DEFAULT 0, captcha INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS captcha (user_id INTEGER, chat_id INTEGER, code TEXT, attempts INTEGER DEFAULT 0, PRIMARY KEY (user_id, chat_id))''')
    conn.commit()
    conn.close()
    print("✅ База данных готова")

init_db()

########## ФУНКЦИИ БД ##########
def sha(text): return xxh32(str(text).lower()).hexdigest()

def save_user(username, user_id):
    if username:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO users VALUES (?, ?)', (sha(username), user_id))
        conn.commit()
        conn.close()

def get_user_id(username):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM users WHERE hashed = ?', (sha(username),))
    r = c.fetchone()
    conn.close()
    return r[0] if r else None

def get_nick(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT nick FROM profiles WHERE user_id = ?', (user_id,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else None

def set_nick(user_id, nick):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO profiles (user_id) VALUES (?)', (user_id,))
    c.execute('UPDATE profiles SET nick = ? WHERE user_id = ?', (nick, user_id))
    conn.commit()
    conn.close()

def get_bio(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT bio FROM profiles WHERE user_id = ?', (user_id,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else None

def set_bio(user_id, bio):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO profiles (user_id) VALUES (?)', (user_id,))
    c.execute('UPDATE profiles SET bio = ? WHERE user_id = ?', (bio, user_id))
    conn.commit()
    conn.close()

def check_sub(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT sub, sub_end FROM profiles WHERE user_id = ?', (user_id,))
    r = c.fetchone()
    conn.close()
    if not r or r[0] == 'free':
        return False
    if r[1] and datetime.fromisoformat(r[1]) > datetime.now():
        return True
    return False

def set_sub(user_id, days):
    end = (datetime.now() + timedelta(days=days)).isoformat()
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO profiles (user_id) VALUES (?)', (user_id,))
    c.execute('UPDATE profiles SET sub = ?, sub_end = ? WHERE user_id = ?', ('premium', end, user_id))
    conn.commit()
    conn.close()

def check_rp_limit(user_id):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT count FROM rp_usage WHERE user_id = ? AND date = ?', (user_id, today))
    r = c.fetchone()
    conn.close()
    return r[0] if r else 0

def add_rp_usage(user_id):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT INTO rp_usage (user_id, date, count) VALUES (?, ?, 1) ON CONFLICT(user_id, date) DO UPDATE SET count = count + 1', (user_id, today))
    conn.commit()
    conn.close()

def add_marry_req(req_id, chat_id, from_id, from_name, to_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT INTO marry_req VALUES (?, ?, ?, ?, ?, ?)', (req_id, str(chat_id), from_id, from_name, to_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_marry_req(req_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT chat_id, from_id, from_name, to_id FROM marry_req WHERE id = ?', (req_id,))
    r = c.fetchone()
    conn.close()
    return r

def del_marry_req(req_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('DELETE FROM marry_req WHERE id = ?', (req_id,))
    conn.commit()
    conn.close()

def is_married(chat_id, user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT 1 FROM marriages WHERE chat_id = ? AND (u1 = ? OR u2 = ?)', (str(chat_id), user_id, user_id))
    r = c.fetchone()
    conn.close()
    return bool(r)

def add_marriage(chat_id, u1, u2):
    a, b = sorted([u1, u2])
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO marriages VALUES (?, ?, ?, ?)', (str(chat_id), a, b, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def del_marriage(chat_id, user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT u1, u2 FROM marriages WHERE chat_id = ? AND (u1 = ? OR u2 = ?)', (str(chat_id), user_id, user_id))
    r = c.fetchone()
    if r:
        a, b = sorted([r[0], r[1]])
        c.execute('DELETE FROM marriages WHERE chat_id = ? AND u1 = ? AND u2 = ?', (str(chat_id), a, b))
        conn.commit()
        conn.close()
        return r[1] if r[0] == user_id else r[0]
    conn.close()
    return None

def get_settings(chat_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT welcome, rules, antiswear, antiflood, captcha FROM chat_settings WHERE chat_id = ?', (chat_id,))
    r = c.fetchone()
    conn.close()
    if r:
        return {'welcome': r[0], 'rules': r[1], 'antiswear': bool(r[2]), 'antiflood': bool(r[3]), 'captcha': bool(r[4])}
    return {'welcome': None, 'rules': None, 'antiswear': False, 'antiflood': False, 'captcha': False}

def save_settings(chat_id, **kwargs):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    s = get_settings(chat_id)
    s.update(kwargs)
    c.execute('INSERT OR REPLACE INTO chat_settings VALUES (?, ?, ?, ?, ?, ?)', 
              (chat_id, s['welcome'], s['rules'], int(s['antiswear']), int(s['antiflood']), int(s['captcha'])))
    conn.commit()
    conn.close()

def add_captcha(user_id, chat_id, code):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO captcha VALUES (?, ?, ?, 0)', (user_id, chat_id, code))
    conn.commit()
    conn.close()

def check_captcha(user_id, chat_id, code):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT code, attempts FROM captcha WHERE user_id = ? AND chat_id = ?', (user_id, chat_id))
    r = c.fetchone()
    if not r:
        conn.close()
        return False
    if r[0].upper() == code.upper():
        c.execute('DELETE FROM captcha WHERE user_id = ? AND chat_id = ?', (user_id, chat_id))
        conn.commit()
        conn.close()
        return True
    if r[1] >= 2:
        c.execute('DELETE FROM captcha WHERE user_id = ? AND chat_id = ?', (user_id, chat_id))
        conn.commit()
        conn.close()
        return False
    c.execute('UPDATE captcha SET attempts = attempts + 1 WHERE user_id = ? AND chat_id = ?', (user_id, chat_id))
    conn.commit()
    conn.close()
    return False

def get_chats():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT chat_id FROM chats')
    r = [x[0] for x in c.fetchall()]
    conn.close()
    return r

def add_chat(chat_id, title):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO chats VALUES (?, ?)', (str(chat_id), title))
    conn.commit()
    conn.close()

########## ВСПОМОГАТЕЛЬНЫЕ ##########
def get_user_link(user_id, chat_id):
    try:
        m = bot.get_chat_member(chat_id, user_id)
        name = get_nick(user_id) or m.user.first_name
        name = name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        if m.user.username:
            return f'<a href="https://t.me/{m.user.username.lstrip("@")}">{name}</a>'
        return f'<a href="tg://user?id={user_id}">{name}</a>'
    except:
        return f"пользователь"

def get_target(message):
    if message.reply_to_message:
        return message.reply_to_message.from_user.id
    for w in message.text.split():
        if w.startswith('@'):
            uid = get_user_id(w[1:].lower())
            if uid:
                return uid
    return None

def is_admin(chat_id, user_id):
    try:
        if user_id == OWNER_ID:
            return True
        admins = bot.get_chat_administrators(chat_id)
        for a in admins:
            if a.user.id == user_id and (a.status == 'creator' or a.can_restrict_members):
                return True
    except:
        pass
    return False

def have_rights(message):
    return is_admin(message.chat.id, message.from_user.id)

def parse_time(text):
    text = text.lower()
    patterns = [(r'(\d+)\s*мин', 60), (r'(\d+)\s*час', 3600), (r'(\d+)\s*дн', 86400),
                (r'(\d+)\s*м', 60), (r'(\d+)\s*ч', 3600), (r'(\d+)\s*д', 86400)]
    for p, m in patterns:
        match = re.search(p, text)
        if match:
            return int(match.group(1)) * m
    return 3600

def format_time(seconds):
    if seconds < 60:
        return f"{seconds} сек"
    if seconds < 3600:
        return f"{seconds//60} мин"
    if seconds < 86400:
        return f"{seconds//3600} ч"
    return f"{seconds//86400} дн"

########## БОТ ##########
bot = telebot.TeleBot(BOT_TOKEN)
print("✅ Бот запущен")

########## КОМАНДЫ ##########
@bot.message_handler(commands=['start'])
def cmd_start(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📋 Команды", callback_data="help"),
        types.InlineKeyboardButton("💎 Премиум", callback_data="premium"),
        types.InlineKeyboardButton("🛡️ Модерация", callback_data="mod_help"),
        types.InlineKeyboardButton("💕 RP", callback_data="rp_help"),
        types.InlineKeyboardButton("⚙️ Админ", callback_data="admin")
    )
    bot.send_message(message.chat.id, 
                     f"🍬 <b>Барбариска Бот</b>\n\nПривет, {message.from_user.first_name}!\nЯ помогу с модерацией и RP.\n\nRP команд: {len(rp_data)}", 
                     parse_mode='HTML', reply_markup=markup)

@bot.message_handler(commands=['help'])
def cmd_help(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛡️ Модерация", callback_data="mod_help"),
        types.InlineKeyboardButton("💕 RP", callback_data="rp_help"),
        types.InlineKeyboardButton("💎 Премиум", callback_data="premium"),
        types.InlineKeyboardButton("🏠 Главное", callback_data="main_menu")
    )
    bot.send_message(message.chat.id, 
                     "📋 <b>Команды бота</b>\n\n• /start - старт\n• /help - помощь\n• /premium - премиум\n• /admin - админка", 
                     parse_mode='HTML', reply_markup=markup)

########## АДМИН ПАНЕЛЬ ##########
@bot.message_handler(commands=['admin'])
def cmd_admin(message):
    if not have_rights(message):
        bot.reply_to(message, "❌ Только для админов!")
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("👋 Приветствие", callback_data="admin_welcome"),
        types.InlineKeyboardButton("📜 Правила", callback_data="admin_rules"),
        types.InlineKeyboardButton("🚫 Антимат", callback_data="admin_antiswear"),
        types.InlineKeyboardButton("🔐 Капча", callback_data="admin_captcha"),
        types.InlineKeyboardButton("🏠 Главное", callback_data="main_menu")
    )
    bot.send_message(message.chat.id, "🛡️ <b>Панель администратора</b>", parse_mode='HTML', reply_markup=markup)

########## ПРЕМИУМ ##########
@bot.message_handler(commands=['premium'])
def cmd_premium(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💎 Купить 30 дней", callback_data="buy_30"))
    bot.send_message(message.chat.id, 
                     "💎 <b>Премиум</b>\n\n• Безлимитные RP\n• 15 RP/день бесплатно\n\n30 дней — 50 ⭐", 
                     parse_mode='HTML', reply_markup=markup)

########## RP КОМАНДЫ ##########
@bot.message_handler(func=lambda m: m.text and m.chat.type != 'private')
def handle_rp(message):
    text = message.text.lower().strip()
    if not text:
        return
    cmd = text.split()[0]
    if cmd not in rp_data:
        return
    
    target_id = get_target(message)
    if not target_id:
        target_id = message.from_user.id
    
    sender = get_nick(message.from_user.id) or message.from_user.first_name
    sender = sender.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    target = get_user_link(target_id, message.chat.id)
    
    if not check_sub(message.from_user.id):
        used = check_rp_limit(message.from_user.id)
        if used >= 15:
            bot.reply_to(message, "❌ Лимит 15 RP в день. Купи премиум!")
            return
        add_rp_usage(message.from_user.id)
    
    data = rp_data[cmd]
    if random.random() < 0.3:
        resp = data.get('reject', data.get('accept', '')).format(sender=sender, target=target)
    else:
        resp = data['accept'].format(sender=sender, target=target)
    
    bot.reply_to(message, resp, parse_mode='HTML')

########## МОДЕРАЦИЯ ##########
@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith('БАН'))
def mod_ban(message):
    if not have_rights(message):
        bot.reply_to(message, "❌ Нет прав!")
        return
    target = get_target(message)
    if not target:
        bot.reply_to(message, "❌ Укажи пользователя")
        return
    if is_admin(message.chat.id, target):
        bot.reply_to(message, "❌ Нельзя забанить админа!")
        return
    try:
        bot.ban_chat_member(message.chat.id, target)
        bot.reply_to(message, f"🔨 Забанен {get_user_link(target, message.chat.id)}", parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, f"❌ {e}")

@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith('КИК'))
def mod_kick(message):
    if not have_rights(message):
        bot.reply_to(message, "❌ Нет прав!")
        return
    target = get_target(message)
    if not target:
        bot.reply_to(message, "❌ Укажи пользователя")
        return
    if is_admin(message.chat.id, target):
        bot.reply_to(message, "❌ Нельзя кикнуть админа!")
        return
    try:
        bot.ban_chat_member(message.chat.id, target)
        bot.unban_chat_member(message.chat.id, target)
        bot.reply_to(message, f"👢 Кикнут {get_user_link(target, message.chat.id)}", parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, f"❌ {e}")

@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith('МУТ'))
def mod_mute(message):
    if not have_rights(message):
        bot.reply_to(message, "❌ Нет прав!")
        return
    target = get_target(message)
    if not target:
        bot.reply_to(message, "❌ Укажи пользователя")
        return
    if is_admin(message.chat.id, target):
        bot.reply_to(message, "❌ Нельзя замутить админа!")
        return
    seconds = parse_time(message.text)
    try:
        bot.restrict_chat_member(message.chat.id, target, until_date=message.date+seconds, can_send_messages=False)
        bot.reply_to(message, f"🔇 Замьючен {get_user_link(target, message.chat.id)} на {format_time(seconds)}", parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, f"❌ {e}")

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'РАЗМУТ')
def mod_unmute(message):
    if not have_rights(message):
        bot.reply_to(message, "❌ Нет прав!")
        return
    target = get_target(message)
    if not target:
        bot.reply_to(message, "❌ Укажи пользователя")
        return
    try:
        bot.restrict_chat_member(message.chat.id, target, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True)
        bot.reply_to(message, f"🔊 Размьючен {get_user_link(target, message.chat.id)}", parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, f"❌ {e}")

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'ВАРН')
def mod_warn(message):
    if not have_rights(message):
        bot.reply_to(message, "❌ Нет прав!")
        return
    target = get_target(message)
    if not target:
        bot.reply_to(message, "❌ Укажи пользователя")
        return
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT count FROM warns WHERE user_id = ?', (target,))
    r = c.fetchone()
    cnt = (r[0] if r else 0) + 1
    c.execute('INSERT OR REPLACE INTO warns VALUES (?, ?, ?)', (target, cnt, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    if cnt >= 3:
        try:
            bot.ban_chat_member(message.chat.id, target)
            bot.reply_to(message, f"⚠️ 3/3 — забанен!")
        except:
            bot.reply_to(message, f"⚠️ Варн {cnt}/3")
    else:
        bot.reply_to(message, f"⚠️ Варн {cnt}/3")

########## БРАК ##########
@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'БРАК')
def cmd_marry(message):
    target = get_target(message)
    if not target:
        bot.reply_to(message, "❌ Укажи пользователя")
        return
    if target == message.from_user.id:
        bot.reply_to(message, "❌ С собой нельзя")
        return
    if is_married(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Ты уже в браке")
        return
    if is_married(message.chat.id, target):
        bot.reply_to(message, "❌ Он/она уже в браке")
        return
    req_id = str(uuid.uuid4())
    add_marry_req(req_id, message.chat.id, message.from_user.id, message.from_user.first_name, target)
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Да", callback_data=f"marry_yes_{req_id}"),
        types.InlineKeyboardButton("❌ Нет", callback_data=f"marry_no_{req_id}")
    )
    bot.send_message(message.chat.id, 
                     f"{get_user_link(message.from_user.id, message.chat.id)} хочет брак с {get_user_link(target, message.chat.id)}!",
                     parse_mode='HTML', reply_markup=markup)

@bot.message_handler(func=lambda m: m.text and m.text.upper() == 'РАЗВОД')
def cmd_divorce(message):
    spouse = del_marriage(message.chat.id, message.from_user.id)
    if spouse:
        bot.reply_to(message, f"💔 Развод с {get_user_link(spouse, message.chat.id)}", parse_mode='HTML')
    else:
        bot.reply_to(message, "❌ Ты не в браке")

########## НИКИ ##########
@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith('+НИК '))
def set_nick_cmd(message):
    nick = message.text[5:].strip()
    if nick:
        set_nick(message.from_user.id, nick)
        bot.reply_to(message, f"✅ Ник: {nick}")

@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith('+ОПИСАНИЕ '))
def set_bio_cmd(message):
    bio = message.text[10:].strip()
    if bio:
        set_bio(message.from_user.id, bio)
        bot.reply_to(message, f"✅ Описание: {bio}")

########## НОВЫЙ УЧАСТНИК ##########
@bot.message_handler(content_types=['new_chat_members'])
def on_new_member(message):
    for u in message.new_chat_members:
        if u.id == bot.get_me().id:
            add_chat(message.chat.id, message.chat.title)
            bot.send_message(message.chat.id, "🍬 Всем привет! Я Барбариска")
        else:
            s = get_settings(message.chat.id)
            if s['welcome']:
                bot.send_message(message.chat.id, s['welcome'].replace('{user}', u.first_name))
            if s['captcha']:
                code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=4))
                add_captcha(u.id, message.chat.id, code)
                bot.send_message(message.chat.id, f"🔐 {u.first_name}, введи код: {code}")
                try:
                    bot.restrict_chat_member(message.chat.id, u.id, can_send_messages=False)
                except:
                    pass

########## CALLBACK ##########
@bot.callback_query_handler(func=lambda c: True)
def on_callback(c):
    if c.data == "main_menu":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📋 Команды", callback_data="help"),
            types.InlineKeyboardButton("💎 Премиум", callback_data="premium"),
            types.InlineKeyboardButton("🛡️ Модерация", callback_data="mod_help"),
            types.InlineKeyboardButton("💕 RP", callback_data="rp_help"),
            types.InlineKeyboardButton("⚙️ Админ", callback_data="admin")
        )
        bot.edit_message_text("🍬 <b>Барбариска Бот</b>\n\nВыбери действие:", 
                              c.message.chat.id, c.message.message_id, parse_mode='HTML', reply_markup=markup)
    
    elif c.data == "help":
        bot.answer_callback_query(c.id)
        cmd_help(c.message)
    
    elif c.data == "mod_help":
        bot.answer_callback_query(c.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🏠 Главное", callback_data="main_menu"))
        bot.edit_message_text(
            "🛡️ <b>Модерация</b>\n\n• Бан @user\n• Кик @user\n• Мут 15м\n• Размут\n• Варн\n• +чат / -чат",
            c.message.chat.id, c.message.message_id, parse_mode='HTML', reply_markup=markup)
    
    elif c.data == "rp_help":
        bot.answer_callback_query(c.id)
        cmds = list(rp_data.keys())[:20]
        text = "💕 <b>RP команды</b>\n\n" + "\n".join([f"• {x}" for x in cmds])
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🏠 Главное", callback_data="main_menu"))
        bot.edit_message_text(text, c.message.chat.id, c.message.message_id, parse_mode='HTML', reply_markup=markup)
    
    elif c.data == "premium":
        bot.answer_callback_query(c.id)
        cmd_premium(c.message)
    
    elif c.data == "admin":
        bot.answer_callback_query(c.id)
        if not have_rights(c.message):
            bot.answer_callback_query(c.id, "❌ Только админ!")
            return
        cmd_admin(c.message)
    
    elif c.data == "admin_settings":
        if not have_rights(c.message):
            bot.answer_callback_query(c.id, "❌ Только админ!")
            return
        s = get_settings(c.message.chat.id)
        text = f"⚙️ <b>Настройки</b>\n\nАнтимат: {'✅' if s['antiswear'] else '❌'}\nКапча: {'✅' if s['captcha'] else '❌'}"
        bot.answer_callback_query(c.id)
        bot.send_message(c.message.chat.id, text, parse_mode='HTML')
    
    elif c.data == "admin_broadcast":
        if not have_rights(c.message):
            bot.answer_callback_query(c.id, "❌ Только админ!")
            return
        bot.answer_callback_query(c.id)
        msg = bot.send_message(c.message.chat.id, "📢 Введи текст для рассылки:")
        bot.register_next_step_handler(msg, do_broadcast)
    
    elif c.data == "admin_welcome":
        if not have_rights(c.message):
            bot.answer_callback_query(c.id, "❌ Только админ!")
            return
        bot.answer_callback_query(c.id)
        msg = bot.send_message(c.message.chat.id, "👋 Введи приветствие (используй {user}):")
        bot.register_next_step_handler(msg, set_welcome)
    
    elif c.data == "admin_antiswear":
        if not have_rights(c.message):
            bot.answer_callback_query(c.id, "❌ Только админ!")
            return
        s = get_settings(c.message.chat.id)
        save_settings(c.message.chat.id, antiswear=not s['antiswear'])
        bot.answer_callback_query(c.id, f"Антимат {'включен' if not s['antiswear'] else 'выключен'}")
    
    elif c.data == "admin_captcha":
        if not have_rights(c.message):
            bot.answer_callback_query(c.id, "❌ Только админ!")
            return
        s = get_settings(c.message.chat.id)
        save_settings(c.message.chat.id, captcha=not s['captcha'])
        bot.answer_callback_query(c.id, f"Капча {'включена' if not s['captcha'] else 'выключена'}")
    
    elif c.data == "buy_30":
        bot.answer_callback_query(c.id, "Покупка через Stars...")
        bot.send_invoice(c.message.chat.id, "Премиум 30 дней", "Безлимитные RP", "premium_30", "", "XTR", [types.LabeledPrice("Премиум", 50)])
    
    elif c.data.startswith("marry_"):
        _, ans, rid = c.data.split('_')
        req = get_marry_req(rid)
        if not req:
            bot.answer_callback_query(c.id, "❌ Запрос устарел")
            return
        chat, from_id, from_name, to_id = req
        if c.from_user.id != to_id:
            bot.answer_callback_query(c.id, "❌ Не твой запрос")
            return
        if ans == "yes":
            add_marriage(chat, from_id, to_id)
            bot.edit_message_text(f"💍 Брак заключён!", c.message.chat.id, c.message.message_id)
            bot.answer_callback_query(c.id, "✅ Поздравляем!")
        else:
            bot.edit_message_text(f"💔 Отказ", c.message.chat.id, c.message.message_id)
            bot.answer_callback_query(c.id, "❌ Отказ")
        del_marry_req(rid)

########## РАССЫЛКА ##########
def do_broadcast(message):
    if not have_rights(message):
        return
    text = message.text
    chats = get_chats()
    sent = 0
    for cid in chats:
        try:
            bot.send_message(int(cid), f"📢 <b>Рассылка</b>\n\n{text}", parse_mode='HTML')
            sent += 1
            time.sleep(1)
        except:
            pass
    bot.reply_to(message, f"✅ Отправлено в {sent} чатов")

def set_welcome(message):
    if not have_rights(message):
        return
    save_settings(message.chat.id, welcome=message.text)
    bot.reply_to(message, "✅ Приветствие сохранено")

########## АНТИМАТ ##########
@bot.message_handler(func=lambda m: True)
def anti_swear(message):
    if message.chat.type == 'private':
        return
    s = get_settings(message.chat.id)
    if s['antiswear']:
        bad = ['хуй', 'пизда', 'бля', 'сука', 'ебл', 'нахуй', 'пиздец']
        if any(x in message.text.lower() for x in bad):
            try:
                bot.delete_message(message.chat.id, message.message_id)
                bot.send_message(message.chat.id, f"{get_user_link(message.from_user.id, message.chat.id)}, не матерись!", parse_mode='HTML')
            except:
                pass
            return
    
    if s['captcha']:
        if check_captcha(message.from_user.id, message.chat.id, message.text):
            bot.reply_to(message, "✅ Капча пройдена!")
            try:
                bot.restrict_chat_member(message.chat.id, message.from_user.id, can_send_messages=True)
            except:
                pass

########## ЗАПУСК ##########
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    print("🚀 Бот работает...")
    bot.infinity_polling()
