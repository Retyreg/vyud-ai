import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command
from aiogram.types import Message, BotCommand, BotCommandScopeDefault

# Пытаемся импортировать наши модули
try:
    from auth import get_user_credits
except ImportError:
    def get_user_credits(email): return 5  # Заглушка, если auth.py не виден

# Инициализация
# ТОКЕН: Лучше прописать в .env или заменить тут на твой "строкой"
TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_ТОКЕН_ЗДЕСЬ") 
router = Router()

async def set_main_menu(bot: Bot):
    main_menu_commands = [
        BotCommand(command='/start', description='Запустить магию VYUD 🚀'),
        BotCommand(command='/profile', description='Мои кредиты ⚡️'),
        BotCommand(command='/help', description='Как это работает? 📖')
    ]
    await bot.set_my_commands(commands=main_menu_commands, scope=BotCommandScopeDefault())

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_email = f"{message.from_user.username}@telegram.io"
    credits = get_user_credits(user_email) or 5
    
    welcome_text = (
        f"<b>Привет! Я твой AI-ассистент в @VyudAiBot</b> 🚀\n\n"
        f"Я превращаю видео-кружочки, аудио и PDF в обучающие тесты за секунды.\n\n"
        f"⚡️ Твой баланс: <b>{credits} кредитов</b>\n\n"
        f"<i>Просто запиши видео-сообщение (кружок), чтобы начать!</i>"
    )
    await message.answer(welcome_text, parse_mode="HTML")

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user_email = f"{message.from_user.username}@telegram.io"
    credits = get_user_credits(user_email) or 0
    await message.answer(f"👤 Профиль: @{message.from_user.username}\n⚡️ Баланс: {credits} кредитов")

@router.message(F.video_note)
async def handle_video_note(message: Message):
    await message.answer("🎬 Вижу кружок! Начинаю обработку...")

async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    # Устанавливаем меню перед стартом
    await set_main_menu(bot)
    
    print("Бот @VyudAiBot запущен через VENV!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())