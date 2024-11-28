from typing import Dict
import logging
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.deep_linking import create_start_link
import asyncio
import os

from game.game_state import GameState
from game.roles import Mafia, Doctor, Detective, Civilian
from game.keyboards import (
    create_join_game_keyboard,
    create_vote_keyboard,
    create_target_keyboard
)
from database.database import cursor, conn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store active games
active_games: Dict[int, GameState] = {}
# Store game timers
game_timers: Dict[int, asyncio.Task] = {}

router = Router()

async def start_game_after_delay(chat_id: int, message: Message):
    """Start the game after a delay if enough players have joined."""
    try:
        await asyncio.sleep(120)  # 2 minutes wait
        
        if chat_id not in active_games:
            return
            
        game = active_games[chat_id]
        if game.phase != "waiting":
            return
            
        if len(game.alive_players) < 3:
            await message.bot.send_message(
                chat_id=chat_id,
                text="❌ Недостатньо гравців для початку гри!\n"
                     "Гра скасована. Використайте /play щоб почати нову гру."
            )
            active_games.pop(chat_id, None)
            return
            
        await start_game(game, message)
        
    except Exception as e:
        logger.error(f"Error in start_game_after_delay: {e}")
        await message.bot.send_message(chat_id=chat_id, text="❌ Помилка при старті гри. Спробуйте ще раз.")
    finally:
        # Clean up timer
        game_timers.pop(chat_id, None)

async def start_game(game: GameState, message: Message):
    """Start the game with animations and player list."""
    try:
        # Assign roles
        game.assign_roles()
        game.phase = "night"
        game.round = 1
        
        # Send game start message
        await message.bot.send_message(chat_id=game.chat_id, text="Гра починається!")
        
        # Send night animation and message
        night_gif = FSInputFile("Media/night.gif")
        await message.bot.send_animation(
            chat_id=game.chat_id,
            animation=night_gif,
            caption=(
                "🌃 Ніч 1\n\n"
                "Під покровом ночі за рогом почулися постріли і виє сирена швидкої. "
                "Сержант наказав усім тісно зачинити двері. Залишаємось на сторожі. "
                "Що ж нам може принести цей світанок...."
            )
        )
        
        # Create player list with mentions
        bot = message.bot
        player_list = []
        for i, player_id in enumerate(game.alive_players, 1):
            try:
                player = await bot.get_chat_member(game.chat_id, player_id)
                name = player.user.first_name
                mention = f"[{name}](tg://user?id={player_id})"
                player_list.append(f"{i}. {mention}")
            except Exception as e:
                logger.error(f"Failed to get player info: {e}")
                player_list.append(f"{i}. Player {player_id}")
        
        # Send player list
        await message.bot.send_message(
            chat_id=game.chat_id,
            text="Список гравців:\n" + "\n".join(player_list),
            parse_mode="Markdown"
        )
        
        # Send role messages to all players
        for player_id, role in game.players.items():
            role_message = (
                f"🎭 Ваша роль: {role.name}\n"
                f"📜 Опис: {role.description}\n"
                f"❗️ Дії: {role.action_description}"
            )
            try:
                await bot.send_message(player_id, role_message)
            except Exception as e:
                logger.error(f"Failed to send role message to player {player_id}: {e}")
        
        # Start night phase
        await handle_night_phase(game, message)
        
    except Exception as e:
        logger.error(f"Error starting game: {e}")
        await message.bot.send_message(chat_id=game.chat_id, text="❌ Помилка при старті гри. Спробуйте ще раз.")

async def handle_night_phase(game: GameState, message: Message):
    """Handle night phase of the game."""
    try:
        bot = message.bot
        chat_id = message.chat.id
        
        # Reset night actions
        for role in game.players.values():
            role.night_action_used = False
        
        # Send night action prompts to players with night actions
        for player_id, role in game.players.items():
            if isinstance(role, (Mafia, Doctor, Detective)) and role.is_alive:
                # Get available targets (excluding self for Mafia)
                available_targets = game.alive_players.copy()
                if isinstance(role, Mafia):
                    available_targets.remove(player_id)
                
                # Create keyboard for target selection
                keyboard = role.get_action_keyboard(available_targets, chat_id)
                
                if keyboard:
                    try:
                        # Send prompt with action keyboard
                        await bot.send_message(
                            player_id,
                            role.get_night_prompt(),
                            reply_markup=keyboard
                        )
                    except Exception as e:
                        logger.error(f"Failed to send night action prompt to player {player_id}: {e}")
        
        # Start night action timer
        game_timers[chat_id] = asyncio.create_task(end_night_phase(game, message))
        
    except Exception as e:
        logger.error(f"Error in night phase: {e}")
        await message.bot.send_message(chat_id=game.chat_id, text="❌ Помилка в нічній фазі. Спробуйте перезапустити гру.")

async def end_night_phase(game: GameState, message: Message, timeout: int = 30):
    """End night phase after timeout or when all actions are completed."""
    try:
        # Wait for timeout
        await asyncio.sleep(timeout)
        
        # Process night actions
        killed_player = None
        saved_player = None
        
        # Find Mafia's target
        for role in game.players.values():
            if isinstance(role, Mafia) and role.is_alive:
                killed_player = role.kill_target
                break
        
        # Check if Doctor saved the target
        for role in game.players.values():
            if isinstance(role, Doctor) and role.is_alive:
                saved_player = role.heal_target
        
        # Process Detective's investigation
        for role in game.players.values():
            if isinstance(role, Detective) and role.is_alive and role.investigated_target:
                target_role = game.players.get(role.investigated_target)
                is_mafia = isinstance(target_role, Mafia)
                try:
                    await message.bot.send_message(
                        role.player_id,
                        f"🕵️ Ваше розслідування показало, що цей гравець {'є' if is_mafia else 'не є'} мафією!"
                    )
                except Exception as e:
                    logger.error(f"Failed to send investigation result: {e}")
        
        # Process killing
        if killed_player and killed_player != saved_player:
            game.kill_player(killed_player)
            try:
                killed_name = (await message.bot.get_chat_member(game.chat_id, killed_player)).user.first_name
                await message.bot.send_message(game.chat_id, f"☠️ {killed_name} був вбитий цієї ночі!")
            except Exception as e:
                logger.error(f"Failed to announce killed player: {e}")
        else:
            await message.bot.send_message(game.chat_id, "😌 Цієї ночі ніхто не загинув!")
        
        # Start day phase
        game.phase = "day"
        await handle_day_phase(game, message)
        
    except Exception as e:
        logger.error(f"Error ending night phase: {e}")
        await message.bot.send_message(game.chat_id, "❌ Помилка при завершенні нічної фази.")
    finally:
        game_timers.pop(message.chat.id, None)

async def handle_day_phase(game: GameState, message: Message):
    """Handle day phase of the game."""
    try:
        # Announce day phase
        day_message = f"☀️ День {game.round}\n\nНастав новий день. Час обговорити події минулої ночі та знайти злочинців серед нас!"
        await message.bot.send_message(game.chat_id, day_message)
        
        # Show alive players list
        alive_players_list = []
        for i, player_id in enumerate(game.alive_players, 1):
            try:
                player = await message.bot.get_chat_member(game.chat_id, player_id)
                name = player.user.first_name
                alive_players_list.append(f"{i}. {name}")
            except Exception as e:
                logger.error(f"Failed to get player info: {e}")
                alive_players_list.append(f"{i}. Player {player_id}")
        
        alive_players_message = "Живі гравці:\n" + "\n".join(alive_players_list)
        await message.bot.send_message(game.chat_id, alive_players_message)
        
        # Create and send voting keyboard
        keyboard = create_vote_keyboard(game.alive_players, game.chat_id)
        for player_id in game.alive_players:
            try:
                await message.bot.send_message(
                    player_id,
                    "🗳 Час голосувати! Виберіть підозрюваного:",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Failed to send voting keyboard to player {player_id}: {e}")
        
        # Start voting timer
        game_timers[game.chat_id] = asyncio.create_task(end_day_phase(game, message))
        
    except Exception as e:
        logger.error(f"Error in day phase: {e}")
        await message.bot.send_message(game.chat_id, "❌ Помилка в денній фазі. Спробуйте перезапустити гру.")

@router.message(Command("play"))
async def cmd_play(message: Message):
    logger.info(f"Play command received in chat {message.chat.id}")
    
    if message.chat.type not in ["group", "supergroup"]:
        await message.bot.send_message(message.chat.id, "Ця гра доступна тільки в групових чатах!")
        return
    
    chat_id = message.chat.id
    
    # Check if game already exists
    if chat_id in active_games:
        await message.bot.send_message(message.chat.id, "Гра вже розпочата в цьому чаті!")
        return
    
    # Create new game
    game = GameState(chat_id)
    active_games[chat_id] = game
    
    # Create join link and get bot info
    bot = message.bot
    bot_info = await bot.get_me()
    
    logger.info(f"Created game in chat {chat_id}")
    
    # Start the game timer
    timer = asyncio.create_task(start_game_after_delay(chat_id, message))
    game_timers[chat_id] = timer
    
    # Send invitation message
    await message.bot.send_message(
        chat_id=chat_id,
        text="🎮 Починається нова гра в Мафію!\n"
             "Натисніть кнопку нижче, щоб приєднатися.\n"
             "Мінімальна кількість гравців: 3\n"
             "Максимальна кількість гравців: 10\n"
             "⏰ Час на приєднання: 2 хвилини\n\n"
             "Ролі для 3 гравців:\n"
             "• Аль Капоне (Мафія)\n"
             "• Лікар\n"
             "• Мирний житель",
        reply_markup=create_join_game_keyboard(bot_info.username, chat_id)
    )

@router.message(Command("force_start"))
async def cmd_force_start(message: Message):
    """Force start the game if minimum players have joined."""
    logger.info(f"Force start command received in chat {message.chat.id}")
    
    if message.chat.type not in ["group", "supergroup"]:
        await message.bot.send_message(message.chat.id, "Ця команда доступна тільки в групових чатах!")
        return
        
    chat_id = message.chat.id
    
    if chat_id not in active_games:
        await message.bot.send_message(message.chat.id, "❌ Немає активної гри для початку!")
        return
        
    game = active_games[chat_id]
    
    if game.phase != "waiting":
        await message.bot.send_message(message.chat.id, "❌ Гра вже розпочата!")
        return
        
    if len(game.alive_players) < 3:
        await message.bot.send_message(message.chat.id, "❌ Недостатньо гравців! Мінімум 3 гравці потрібно.")
        return
    
    # Cancel the auto-start timer if it exists
    if chat_id in game_timers:
        game_timers[chat_id].cancel()
        game_timers.pop(chat_id)
        
    await start_game(game, message)

@router.message(CommandStart(deep_link=True))
async def cmd_start_join(message: Message):
    logger.info(f"Start command received: {message.text}")
    
    # Get the deep link parameter from the message text
    # Format will be "/start join_CHATID"
    command_parts = message.text.split()
    if len(command_parts) != 2:
        return
        
    args = command_parts[1]  # Get the part after /start
    logger.info(f"Start command args: {args}")
    
    if not args.startswith("join_"):
        return
    
    try:
        chat_id = int(args[5:])  # Extract chat ID from "join_XXXXX"
        logger.info(f"Attempting to join game in chat {chat_id}")
    except ValueError:
        await message.bot.send_message(message.chat.id, "❌ Невірне посилання для приєднання.")
        return
    
    player_id = message.from_user.id
    
    if chat_id not in active_games:
        logger.warning(f"No active game found in chat {chat_id}")
        await message.bot.send_message(message.chat.id, "❌ Гра не знайдена або вже закінчена.")
        return
    
    game = active_games[chat_id]
    
    if game.phase != "waiting":
        await message.bot.send_message(message.chat.id, "❌ Гра вже розпочата.")
        return
    
    if len(game.alive_players) >= 10:
        await message.bot.send_message(message.chat.id, "❌ Досягнуто максимальну кількість гравців.")
        return
    
    # Add player to game
    if game.add_player(player_id, message.from_user.first_name):
        logger.info(f"Player {player_id} ({message.from_user.first_name}) joined game in chat {chat_id}")
        await message.bot.send_message(message.chat.id, "✅ Ви успішно приєднались до гри!")
        
        # Update player count in group
        await message.bot.send_message(
            chat_id=chat_id,
            text=f"👤 {message.from_user.first_name} приєднався до гри!\n"
                 f"Кількість гравців: {len(game.alive_players)}/10"
        )
    else:
        await message.bot.send_message(message.chat.id, "❌ Ви вже в грі!")

@router.message(Command("leave"))
async def cmd_leave(message: Message):
    chat_id = message.chat.id
    player_id = message.from_user.id
    
    if chat_id not in active_games:
        await message.bot.send_message(message.chat.id, "❌ В цьому чаті немає активної гри.")
        return
    
    game = active_games[chat_id]
    
    if game.phase != "waiting":
        await message.bot.send_message(message.chat.id, "❌ Не можна покинути гру, яка вже розпочата.")
        return
    
    if game.remove_player(player_id):
        await message.bot.send_message(
            chat_id=chat_id,
            text=f"👋 {message.from_user.first_name} покинув гру.\n"
                 f"Кількість гравців: {len(game.alive_players)}/10"
        )
    else:
        await message.bot.send_message(message.chat.id, "❌ Ви не були в грі.")

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Show available commands."""
    help_text = (
        "📋 Доступні команди:\n\n"
        "/play - Почати нову гру\n"
        "/force_start - Примусово почати гру (якщо є мінімум 3 гравці)\n"
        "/help - Показати це повідомлення\n"
        "/rules - Показати правила гри\n\n"
        "🎮 Мінімальна кількість гравців: 3\n"
        "👥 Максимальна кількість гравців: 10"
    )
    await message.bot.send_message(message.chat.id, help_text)

@router.message(Command("rules"))
async def cmd_rules(message: Message):
    """Show game rules."""
    rules_text = (
        "📜 Правила гри Мафія:\n\n"
        "1️⃣ Гра складається з двох фаз: День і Ніч\n\n"
        "🌙 Вночі:\n"
        "• Мафія (Аль Капоне) вибирає жертву\n"
        "• Лікар може врятувати одного гравця\n"
        "• Детектив (якщо є) може перевірити одного гравця\n\n"
        "☀️ Вдень:\n"
        "• Всі гравці обговорюють і голосують\n"
        "• Гравець з найбільшою кількістю голосів буде страчений\n\n"
        "🎯 Цілі:\n"
        "• Мафія: вбити всіх мирних жителів\n"
        "• Мирні: знайти і стратити мафію\n\n"
        "❗️ Важливо: Не розкривайте свою роль іншим гравцям!"
    )
    await message.bot.send_message(message.chat.id, rules_text)

@router.callback_query(F.data.startswith("kill_"))
async def handle_kill(callback: CallbackQuery):
    """Handle mafia's kill action."""
    try:
        chat_id = int(callback.data.split('_')[2])
        target_id = int(callback.data.split('_')[1])
        
        if chat_id not in active_games:
            await callback.answer("❌ Гра не знайдена!")
            return
            
        game = active_games[chat_id]
        player_id = callback.from_user.id
        
        if game.phase != "night":
            await callback.answer("❌ Зараз не нічна фаза!")
            return
            
        role = game.players.get(player_id)
        if not isinstance(role, Mafia):
            await callback.answer("❌ Ви не можете вбивати!")
            return
            
        if role.night_action_used:
            await callback.answer("❌ Ви вже зробили свій вибір!")
            return
            
        await role.night_action(target_id, callback.bot)
        await callback.answer("✅ Ціль обрана!")
        
        # Check if all night actions are completed
        all_actions_completed = True
        for role in game.players.values():
            if isinstance(role, (Mafia, Doctor, Detective)) and role.is_alive and not role.night_action_used:
                all_actions_completed = False
                break
                
        if all_actions_completed:
            # Cancel timer and end night phase immediately
            if chat_id in game_timers:
                game_timers[chat_id].cancel()
            await end_night_phase(game, callback.message, timeout=0)
            
    except Exception as e:
        logger.error(f"Error in kill action: {e}")
        await callback.answer("❌ Помилка при виборі цілі!")

@router.callback_query(F.data.startswith("heal_"))
async def handle_heal(callback: CallbackQuery):
    """Handle doctor's heal action."""
    try:
        chat_id = int(callback.data.split('_')[2])
        target_id = int(callback.data.split('_')[1])
        
        if chat_id not in active_games:
            await callback.answer("❌ Гра не знайдена!")
            return
            
        game = active_games[chat_id]
        player_id = callback.from_user.id
        
        if game.phase != "night":
            await callback.answer("❌ Зараз не нічна фаза!")
            return
            
        role = game.players.get(player_id)
        if not isinstance(role, Doctor):
            await callback.answer("❌ Ви не лікар!")
            return
            
        if role.night_action_used:
            await callback.answer("❌ Ви вже зробили свій вибір!")
            return
            
        if target_id == player_id and role.self_heals_remaining <= 0:
            await callback.answer("❌ Ви більше не можете лікувати себе!")
            return
            
        await role.night_action(target_id, callback.bot)
        await callback.answer("✅ Ви вилікували гравця!")
        
        # Check if all night actions are completed
        all_actions_completed = True
        for role in game.players.values():
            if isinstance(role, (Mafia, Doctor, Detective)) and role.is_alive and not role.night_action_used:
                all_actions_completed = False
                break
                
        if all_actions_completed:
            # Cancel timer and end night phase immediately
            if chat_id in game_timers:
                game_timers[chat_id].cancel()
            await end_night_phase(game, callback.message, timeout=0)
            
    except Exception as e:
        logger.error(f"Error in heal action: {e}")
        await callback.answer("❌ Помилка при виборі цілі!")

@router.callback_query(F.data.startswith("investigate_"))
async def handle_investigate(callback: CallbackQuery):
    """Handle detective's investigate action."""
    try:
        chat_id = int(callback.data.split('_')[2])
        target_id = int(callback.data.split('_')[1])
        
        if chat_id not in active_games:
            await callback.answer("❌ Гра не знайдена!")
            return
            
        game = active_games[chat_id]
        player_id = callback.from_user.id
        
        if game.phase != "night":
            await callback.answer("❌ Зараз не нічна фаза!")
            return
            
        role = game.players.get(player_id)
        if not isinstance(role, Detective):
            await callback.answer("❌ Ви не детектив!")
            return
            
        if role.night_action_used:
            await callback.answer("❌ Ви вже зробили свій вибір!")
            return
            
        await role.night_action(target_id, callback.bot)
        await callback.answer("✅ Ви почали розслідування!")
        
        # Check if all night actions are completed
        all_actions_completed = True
        for role in game.players.values():
            if isinstance(role, (Mafia, Doctor, Detective)) and role.is_alive and not role.night_action_used:
                all_actions_completed = False
                break
                
        if all_actions_completed:
            # Cancel timer and end night phase immediately
            if chat_id in game_timers:
                game_timers[chat_id].cancel()
            await end_night_phase(game, callback.message, timeout=0)
            
    except Exception as e:
        logger.error(f"Error in investigate action: {e}")
        await callback.answer("❌ Помилка при виборі цілі!")

@router.callback_query(F.data.startswith("vote_"))
async def handle_vote(callback: CallbackQuery):
    """Handle voting during day phase."""
    try:
        chat_id = int(callback.data.split('_')[2])
        target_id = int(callback.data.split('_')[1])
        
        if chat_id not in active_games:
            await callback.answer("❌ Гра не знайдена!")
            return
            
        game = active_games[chat_id]
        player_id = callback.from_user.id
        
        if game.phase != "day":
            await callback.answer("❌ Зараз не час для голосування!")
            return
            
        if player_id not in game.alive_players:
            await callback.answer("❌ Мертві не голосують!")
            return
            
        if target_id not in game.alive_players:
            await callback.answer("❌ Цей гравець мертвий!")
            return
            
        # Record the vote
        game.votes[player_id] = target_id
        await callback.answer("✅ Ваш голос зараховано!")
        
        # Check if everyone has voted
        if len(game.votes) == len(game.alive_players):
            # Cancel timer and end day phase immediately
            if chat_id in game_timers:
                game_timers[chat_id].cancel()
            await end_day_phase(game, callback.message, timeout=0)
            
    except Exception as e:
        logger.error(f"Error in voting: {e}")
        await callback.answer("❌ Помилка при голосуванні!")

async def end_day_phase(game: GameState, message: Message, timeout: int = 30):
    """End day phase and process voting results."""
    try:
        if timeout > 0:
            await asyncio.sleep(timeout)
        
        # Count votes
        vote_counts = {}
        for target_id in game.votes.values():
            vote_counts[target_id] = vote_counts.get(target_id, 0) + 1
        
        if not vote_counts:
            await message.bot.send_message(game.chat_id, "😕 Ніхто не проголосував. Ніхто не буде страчений.")
        else:
            # Find player with most votes
            max_votes = max(vote_counts.values())
            condemned = [pid for pid, votes in vote_counts.items() if votes == max_votes]
            
            if len(condemned) > 1:
                await message.bot.send_message(game.chat_id, "🤔 Голоси розділилися порівну. Ніхто не буде страчений.")
            else:
                condemned_id = condemned[0]
                game.kill_player(condemned_id)
                try:
                    condemned_name = (await message.bot.get_chat_member(game.chat_id, condemned_id)).user.first_name
                    await message.bot.send_message(game.chat_id, f"⚖️ За рішенням більшості, {condemned_name} був страчений!")
                except Exception as e:
                    logger.error(f"Failed to announce condemned player: {e}")
        
        # Check win conditions
        mafia_count = sum(1 for role in game.players.values() if isinstance(role, Mafia) and role.is_alive)
        civilian_count = sum(1 for role in game.players.values() if not isinstance(role, Mafia) and role.is_alive)
        
        if mafia_count == 0:
            await message.bot.send_message(game.chat_id, "🎉 Мирні жителі перемогли! Мафія знищена!")
            active_games.pop(message.chat.id, None)
            return
        elif mafia_count >= civilian_count:
            await message.bot.send_message(game.chat_id, "👻 Мафія перемогла! Місто в їхній владі!")
            active_games.pop(message.chat.id, None)
            return
        
        # Start next round
        game.round += 1
        game.phase = "night"
        game.votes.clear()
        
        # Start next night phase
        await handle_night_phase(game, message)
        
    except Exception as e:
        logger.error(f"Error ending day phase: {e}")
        await message.bot.send_message(game.chat_id, "❌ Помилка при завершенні дня.")
    finally:
        game_timers.pop(message.chat.id, None)
