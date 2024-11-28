from typing import List, Optional
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.database import cursor

def create_target_keyboard(players: List[int], exclude_id: Optional[int], action_type: str, chat_id: int) -> InlineKeyboardMarkup:
    """Create a keyboard for selecting target players."""
    keyboard = InlineKeyboardBuilder()
    
    for player_id in players:
        if exclude_id is not None and player_id == exclude_id:
            continue
            
        cursor.execute("SELECT tg_name FROM users WHERE id = %s", (player_id,))
        player_name = cursor.fetchone()[0]
        
        keyboard.button(
            text=player_name,
            callback_data=f"{action_type}_{player_id}_{chat_id}"
        )
    
    keyboard.adjust(1)  # One button per row
    return keyboard.as_markup()

def create_vote_keyboard(players: List[int], chat_id: int) -> InlineKeyboardMarkup:
    """Create a keyboard for voting."""
    keyboard = InlineKeyboardBuilder()
    
    for player_id in players:
        cursor.execute("SELECT tg_name FROM users WHERE id = %s", (player_id,))
        player_name = cursor.fetchone()[0]
        
        keyboard.button(
            text=player_name,
            callback_data=f"vote_{player_id}_{chat_id}"
        )
    
    keyboard.adjust(1)  # One button per row
    return keyboard.as_markup()

def create_join_game_keyboard(bot_username: str, chat_id: int) -> InlineKeyboardMarkup:
    """Create a keyboard for joining the game."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="Приєднатися до гри!",
            url=f"https://t.me/{bot_username}?start=join_{chat_id}"
        )
    ]])

def create_role_action_keyboard(action_type: str) -> InlineKeyboardMarkup:
    """Create a keyboard for role-specific actions."""
    keyboard = InlineKeyboardBuilder()
    
    if action_type == "mafia":
        keyboard.button(text="Вбити", callback_data="action_kill")
    elif action_type == "doctor":
        keyboard.button(text="Лікувати", callback_data="action_heal")
    elif action_type == "detective":
        keyboard.button(text="Перевірити", callback_data="action_investigate")
    
    keyboard.adjust(1)
    return keyboard.as_markup()
