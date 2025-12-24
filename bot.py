import asyncio
import logging
import os
import toml
from pathlib import Path
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, BotCommand, BotCommandScopeDefault, FSInputFile

# --- НАШИ МОДУЛИ ---
# Импортируем логику. Убедись, что в logic.py есть эти функции!
# Если они называются иначе, поправь импорт ниже.
try:
    from logic import transcribe_audio, generate_quiz_from_text
    from auth import get_user_credits, deduct_credits  # Добавил списание кредитов
except ImportError as e:
    print(f"⚠️ Ошибка импорта модулей: {e}")
    # Заглушки для локального теста, если файлов нет
    def transcribe_audio(path): return "Тестовая транскрипция: Это видео про Python."
    def generate_quiz_from_text(text): return "1. Вопрос по Python? (A) Да (B) Нет"
    def get_user_credits(email): return 999
    def deduct_credits(email, amount): pass

# 1. Загрузка секретов из Streamlit
secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
if secrets_path.exists():
    secrets = toml.load(secrets_path)
    TOKEN = secrets.get("BOT_TOKEN")
    
    # Прокидываем ключи в Environment, чтобы logic.py и auth.py их видели
    os.environ["OPENAI_API_KEY"] = secrets.get("OPENAI_API_KEY", "")
    os.environ["SUPABASE_URL"] = secrets.get("SUPABASE_URL", "")
    os.environ["SUPABASE_KEY"] = secrets.get("SUPABASE_KEY", "")
else:
    # Fallback для сервера, если переменные уже в ENV
    TOKEN = os.getenv("BOT_TOKEN")

# Проверка токена
if not TOKEN:
    raise ValueError("🔴 ОШИБКА: BOT_TOKEN не найден! Проверь .streamlit/secrets.toml")

router = Router()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def set_main_menu(bot: Bot):
    main_menu_commands = [
        BotCommand(command='/start', description='Запустить магию VYUD 🚀'),
        BotCommand(command='/profile', description='Мои кредиты ⚡️'),
        BotCommand(command='/help', description='Инструкция 📖')
    ]
    await bot.set_my_commands(commands=main_menu_commands, scope=BotCommandScopeDefault())

# --- ХЕНДЛЕРЫ ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_email = f"{message.from_user.username}@telegram.io"
    credits = get_user_credits(user_email)
    
    welcome_text = (
        f"<b>Привет! Я твой AI-ассистент VYUD</b> 🚀\n\n"
        f"Я превращаю видео-кружочки и аудио в готовые тесты за секунды.\n\n"
        f"⚡️ Твой баланс: <b>{credits} кредитов</b>\n\n"
        f"🎥 <b>Просто перешли мне видео-сообщение (кружочек)!</b>"
    )
    await message.answer(welcome_text, parse_mode="HTML")

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user_email = f"{message.from_user.username}@telegram.io"
    credits = get_user_credits(user_email)
    await message.answer(f"👤 Профиль: @{message.from_user.username}\n⚡️ Баланс: {credits} кредитов")

@router.message(F.video_note)
async def handle_video_note(message: Message, bot: Bot):
    user_email = f"{message.from_user.username}@telegram.io"
    
    # 1. Проверка баланса
    credits = get_user_credits(user_email)
    if credits <= 0:
        await message.answer("🚫 Недостаточно кредитов! Пополните баланс.")
        return

    status_msg = await message.answer("🎬 Вижу кружочек! Скачиваю...")
    
    # Временный файл
    file_id = message.video_note.file_id
    file_info = await bot.get_file(file_id)
    file_path = f"temp_{message.from_user.id}_{file_id}.mp4"

    try:
        # 2. Скачивание
        await bot.download_file(file_info.file_path, file_path)
        
        await bot.edit_message_text("👂 Слушаю (Whisper)...", chat_id=message.chat.id, message_id=status_msg.message_id)
        
        # 3. Транскрибация (в отдельном потоке, чтобы не блочить бота)
        # В logic.py должна быть функция transcribe_audio(file_path)
        transcript = await asyncio.to_thread(transcribe_audio, file_path)
        
        await bot.edit_message_text("🧠 Генерирую тест (GPT-4)...", chat_id=message.chat.id, message_id=status_msg.message_id)
        
        # 4. Генерация теста
        # В logic.py должна быть функция generate_quiz_from_text(text)
        quiz_content = await asyncio.to_thread(generate_quiz_from_text, transcript)
        
        # 5. Списание кредита
        deduct_credits(user_email, 1)
        
        # 6. Отправка результата
        # Для MVP просто отправляем текст. В будущем можно генерировать PDF или ссылку на Web App.
        response_text = (
            f"✅ <b>Готово!</b>\n\n"
            f"📝 <b>Транскрипция (начало):</b>\n<i>{transcript[:100]}...</i>\n\n"
            f"🎯 <b>Тест:</b>\n{quiz_content}\n\n"
            f"➖ Списан 1 кредит."
        )
        
        await message.answer(response_text, parse_mode="HTML")

    except Exception as e:
        logging.error(f"Error processing video note: {e}")
        await message.answer(f"❌ Произошла ошибка при обработке: {str(e)}")
    
    finally:
        # 7. Уборка мусора
        if os.path.exists(file_path):
            os.remove(file_path)

# --- ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await set_main_menu(bot)
    
    print("✅ Бот VYUD успешно запущен!")
    print("waiting for messages...")
    
    # Удаляем вебхуки, если были, и запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())