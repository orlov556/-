import re
import random
import aiohttp
import requests
from datetime import datetime
from typing import List, Tuple, Optional
import config

class TextFormatter:
    @staticmethod
    def escape_markdown(text: str) -> str:
        """Экранирует специальные символы для Markdown"""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    @staticmethod
    def format_user_name(user) -> str:
        """Форматирует имя пользователя"""
        name = user.first_name
        if user.last_name:
            name += f" {user.last_name}"
        return name

class CaptchaGenerator:
    @staticmethod
    def generate_question() -> Tuple[str, str]:
        """Генерирует простой вопрос для капчи"""
        operations = ['+', '-']
        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        op = random.choice(operations)
        
        if op == '+':
            answer = num1 + num2
            question = f"Сколько будет {num1} + {num2}?"
        else:
            # Чтобы не было отрицательных результатов
            if num1 < num2:
                num1, num2 = num2, num1
            answer = num1 - num2
            question = f"Сколько будет {num1} - {num2}?"
        
        return question, str(answer)

    @staticmethod
    def generate_button_captcha() -> Tuple[str, str]:
        """Генерирует капчу с кнопкой"""
        captcha_id = ''.join(random.choices('0123456789abcdef', k=8))
        return f"captcha_{captcha_id}", captcha_id

class ProfanityFilter:
    def __init__(self):
        self.bad_words = [
            r'бля\w*', r'хуй\w*', r'пизд\w*', r'еба\w*', r'нах\w*',
            r'сук\w*', r'пидор\w*', r'гандон\w*', r'мудак\w*',
            r'долбо\w*', r'уеб\w*', r'залуп\w*', r'шлюх\w*',
            r'хер\w*', r'залуп\w*', r'ебан\w*', r'пидр\w*'
        ]
        self.pattern = re.compile('|'.join(self.bad_words), re.IGNORECASE)

    def contains_profanity(self, text: str) -> bool:
        return bool(self.pattern.search(text))

    def censor(self, text: str) -> str:
        return self.pattern.sub('[цензура]', text)

class RPGenerator:
    def __init__(self):
        self.rp_actions = {
            'обнять': [
                "{user1} нежно обнял {user2}, и в комнате стало теплее ☀️",
                "{user1} крепко обнимает {user2}, даря свое тепло 🤗",
                "{user1} заключил {user2} в объятия, и мир стал лучше ✨",
                "{user1} обнял {user2} так крепко, что все проблемы исчезли 💫",
                "{user1} подарил {user2} самые теплые объятия 🥰"
            ],
            'поцеловать': [
                "{user1} нежно поцеловал {user2} в щечку 💋",
                "{user1} подарил {user2} сладкий поцелуй 💝",
                "{user1} чмокнул {user2} в носик 🥰",
                "{user1} поцеловал {user2} в лоб, как самого дорогого человека 💕",
                "{user1} украл у {user2} сладкий поцелуй 🌸"
            ],
            'погладить': [
                "{user1} гладит {user2} по голове, как самого лучшего котика 🐱",
                "{user1} нежно погладил {user2} по спинке ✨",
                "{user1} погладил {user2}, и тот довольно замурлыкал 😊",
                "{user1} гладит {user2} по волосам, вызывая приятную дрожь 💫",
                "{user1} нежно поглаживает {user2} по плечам 🌙"
            ],
            'укусить': [
                "{user1} игриво укусил {user2} за плечо 😈",
                "{user1} куснул {user2} за ушко 👂",
                "{user1} оставил маленький укус на руке {user2} 🌸",
                "{user1} легонько прикусил мочку уха {user2} 🌟",
                "{user1} куснул {user2} и довольно улыбнулся 😏"
            ],
            'шлепнуть': [
                "{user1} игриво шлепнул {user2} по попе 😏",
                "{user1} легонько шлепнул {user2} и убежал 🏃",
                "{user1} шлепнул {user2} и засмущался 😳",
                "{user1} звонко шлепнул {user2}, вызвав румянец на щеках 🌸",
                "{user1} игриво шлепнул {user2} и подмигнул 😉"
            ],
            'прижать_к_стене': [
                "{user1} прижал {user2} к стене, шепча на ушко нежности 💕",
                "{user1} нежно прижал {user2} к стене, и время остановилось 🌹",
                "{user1} прижал {user2} к стене, создавая интимную атмосферу ✨",
                "{user1} прижался к {user2} у стены, чувствуя биение сердца 💓",
                "{user1} заботливо прижал {user2} к стене, укрывая от всего мира 🌙"
            ],
            'прошептать_на_ушко': [
                "{user1} прошептал {user2} на ушко что-то очень приятное 🥰",
                "{user1} шепчет {user2} комплименты, от которых {user2} краснеет 😊",
                "{user1} прошептал {user2} на ушко самый сладкий секрет 💫",
                "{user1} шепнул {user2} нежные слова, от которых по коже побежали мурашки ✨",
                "{user1} прошептал на ушко {user2} признание в любви 💕"
            ],
            'покормить': [
                "{user1} кормит {user2} с ложечки вареньем 🍯",
                "{user1} угощает {user2} вкусным чаем с печеньками 🍪",
                "{user1} кормит {user2} самыми спелыми ягодами 🍓",
                "{user1} приготовил ужин для {user2} и кормит с особой нежностью 🍽️"
            ],
            'погладить_по_голове': [
                "{user1} нежно гладит {user2} по голове, успокаивая 🌙",
                "{user1} треплет {user2} по голове, как самого лучшего друга 🐾",
                "{user1} ласково гладит {user2} по макушке, вызывая улыбку 😊"
            ]
        }

    def get_action_text(self, action: str, user1: str, user2: str) -> str:
        if action not in self.rp_actions:
            return None
        text = random.choice(self.rp_actions[action])
        return text.format(user1=user1, user2=user2)

    def get_all_actions(self) -> list:
        """Возвращает список всех доступных RP действий"""
        return list(self.rp_actions.keys())

class ProbabilityAnswers:
    def __init__(self):
        self.answers = [
            (1.0, "🍒 Барбарис уверен на 100%! Бесспорно да!"),
            (0.95, "✨ Абсолютно точно! Барбарис не сомневается!"),
            (0.9, "🌟 С вероятностью 90% - да! Звезды сошлись!"),
            (0.85, "💫 Почти наверняка! Барбарис чувствует это!"),
            (0.8, "🎯 Очень высокая вероятность! Дерзай!"),
            (0.75, "🌿 Скорее всего да, Барбарис в этом уверен"),
            (0.7, "🍀 Хорошие шансы! Барбарис верит в успех!"),
            (0.65, "📈 Склоняюсь к положительному ответу"),
            (0.6, "🤔 Скорее да, чем нет, но не настаиваю"),
            (0.55, "🌸 Чуть больше шансов на да, чем на нет"),
            (0.5, "🎲 50 на 50 - решай сам(а), Барбарис пассует"),
            (0.45, "🌧️ Небольшой перевес в сторону отрицательного ответа"),
            (0.4, "💨 Скорее нет, чем да, но всякое бывает"),
            (0.35, "🌪️ Шансы невелики, Барбарис сомневается"),
            (0.3, "⛈️ Маловероятно, готовься к другому исходу"),
            (0.25, "❄️ Очень маленькая вероятность, почти нет"),
            (0.2, "🌊 Барбарис говорит - нет, с вероятностью 80%"),
            (0.15, "⚡ Крайне маловероятно, но чудеса случаются"),
            (0.1, "💔 Почти нет, Барбарис расстроен ответом"),
            (0.05, "🌑 Шансы призрачны, лучше и не надейся"),
            (0.0, "⛔ Ни в коем случае! Барбарис категоричен!")
        ]

    def get_answer(self) -> Tuple[str, int]:
        """Возвращает случайный ответ и вероятность в процентах"""
        answer = random.choice(self.answers)
        probability = int(answer[0] * 100)
        return answer[1], probability

class GifManager:
    """Класс для работы с гифками через различные API"""
    
    def __init__(self, tenor_api_key: str = None):
        self.tenor_api_key = tenor_api_key
        self.gif_terms = {
            'обнять': ['hug', 'anime hug', 'cute hug'],
            'поцеловать': ['kiss', 'anime kiss', 'romantic kiss'],
            'погладить': ['pat', 'headpat', 'anime pat'],
            'укусить': ['bite', 'anime bite', 'playful bite'],
            'шлепнуть': ['slap', 'anime slap', 'playful slap'],
            'прижать_к_стене': ['wallpunch', 'anime wall', 'romantic wall'],
            'прошептать_на_ушко': ['whisper', 'anime whisper', 'secret'],
            'покормить': ['feed', 'anime feed', 'cute feed'],
            'погладить_по_голове': ['headpat', 'anime headpat', 'pet']
        }

    async def get_random_gif(self, action: str) -> Optional[str]:
        """
        Получает случайную гифку для действия
        Сначала пробует Tenor API, если есть ключ
        Если нет, возвращает None (бот будет использовать только текст)
        """
        if not self.tenor_api_key:
            return None
        
        if action not in self.gif_terms:
            return None
        
        search_terms = self.gif_terms[action]
        search_term = random.choice(search_terms)
        
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://tenor.googleapis.com/v2/search"
                params = {
                    'q': search_term,
                    'key': self.tenor_api_key,
                    'limit': 20,
                    'media_filter': 'tinygif'
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('results'):
                            gif = random.choice(data['results'])
                            return gif['media_formats']['tinygif']['url']
        except Exception as e:
            print(f"Error fetching GIF: {e}")
            return None
        
        return None

    def get_random_sticker(self) -> Optional[str]:
        """
        Возвращает ID случайного стикера из локального набора
        Можно добавить позже, если будут свои стикеры
        """
        return None

class TimeParser:
    """Парсер временных интервалов"""
    
    @staticmethod
    def parse_time(time_str: str) -> Optional[int]:
        """
        Парсит строку времени в секунды
        Поддерживает форматы: 30s, 5m, 2h, 1d
        """
        if not time_str:
            return None
        
        match = re.match(r'^(\d+)([smhd])$', time_str.lower())
        if not match:
            return None
        
        value, unit = match.groups()
        value = int(value)
        
        units = {
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400
        }
        
        return value * units.get(unit, 1)

    @staticmethod
    def format_duration(seconds: int) -> str:
        """Форматирует секунды в читаемый вид"""
        if seconds < 60:
            return f"{seconds} сек"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} мин"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} ч"
        else:
            days = seconds // 86400
            return f"{days} дн"
