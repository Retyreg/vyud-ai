import asyncio
import logging
import os
import toml
from pathlib import Path
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, BotCommand, BotCommandScopeDefault

# --- ИМПОРТ ЛОГИКИ И AUTH ---
# Оборачиваем в try-except, чтобы видеть понятную ошибку, если имена функций отличаются
try:
    from logic import transcribe_audio, generate_quiz_from_text
    from auth import get_user_credits, deduct_credits
except ImportError as e:
    logging.error(f"CRITICAL: Ошибка импорта модулей! Проверь названия функций в logic.py. Детали: {e}")
    # Заглушки, чтобы бот не упал при старте, но сообщил об ошибке
    def transcribe_audio(path): return "SYSTEM ERROR: Logic module not found."
    def generate_quiz_from_text(text): return "SYSTEM ERROR: Logic module not found."
    def get_user_credits(email): return 0
    def deduct_credits(email, n): pass

# --- КОНФИГУРАЦИЯ ---
secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
if secrets_path.exists():
    secrets = toml.load(secrets_path)
    TOKEN = secrets.get("BOT_TOKEN")
    # Прокидываем ключи в ENV для logic.py
    os.environ["OPENAI_API_KEY"] = secrets.get("OPENAI_API_KEY", "")
    os.environ["SUPABASE_URL"] = secrets.get("SUPABASE_URL", "")
    os.environ["SUPABASE_KEY"] = secrets.get("SUPABASE_KEY", "")
else:
    TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("🔴 ОШИБКА: BOT_TOKEN не найден! Проверь .streamlit/secrets.toml")

router = Router()

# --- МЕНЮ БОТА ---
async def set_main_menu(bot: Bot):
    main_menu_commands = [
        BotCommand(command='/start', description='Запустить магию 🚀'),
        BotCommand(command='/profile', description='Баланс ⚡️'),
        BotCommand(command='/help', description='Помощь 📖')
    ]
    await bot.set_my_commands(commands=main_menu_commands, scope=BotCommandScopeDefault())

# --- ХЕНДЛЕРЫ (ОБРАБОТЧИКИ) ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_email = f"{message.from_user.username}@telegram.io"
    credits = get_user_credits(user_email)
    
    text = (
        f"<b>Привет! Я VYUD AI.</b> 🚀\n\n"
        f"Я превращаю твои видео-кружочки в готовые тесты.\n"
        f"⚡️ Твой баланс: <b>{credits} кредитов</b>\n\n"
        f"👇 <b>Запиши или перешли мне видео-кружочек, чтобы начать!</b>"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user_email = f"{message.from_user.username}@telegram.io"
    credits = get_user_credits(user_email)
    await message.answer(f"👤 Пользователь: @{message.from_user.username}\n⚡️ Баланс: {credits} кредитов")

@router.message(F.video_note)
async def handle_video_note(message: Message, bot: Bot):
    user_email = f"{message.from_user.username}@telegram.io"
    
    # 1. Проверяем кредиты
    credits = get_user_credits(user_email)
    if credits <= 0:
        await message.answer("🚫 Упс! Кредиты закончились. Пополните баланс.")
        return

    # Сообщение о статусе
    status_msg = await message.answer("📥 Скачиваю кружочек...")
    
    # Путь для временного файла
    file_id = message.video_note.file_id
    file_info = await bot.get_file(file_id)
    file_path = f"temp_{message.from_user.id}_{file_id}.mp4"

    try:
        # 2. Скачиваем файл
        await bot.download_file(file_info.file_path, file_path)
        
        # 3. Транскрибация (Whisper)
        await bot.edit_message_text("👂 Слушаю и разбираю речь (Whisper)...", chat_id=message.chat.id, message_id=status_msg.message_id)
        transcript = await asyncio.to_thread(transcribe_audio, file_path)
        
        if "SYSTEM ERROR" in transcript:
             raise ImportError("Logic module function failed.")

        # 4. Генерация теста (GPT)
        await bot.edit_message_text("🧠 Создаю вопросы и ответы (GPT-4)...", chat_id=message.chat.id, message_id=status_msg.message_id)
        quiz_content = await asyncio.to_thread(generate_quiz_from_text, transcript)
        
        # 5. Списываем кредит
        deduct_credits(user_email, 1)
        
        # 6. Отправляем результат
        result_text = (
            f"✅ <b>Готово!</b>\n\n"
            f"🗣 <b>О чем речь:</b>\n<i>{transcript[:150]}...</i>\n\n"
            f"📝 <b>Твой Тест:</b>\n{quiz_content}\n\n"
            f"➖ Списан 1 кредит. Осталось: {credits - 1}"
        )
        await message.answer(result_text, parse_mode="HTML")

    except Exception as e:
        logging.error(f"Error: {e}")
        await message.answer(f"❌ Что-то пошло не так: {e}")
    
    finally:
        # 7. Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)

# --- ТОЧКА ВХОДА ---
async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    await set_main_menu(bot)
    
    print("✅ Бот VYUD запущен! Жду кружочки...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())