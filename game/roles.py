from abc import ABC, abstractmethod
from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from typing import Optional, List

class Role(ABC):
    def __init__(self, player_id: int, name: str):
        self.player_id = player_id
        self.name = name
        self.is_alive = True
        self.night_action_used = False
        self.description = "Базова роль"
        self.action_description = "Немає спеціальних дій"
    
    @abstractmethod
    async def night_action(self, target_id: int, bot: Bot) -> None:
        pass
    
    @abstractmethod
    def get_action_keyboard(self, players: List[int], chat_id: int) -> InlineKeyboardMarkup:
        pass
    
    @abstractmethod
    def get_night_prompt(self) -> str:
        pass

class Mafia(Role):
    def __init__(self, player_id: int):
        super().__init__(player_id, "Аль Капоне")
        self.kill_target: Optional[int] = None
        self.description = "Ви - голова мафії! Ваша мета - знищити всіх мирних жителів."
        self.action_description = "Вночі ви можете вибрати одного гравця для вбивства."
    
    async def night_action(self, target_id: int, bot: Bot) -> None:
        self.kill_target = target_id
        self.night_action_used = True
    
    def get_action_keyboard(self, players: List[int], chat_id: int) -> InlineKeyboardMarkup:
        from game.keyboards import create_target_keyboard
        return create_target_keyboard(players, self.player_id, "kill", chat_id)
    
    def get_night_prompt(self) -> str:
        return "🎭 Виберіть свою жертву:"

class Doctor(Role):
    def __init__(self, player_id: int):
        super().__init__(player_id, "Лікар")
        self.heal_target: Optional[int] = None
        self.self_heals_remaining = 1
        self.description = "Ви - лікар! Ваша мета - рятувати життя та допомогти мирним жителям перемогти мафію."
        self.action_description = "Вночі ви можете вилікувати одного гравця (включаючи себе, але тільки один раз за гру)."
    
    async def night_action(self, target_id: int, bot: Bot) -> None:
        if target_id == self.player_id:
            if self.self_heals_remaining > 0:
                self.self_heals_remaining -= 1
            else:
                return
        self.heal_target = target_id
        self.night_action_used = True
    
    def get_action_keyboard(self, players: List[int], chat_id: int) -> InlineKeyboardMarkup:
        from game.keyboards import create_target_keyboard
        return create_target_keyboard(players, None, "heal", chat_id)
    
    def get_night_prompt(self) -> str:
        return "👨‍⚕️ Кого ви хочете вилікувати цієї ночі?"

class Detective(Role):
    def __init__(self, player_id: int):
        super().__init__(player_id, "Детектив")
        self.investigated_target: Optional[int] = None
        self.description = "Ви - детектив! Ваша мета - знайти мафію та допомогти мирним жителям."
        self.action_description = "Вночі ви можете перевірити одного гравця і дізнатися, чи є він мафією."
    
    async def night_action(self, target_id: int, bot: Bot) -> None:
        self.investigated_target = target_id
        self.night_action_used = True
    
    def get_action_keyboard(self, players: List[int], chat_id: int) -> InlineKeyboardMarkup:
        from game.keyboards import create_target_keyboard
        return create_target_keyboard(players, self.player_id, "investigate", chat_id)
    
    def get_night_prompt(self) -> str:
        return "🕵️ Кого ви хочете перевірити цієї ночі?"

class Civilian(Role):
    def __init__(self, player_id: int):
        super().__init__(player_id, "Мирний житель")
        self.description = "Ви - мирний житель! Ваша мета - знайти і викрити мафію разом з іншими мирними жителями."
        self.action_description = "Вночі ви спите. Вдень ви можете голосувати проти підозрілих гравців."
    
    async def night_action(self, target_id: int, bot: Bot) -> None:
        pass  # Civilians have no night action
    
    def get_action_keyboard(self, players: List[int], chat_id: int) -> InlineKeyboardMarkup:
        return None  # Civilians have no action keyboard
    
    def get_night_prompt(self) -> str:
        return "😴 Ви мирний житель. Спіть спокійно!"
