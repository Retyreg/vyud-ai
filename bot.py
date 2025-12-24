import asyncio
import logging
import os
import toml
from pathlib import Path
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command
from aiogram.types import Message, BotCommand, BotCommandScopeDefault

# 1. Загрузка секретов из Streamlit
secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
if secrets_path.exists():
    secrets = toml.load(secrets_path)
    TOKEN = secrets.get("BOT_TOKEN")
    # Прокидываем остальные ключи в env, чтобы другие модули (logic, auth) их видели
    os.environ["OPENAI_API_KEY"] = secrets.get("OPENAI_API_KEY", "")
    os.environ["SUPABASE_URL"] = secrets.get("SUPABASE_URL", "")
    os.environ["SUPABASE_KEY"] = secrets.get("SUPABASE_KEY", "")
else:
    TOKEN = os.getenv("BOT_TOKEN")

# Проверка токена перед запуском
if not TOKEN:
    raise ValueError("ОШИБКА: BOT_TOKEN не найден в .streamlit/secrets.toml")

router = Router()

# Импортируем наши функции (уже после настройки env)
try:
    from auth import get_user_credits
except ImportError:
    def get_user_credits(email): return 5

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
        f"<b>Привет! Я твой AI-ассистент VYUD</b> 🚀\n\n"
        f"Я беру данные из твоих секретов и готов к работе.\n\n"
        f"⚡️ Твой баланс: <b>{credits} кредитов</b>\n\n"
        f"Отправь мне кружочек или PDF!"
    )
    await message.answer(welcome_text, parse_mode="HTML")

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user_email = f"{message.from_user.username}@telegram.io"
    credits = get_user_credits(user_email) or 0
    await message.answer(f"👤 Профиль: @{message.from_user.username}\n⚡️ Баланс: {credits} кредитов")

@router.message(F.video_note)
async def handle_video_note(message: Message):
    await message.answer("🎬 Вижу кружочек! Начинаю обработку через Whisper...")

async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await set_main_menu(bot)
    print("✅ Бот успешно запущен с ключами из secrets.toml")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())