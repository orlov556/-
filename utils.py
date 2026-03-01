import re
import random
from datetime import datetime
from typing import List, Tuple
import aiohttp

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

class ProfanityFilter:
    def __init__(self):
        self.bad_words = [
            r'бля\w*', r'хуй\w*', r'пизд\w*', r'еба\w*', r'нах\w*',
            r'сук\w*', r'пидор\w*', r'гандон\w*', r'мудак\w*',
            r'долбо\w*', r'уеб\w*', r'залуп\w*', r'шлюх\w*'
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
                "{user1} заключил {user2} в объятия, и мир стал лучше ✨"
            ],
            'поцеловать': [
                "{user1} нежно поцеловал {user2} в щечку 💋",
                "{user1} подарил {user2} сладкий поцелуй 💝",
                "{user1} чмокнул {user2} в носик 🥰"
            ],
            'погладить': [
                "{user1} гладит {user2} по голове, как самого лучшего котика 🐱",
                "{user1} нежно погладил {user2} по спинке ✨",
                "{user1} погладил {user2}, и тот довольно замурлыкал 😊"
            ],
            'укусить': [
                "{user1} игриво укусил {user2} за плечо 😈",
                "{user1} куснул {user2} за ушко 👂",
                "{user1} оставил маленький укус на руке {user2} 🌸"
            ],
            'шлепнуть': [
                "{user1} игриво шлепнул {user2} по попе 😏",
                "{user1} легонько шлепнул {user2} и убежал 🏃",
                "{user1} шлепнул {user2} и засмущался 😳"
            ],
            'прижать_к_стене': [
                "{user1} прижал {user2} к стене, шепча на ушко нежности 💕",
                "{user1} нежно прижал {user2} к стене, и время остановилось 🌹",
                "{user1} прижал {user2} к стене, создавая интимную атмосферу ✨"
            ],
            'прошептать_на_ушко': [
                "{user1} прошептал {user2} на ушко что-то очень приятное 🥰",
                "{user1} шепчет {user2} комплименты, от которых {user2} краснеет 😊",
                "{user1} прошептал {user2} на ушко самый сладкий секрет 💫"
            ]
        }

    def get_action_text(self, action: str, user1: str, user2: str) -> str:
        if action not in self.rp_actions:
            return None
        text = random.choice(self.rp_actions[action])
        return text.format(user1=user1, user2=user2)

class ProbabilityAnswers:
    def __init__(self):
        self.answers = [
            (1.0, "Барбарис уверен на 100%! Бесспорно да! 🌟"),
            (0.9, "Скорее всего да, Барбарис почти уверен ✨"),
            (0.8, "Вероятность высока, дерзай! 🍀"),
            (0.7, "Скорее да, чем нет 📈"),
            (0.6, "Барбарис думает, что да, но не настаивает 🤔"),
            (0.5, "50 на 50, решай сам(а) 🎲"),
            (0.4, "Скорее нет, чем да 📉"),
            (0.3, "Маловероятно, но возможно 🌧️"),
            (0.2, "Барбарис сомневается, лучше перепроверь 🌪️"),
            (0.1, "Очень вряд ли, готовься к худшему 💨"),
            (0.0, "Ни в коем случае! Барбарис категоричен ⛔")
        ]

    def get_answer(self) -> Tuple[str, int]:
        answer = random.choice(self.answers)
        probability = int(answer[0] * 100)
        return answer[1], probability

async def get_random_gif(tag: str, api_key: str = None) -> str:
    """Получает случайную гифку с Tenor"""
    if not api_key:
        return None
    
    async with aiohttp.ClientSession() as session:
        url = f"https://tenor.googleapis.com/v2/search?q={tag}&key={api_key}&limit=50"
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if data['results']:
                    gif = random.choice(data['results'])
                    return gif['media_formats']['tinygif']['url']
    return None
