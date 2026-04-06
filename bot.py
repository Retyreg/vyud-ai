import asyncio
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# Импортируем нашу логику
import logic 
import auth

# --- НАСТРОЙКИ ---
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
LLAMA_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

router = Router()
bot = Bot(token=TOKEN)

# --- АДАПТЕР ФАЙЛОВ ---
class LocalFileWrapper:
    def __init__(self, path):
        self.name = path
        with open(path, "rb") as f:
            self._data = f.read()

    def getvalue(self):
        return self._data

# --- ОБРАБОТЧИКИ ---

@router.message(Command("start"))
async def start(m: Message): 
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Канал экосистемы VYUD AI", url="https://t.me/vyud_ai")]
    ])
    await m.answer(
        "👋 Привет! Я VYUD AI. \n\n"
        "Пришли мне файл (PDF/DOCX), голосовое, видео-кружочек или аудио, и я превращу его в интерактивный тест!\n\n"
        "Следите за всеми нашими проектами в официальном канале:",
        reply_markup=keyboard
    )

@router.message(F.video_note | F.voice | F.audio | F.video | F.document)
async def handle_files(m: Message):
    user_email = f"{m.from_user.username or m.from_user.id}@telegram.vyud"
    
    # 1. Проверка баланса
    if auth.get_credits(user_email) <= 0: 
        await m.answer("🚫 Недостаточно кредитов. Попросите админа пополнить баланс.")
        return
        
    msg = await m.answer("📥 Скачиваю файл...")
    
    # Определение ID
    if m.video_note: fid = m.video_note.file_id
    elif m.voice: fid = m.voice.file_id
    elif m.audio: fid = m.audio.file_id
    elif m.video: fid = m.video.file_id
    elif m.document: fid = m.document.file_id
    else: return

    path = f"temp_bot_{m.from_user.id}_{fid}" 
    
    try:
        f_info = await bot.get_file(fid)
        ext = f_info.file_path.split('.')[-1]
        path = f"{path}.{ext}"
        
        await bot.download_file(f_info.file_path, path)
        
        # 2. Обработка (Используем именованные аргументы!)
        await bot.edit_message_text(
            text="👂 Изучаю содержимое ...", 
            chat_id=m.chat.id, 
            message_id=msg.message_id
        )
        
        wrapped_file = LocalFileWrapper(path)
        
        # Запускаем логику в потоке
        text = await asyncio.to_thread(logic.process_file_to_text, wrapped_file, OPENAI_KEY, LLAMA_KEY)
        
        if not text:
            await bot.edit_message_text(
                text="❌ Не удалось извлечь текст.", 
                chat_id=m.chat.id, 
                message_id=msg.message_id
            )
            return

        # 3. Генерация квиза
        await bot.edit_message_text(
            text="🧠 Придумываю вопросы ...", 
            chat_id=m.chat.id, 
            message_id=msg.message_id
        )
        
        quiz = await asyncio.to_thread(
            logic.generate_quiz_ai, 
            text=text, 
            count=5, 
            difficulty="Medium", 
            lang="Russian"
        )
        
        # 4. Финал
        auth.deduct_credit(user_email, 1)
        await bot.delete_message(chat_id=m.chat.id, message_id=msg.message_id)
        await m.answer("✅ Готово! Вот ваш тест:")

        for q in quiz.questions:
            try:
                await bot.send_poll(
                    chat_id=m.chat.id,
                    question=q.scenario[:299], 
                    options=[o[:99] for o in q.options], 
                    type='quiz', 
                    correct_option_id=q.correct_option_id,
                    explanation=q.explanation[:199]
                )
                await asyncio.sleep(1)
            except Exception as e:
                logging.error(f"Poll error: {e}")
                
    except Exception as e:
        await m.answer(f"❌ Произошла ошибка: {e}")
        logging.error(e)
    finally:
        if os.path.exists(path): 
            os.remove(path)

async def main():
    logging.basicConfig(level=logging.INFO)
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    print("🤖 Бот VYUD AI запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__": 
    asyncio.run(main())