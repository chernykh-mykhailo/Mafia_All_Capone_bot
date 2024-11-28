import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from game.handlers import router as game_router
from commands.start import router_start
from commands.buy import router_pay
from commands.construct_event import router_construct_event

# Get token from environment variable
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("No BOT_TOKEN environment variable set")

async def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize bot and dispatcher
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    
    # Set up command list
    commands = [
        BotCommand(command="start", description="Запуск бота "),
        BotCommand(command="help", description="Допомога "),
        BotCommand(command="play", description="Почати гру "),
        BotCommand(command="leave", description="Покинути гру "),
        BotCommand(command="force_start", description="Примусово почати гру (мінімум 3 гравці) "),
        BotCommand(command="rules", description="Показати правила гри "),
        BotCommand(command="buy_subscription", description="Купити/Продовжити Підписку "),
        BotCommand(command="stop_subscription", description="Призупинити підписку "),
        BotCommand(command="construct_event", description="Конструктор івентів ")
    ]
    
    await bot.set_my_commands(commands)
    
    # Register routers
    dp.include_routers(
        game_router,
        router_start,
        router_pay,
        router_construct_event
    )
    
    # Start polling
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logging.info("Bot stopped!")

if __name__ == "__main__":
    asyncio.run(main())
