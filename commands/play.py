from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from game.handlers import router as game_router

router_play = Router()

@router_play.message(Command("play"))
async def check_permissions(message: Message):
    if message.chat.type in ["group", "supergroup"]:
        # Get bot member info
        bot_member = await message.bot.get_chat_member(message.chat.id, message.bot.id)
        
        # Check if bot is admin and has required permissions
        if not bot_member.can_delete_messages or not bot_member.can_pin_messages:
            await message.answer(
                "⚠️ Для початку гри боту потрібні права адміністратора з такими дозволами:\n"
                "• Видалення повідомлень\n"
                "• Прикріплення повідомлень\n\n"
                "Будь ласка, надайте необхідні права та спробуйте знову."
            )
            return
        
        # If bot has permissions, proceed with game router
        await game_router.message(Command("play"))(message)
    else:
        await message.answer("Гра доступна тільки в групових чатах!")