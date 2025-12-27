import asyncio
import logging
import os
import toml
from pathlib import Path
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, BotCommand, BotCommandScopeDefault

# --- ИМПОРТ ЛОГИКИ ---
try:
    from logic import transcribe_audio, generate_quiz_struct
    # [FIX] Исправил названия функций как в auth.py
    from auth import get_credits, deduct_credit 
except ImportError as e:
    logging.error(f"CRITICAL IMPORT ERROR: {e}")
    # Заглушки (чтобы бот не упал сразу, но работать не будет)
    def transcribe_audio(path): return "Error"
    def generate_quiz_struct(text): return None
    def get_credits(email): return 99
    def deduct_credit(email, n): pass

# --- КОНФИГУРАЦИЯ ---
secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
if secrets_path.exists():
    secrets = toml.load(secrets_path)
    TOKEN = secrets.get("TELEGRAM_BOT_TOKEN") # [CHECK] Проверь имя ключа в secrets.toml!
    os.environ["OPENAI_API_KEY"] = secrets.get("OPENAI_API_KEY", "")
    os.environ["SUPABASE_URL"] = secrets.get("SUPABASE_URL", "")
    os.environ["SUPABASE_KEY"] = secrets.get("SUPABASE_KEY", "")
else:
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN: 
    # Fallback если ключи названы иначе (обычно BOT_TOKEN или TELEGRAM_BOT_TOKEN)
    TOKEN = secrets.get("BOT_TOKEN") 

if not TOKEN: raise ValueError("🔴 BOT_TOKEN не найден!")

router = Router()

# --- МЕНЮ ---
async def set_main_menu(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command='/start', description='Начать 🚀'),
        BotCommand(command='/profile', description='Баланс ⚡️')
    ], scope=BotCommandScopeDefault())

# --- ХЕНДЛЕРЫ ---
@router.message(Command("start"))
async def cmd_start(message: Message):
    # [FIX] Используем get_credits
    credits = get_credits(f"{message.from_user.username}@telegram.io")
    await message.answer(
        f"👋 <b>Привет! Я VYUD AI.</b>\n\n"
        f"Кидай мне кружочек — я сделаю из него <b>интерактивную викторину!</b>\n"
        f"⚡️ Баланс: {credits}", parse_mode="HTML"
    )

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    credits = get_credits(f"{message.from_user.username}@telegram.io")
    await message.answer(f"👤 @{message.from_user.username}\n⚡️ {credits} кредитов")

@router.message(F.video_note)
async def handle_video_note(message: Message, bot: Bot):
    user_email = f"{message.from_user.username}@telegram.io"
    
    # [FIX] Проверка баланса
    if get_credits(user_email) <= 0:
        await message.answer("🚫 Кредиты закончились! Пополните баланс.")
        return

    status_msg = await message.answer("📥 Скачиваю кружочек...")
    file_id = message.video_note.file_id
    file_path = f"temp_{message.from_user.id}_{file_id}.mp4"

    try:
        # 1. Скачивание
        file_info = await bot.get_file(file_id)
        await bot.download_file(file_info.file_path, file_path)
        
        # 2. Транскрибация (в потоке)
        await bot.edit_message_text("👂 Слушаю (Whisper)...", chat_id=message.chat.id, message_id=status_msg.message_id)
        transcript = await asyncio.to_thread(transcribe_audio, file_path)
        
        if not transcript or "Error" in transcript:
            await message.answer("❌ Не слышу речи или файл поврежден.")
            return

        # 3. Генерация (в потоке)
        await bot.edit_message_text("🧠 Генерирую викторину...", chat_id=message.chat.id, message_id=status_msg.message_id)
        quiz_data = await asyncio.to_thread(generate_quiz_struct, transcript)
        
        if not quiz_data or not quiz_data.questions:
            await message.answer("❌ Не удалось придумать вопросы по этому тексту.")
            return

        # 4. Результат и списание
        # [FIX] Используем deduct_credit
        deduct_credit(user_email, 1)
        
        await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
        
        # Обрезаем превью текста для красоты
        preview_text = transcript[:200] + "..." if len(transcript) > 200 else transcript
        
        await message.answer(
            f"✅ <b>Готово!</b>\n\n"
            f"🗣 <i>\"{preview_text}\"</i>\n\n"
            f"👇 <b>А теперь проверь себя!</b>",
            parse_mode="HTML"
        )
        
        # 5. ОТПРАВКА POLLS
        for q in quiz_data.questions:
            try:
                # Telegram API лимиты: Question < 300 chars, Option < 100 chars
                q_text = q.scenario[:299]
                q_opts = [opt[:99] for opt in q.options]
                q_expl = q.explanation[:199]
                
                await bot.send_poll(
                    chat_id=message.chat.id,
                    question=q_text,
                    options=q_opts,
                    type='quiz',
                    correct_option_id=q.correct_option_id,
                    explanation=q_expl,
                    is_anonymous=False
                )
                await asyncio.sleep(0.5) 
            except Exception as e:
                logging.error(f"Poll Error: {e}")

    except Exception as e:
        logging.error(f"Global Error: {e}")
        await message.answer("❌ Произошла ошибка на сервере.")
    
    finally:
        if os.path.exists(file_path): 
            try: os.remove(file_path)
            except: pass

async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await set_main_menu(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())