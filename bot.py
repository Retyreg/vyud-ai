import asyncio
import logging
import os
import toml
from pathlib import Path
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message

# Импортируем нашу новую логику
import logic 
import auth

# --- НАСТРОЙКИ ---
secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
if secrets_path.exists():
    secrets = toml.load(secrets_path)
    TOKEN = secrets.get("TELEGRAM_BOT_TOKEN")
    # Устанавливаем ключи в переменные окружения, чтобы logic.py мог их найти, 
    # если они не передаются явно, или передаем их вручную (как сделано ниже)
    OPENAI_KEY = secrets.get("OPENAI_API_KEY", "")
    LLAMA_KEY = secrets.get("LLAMA_CLOUD_API_KEY", "")
else: 
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    OPENAI_KEY = os.getenv("OPENAI_API_KEY")
    LLAMA_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

router = Router()
bot = Bot(token=TOKEN)

# --- АДАПТЕР ФАЙЛОВ ---
class LocalFileWrapper:
    """
    Превращает локальный файл (путь) в объект, похожий на UploadedFile из Streamlit.
    Это нужно, чтобы logic.process_file_to_text могла с ним работать.
    """
    def __init__(self, path):
        self.name = path
        with open(path, "rb") as f:
            self._data = f.read()

    def getvalue(self):
        return self._data

# --- ОБРАБОТЧИКИ ---

@router.message(Command("start"))
async def start(m: Message): 
    await m.answer("👋 Привет! Я VYUD AI. Пришли мне файл видео-кружочек, (PDF/DOCX) или голосовое сообщение.")

@router.message(F.video_note | F.voice | F.audio | F.video | F.document)
async def handle_files(m: Message):
    # Создаем "виртуального" пользователя для базы данных
    user_email = f"{m.from_user.username or m.from_user.id}@telegram.vyud"
    
    # 1. Проверка баланса
    # Важно: auth.get_credits синхронная функция, но она быстрая (если база не тупит)
    # Для идеального асинхрона лучше тоже заворачивать в to_thread, но для MVP ок.
    if auth.get_credits(user_email) <= 0: 
        await m.answer("🚫 Недостаточно кредитов. Попросите админа пополнить баланс.")
        return
        
    msg = await m.answer("📥 Скачиваю файл...")
    
    # Определение ID файла
    if m.video_note: fid = m.video_note.file_id
    elif m.voice: fid = m.voice.file_id
    elif m.audio: fid = m.audio.file_id
    elif m.video: fid = m.video.file_id
    elif m.document: fid = m.document.file_id
    else: return

    # Формирование временного пути
    # Мы не знаем расширение заранее, aiogram поможет, но для простоты берем временное имя
    path = f"temp_bot_{m.from_user.id}_{fid}" 
    
    try:
        # Скачивание
        f_info = await bot.get_file(fid)
        # Получаем реальное расширение файла из Telegram
        ext = f_info.file_path.split('.')[-1]
        path = f"{path}.{ext}"
        
        await bot.download_file(f_info.file_path, path)
        
        # 2. Обработка (Транскрибация / Парсинг)
        await bot.edit_message_text("👂 Изучаю содержимое (🤖 AI работает на тебя. Чуть-чуть вашего терпения)...", m.chat.id, msg.message_id)
        
        # Создаем обертку для logic.py
        wrapped_file = LocalFileWrapper(path)
        
        # Запускаем тяжелую синхронную функцию в отдельном потоке
        text = await asyncio.to_thread(logic.process_file_to_text, wrapped_file, OPENAI_KEY, LLAMA_KEY)
        
        if not text:
            await bot.edit_message_text("❌ Не удалось извлечь текст.", m.chat.id, msg.message_id)
            return

        # 3. Генерация квиза
        await bot.edit_message_text("🧠 Придумываю вопросы и делаю тест/квиз ...", m.chat.id, msg.message_id)
        
        # Хардкодим параметры для бота (в Streamlit они в UI)
        quiz = await asyncio.to_thread(
            logic.generate_quiz_ai, 
            text=text, 
            count=5, 
            difficulty="Medium", 
            lang="Russian"
        )
        
        # 4. Списание средств и финал
        auth.deduct_credit(user_email, 1)
        await bot.delete_message(m.chat.id, msg.message_id)
        await m.answer("✅ Готово! Вот ваш тест/квиз:")

        # Отправка нативных опросов Telegram
        for q in quiz.questions:
            try:
                # Telegram имеет лимиты: вопрос < 300 символов, опция < 100
                await bot.send_poll(
                    chat_id=m.chat.id,
                    question=q.scenario[:299], 
                    options=[o[:99] for o in q.options], 
                    type='quiz', 
                    correct_option_id=q.correct_option_id,
                    explanation=q.explanation[:199] # Можно добавить объяснение (до 200 символов)
                )
                await asyncio.sleep(1) # Небольшая пауза, чтобы не спамить
            except Exception as e:
                logging.error(f"Ошибка отправки опроса: {e}")
                
    except Exception as e:
        await m.answer(f"❌ Произошла ошибка: {e}")
        logging.error(e)
    finally:
        # Удаляем временный файл
        if os.path.exists(path): 
            os.remove(path)

async def main():
    logging.basicConfig(level=logging.INFO)
    dp = Dispatcher()
    dp.include_router(router)
    
    # Удаляем вебхук, чтобы polling заработал сразу
    await bot.delete_webhook(drop_pending_updates=True)
    print("🤖 Бот VYUD AI запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__": 
    asyncio.run(main())