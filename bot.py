import asyncio
import logging
import os
import sys
import toml

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile

import logic
import auth

# --- БЕЗОПАСНАЯ ЗАГРУЗКА КЛЮЧЕЙ ---
try:
    secrets = toml.load(".streamlit/secrets.toml")
    
    BOT_TOKEN = secrets.get("TELEGRAM_BOT_TOKEN")
    
    # Передаем ключи в окружение для logic.py
    os.environ["OPENAI_API_KEY"] = secrets.get("OPENAI_API_KEY", "")
    os.environ["LLAMA_CLOUD_API_KEY"] = secrets.get("LLAMA_CLOUD_API_KEY", "")
    
    if not BOT_TOKEN:
        raise ValueError("Токен бота не найден в secrets.toml!")
        
except Exception as e:
    print(f"❌ Ошибка загрузки ключей: {e}")
    sys.exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- БАЗА ДАННЫХ ---
def get_user_credits(telegram_id):
    fake_email = f"tg_{telegram_id}@vyud.bot"
    try:
        res = auth.supabase.table('users_credits').select("*").eq('email', fake_email).execute()
        if not res.data:
            auth.supabase.table('users_credits').insert({'email': fake_email, 'credits': 3}).execute()
            return 3
        return res.data[0]['credits']
    except Exception as e:
        logging.error(f"DB Error: {e}")
        return 0

def deduct_credit_bot(telegram_id):
    fake_email = f"tg_{telegram_id}@vyud.bot"
    current = get_user_credits(telegram_id)
    if current > 0:
        auth.supabase.table('users_credits').update({'credits': current - 1}).eq('email', fake_email).execute()
        return True
    return False

# --- ОБРАБОТЧИКИ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    credits = get_user_credits(message.from_user.id)
    await message.answer(
        f"👋 Привет! Я Vyud AI Bot.\n"
        f"Кредиты: **{credits}**.\n"
        f"Отправь мне **видео-кружочек**!"
    )

@dp.message(F.video_note | F.video)
async def handle_video(message: types.Message):
    user_id = message.from_user.id
    if get_user_credits(user_id) <= 0:
        await message.answer("⚠️ Кредиты закончились!")
        return

    status_msg = await message.answer("⏳ Скачиваю видео...")
    file_path = f"temp_{user_id}.mp4"

    try:
        if message.video_note:
            file_id = message.video_note.file_id
        else:
            file_id = message.video.file_id

        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, file_path)
        
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            
        class MockFile:
            def __init__(self, name, data):
                self.name = name
                self._data = data
            def getvalue(self): return self._data

        mock_file = MockFile("video.mp4", file_bytes)

        await status_msg.edit_text("🎧 Распознаю речь...")
        text = logic.process_file_to_text(mock_file, os.environ["OPENAI_API_KEY"], os.environ["LLAMA_CLOUD_API_KEY"])
        
        if not text:
            await status_msg.edit_text("❌ Речь не распознана.")
            return

        await status_msg.edit_text("🧠 Генерирую тест...")
        quiz = logic.generate_quiz_ai(text, count=1, difficulty="Medium", lang="Russian")
        
        if quiz and quiz.questions:
            q = quiz.questions[0]
            deduct_credit_bot(user_id)
            await message.answer_poll(
                question=q.scenario[:300],
                options=[opt[:100] for opt in q.options],
                type="quiz",
                correct_option_id=q.correct_option_id,
                explanation=q.explanation[:200],
                is_anonymous=False
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Ошибка генерации.")

    except Exception as e:
        await status_msg.edit_text(f"Ошибка: {e}")
        logging.error(e)
    finally:
        if os.path.exists(file_path): os.remove(file_path)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
