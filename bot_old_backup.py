import asyncio
import logging
import os
import toml
from pathlib import Path
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, BotCommand, BotCommandScopeDefault, InlineKeyboardMarkup, InlineKeyboardButton

# --- ИМПОРТ ЛОГИКИ ---
try:
    from logic import (
        transcribe_for_bot as transcribe_audio,
        generate_quiz_ai as generate_quiz_struct,
        process_file_to_text
    )
    from auth import get_user_credits as get_credits, deduct_credit
except ImportError as e:
    logging.error(f"CRITICAL IMPORT ERROR: {e}")
    def transcribe_audio(path): return "Error"
    def generate_quiz_struct(text, count, diff, lang): return None
    def process_file_to_text(file, api_key): return "Error"
    def get_credits(email): return 99
    def deduct_credit(email, n): pass

# --- КОНФИГУРАЦИЯ ---
secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
if secrets_path.exists():
    secrets = toml.load(secrets_path)
    TOKEN = secrets.get("TELEGRAM_BOT_TOKEN") or secrets.get("BOT_TOKEN")
    OPENAI_API_KEY = secrets.get("OPENAI_API_KEY", "")
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    os.environ["SUPABASE_URL"] = secrets.get("SUPABASE_URL", "")
    os.environ["SUPABASE_KEY"] = secrets.get("SUPABASE_KEY", "")
else:
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TOKEN: raise ValueError("🔴 BOT_TOKEN не найден!")
if not OPENAI_API_KEY: raise ValueError("🔴 OPENAI_API_KEY не найден!")

router = Router()
bot = Bot(token=TOKEN)

WEB_APP_URL = "https://app.vyud.online"
MAX_FILE_SIZE_MB = 50

async def set_main_menu(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command='/start', description='🚀 Начать'),
        BotCommand(command='/profile', description='⚡️ Баланс'),
        BotCommand(command='/help', description='❓ Помощь')
    ], scope=BotCommandScopeDefault())

def get_user_email(message: Message) -> str:
    username = message.from_user.username or f"user{message.from_user.id}"
    return f"{username}@telegram.io"

def create_web_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💻 Веб-версия VYUD", url=WEB_APP_URL)
    ]])

async def process_media_file(message: Message, file_id: str, file_name: str, is_audio: bool = False):
    user_email = get_user_email(message)
    credits = get_credits(user_email)
    
    if credits <= 0:
        await message.answer(
            "🚫 <b>Кредиты закончились!</b>\n\n"
            f"Пополните баланс на {WEB_APP_URL}",
            parse_mode="HTML",
            reply_markup=create_web_keyboard()
        )
        return

    status_msg = await message.answer(
        f"📥 Скачиваю {'аудио' if is_audio else 'видео'}...",
        parse_mode="HTML"
    )
    
    file_path = f"temp_{message.from_user.id}_{file_id[:8]}.{'mp3' if is_audio else 'mp4'}"

    try:
        file_info = await bot.get_file(file_id)
        file_size_mb = file_info.file_size / (1024 * 1024)
        
        if file_size_mb > MAX_FILE_SIZE_MB:
            await message.answer(
                f"❌ <b>Файл слишком большой!</b>\n\n"
                f"Размер: {file_size_mb:.1f} MB (макс. {MAX_FILE_SIZE_MB} MB)",
                parse_mode="HTML"
            )
            return
        
        await bot.download_file(file_info.file_path, file_path)
        
        await bot.edit_message_text(
            "👂 Распознаю речь...",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )
        transcript = await asyncio.to_thread(transcribe_audio, file_path)
        
        if not transcript or "Error" in transcript or len(transcript) < 50:
            await message.answer("❌ <b>Не удалось распознать речь</b>", parse_mode="HTML")
            return

        await bot.edit_message_text(
            "🧠 Создаю викторину...",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )
        quiz_data = await asyncio.to_thread(
            generate_quiz_struct,
            transcript, 5, "Medium", "Russian"
        )
        
        if not quiz_data or not quiz_data.questions:
            await message.answer("❌ <b>Не удалось создать вопросы</b>", parse_mode="HTML")
            return

        deduct_credit(user_email, 1)
        new_balance = get_credits(user_email)
        
        await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
        
        preview = transcript[:150] + "..." if len(transcript) > 150 else transcript
        await message.answer(
            f"✅ <b>Викторина готова!</b>\n\n"
            f"🗣 <i>\"{preview}\"</i>\n\n"
            f"📊 Вопросов: {len(quiz_data.questions)}\n"
            f"⚡️ Баланс: {new_balance}\n\n"
            f"👇 <b>Проверь себя!</b>",
            parse_mode="HTML",
            reply_markup=create_web_keyboard()
        )
        
        for i, q in enumerate(quiz_data.questions, 1):
            try:
                await bot.send_poll(
                    chat_id=message.chat.id,
                    question=f"{i}. {q.scenario[:250]}",
                    options=[opt[:95] for opt in q.options],
                    type='quiz',
                    correct_option_id=q.correct_option_id,
                    explanation=q.explanation[:195] if q.explanation else None,
                    is_anonymous=False
                )
                await asyncio.sleep(0.3)
            except Exception as e:
                logging.error(f"Poll error: {e}")

    except Exception as e:
        logging.error(f"Error: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:100]}", parse_mode="HTML")
    
    finally:
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass

async def process_document_file(message: Message, file_id: str, file_name: str):
    user_email = get_user_email(message)
    credits = get_credits(user_email)
    
    if credits <= 0:
        await message.answer(
            "🚫 <b>Кредиты закончились!</b>",
            parse_mode="HTML",
            reply_markup=create_web_keyboard()
        )
        return

    status_msg = await message.answer("📥 Загружаю документ...", parse_mode="HTML")
    file_path = f"temp_{message.from_user.id}_{file_id[:8]}_{file_name}"

    try:
        file_info = await bot.get_file(file_id)
        file_size_mb = file_info.file_size / (1024 * 1024)
        
        if file_size_mb > MAX_FILE_SIZE_MB:
            await message.answer(
                f"❌ <b>Файл слишком большой!</b>\n\nРазмер: {file_size_mb:.1f} MB",
                parse_mode="HTML"
            )
            return
        
        await bot.download_file(file_info.file_path, file_path)
        
        await bot.edit_message_text(
            "📖 Читаю документ...",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )
        
        class FileWrapper:
            def __init__(self, path, name):
                self.path = path
                self.name = name
            def read(self):
                with open(self.path, 'rb') as f:
                    return f.read()
            def seek(self, pos): pass
        
        file_obj = FileWrapper(file_path, file_name)
        text_content = await asyncio.to_thread(process_file_to_text, file_obj, OPENAI_API_KEY)
        
        if not text_content or "Error" in text_content or len(text_content) < 100:
            await message.answer("❌ <b>Не удалось извлечь текст</b>", parse_mode="HTML")
            return

        await bot.edit_message_text(
            "🧠 Создаю викторину...",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )
        quiz_data = await asyncio.to_thread(generate_quiz_struct, text_content, 5, "Medium", "Russian")
        
        if not quiz_data or not quiz_data.questions:
            await message.answer("❌ <b>Не удалось создать вопросы</b>", parse_mode="HTML")
            return

        deduct_credit(user_email, 1)
        new_balance = get_credits(user_email)
        
        await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
        
        await message.answer(
            f"✅ <b>Викторина готова!</b>\n\n"
            f"📄 {file_name}\n"
            f"📊 Вопросов: {len(quiz_data.questions)}\n"
            f"⚡️ Баланс: {new_balance}\n\n"
            f"👇 <b>Проверь себя!</b>",
            parse_mode="HTML",
            reply_markup=create_web_keyboard()
        )
        
        for i, q in enumerate(quiz_data.questions, 1):
            try:
                await bot.send_poll(
                    chat_id=message.chat.id,
                    question=f"{i}. {q.scenario[:250]}",
                    options=[opt[:95] for opt in q.options],
                    type='quiz',
                    correct_option_id=q.correct_option_id,
                    explanation=q.explanation[:195] if q.explanation else None,
                    is_anonymous=False
                )
                await asyncio.sleep(0.3)
            except Exception as e:
                logging.error(f"Poll error: {e}")

    except Exception as e:
        logging.error(f"Error: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:100]}", parse_mode="HTML")
    
    finally:
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_email = get_user_email(message)
    credits = get_credits(user_email)
    
    await message.answer(
        f"👋 <b>Привет! Я VYUD AI.</b>\n\n"
        f"📚 Превращаю файлы в викторины!\n\n"
        f"<b>Что я умею:</b>\n"
        f"• 🎤 Кружочки и аудио\n"
        f"• 🎥 Видео\n"
        f"• 📄 PDF, DOCX, PPTX\n\n"
        f"⚡️ Баланс: <b>{credits}</b>\n\n"
        f"👇 Отправь файл!",
        parse_mode="HTML",
        reply_markup=create_web_keyboard()
    )

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user_email = get_user_email(message)
    credits = get_credits(user_email)
    username = message.from_user.username or f"User {message.from_user.id}"
    
    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"@{username}\n"
        f"⚡️ Кредиты: <b>{credits}</b>\n\n"
        f"💳 Пополнить:",
        parse_mode="HTML",
        reply_markup=create_web_keyboard()
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "❓ <b>Помощь</b>\n\n"
        "<b>Форматы:</b>\n"
        "• 🎤 Audio: MP3, WAV, OGG\n"
        "• 🎥 Video: MP4, MOV\n"
        "• 📄 Docs: PDF, DOCX, PPTX\n\n"
        "<b>Лимиты:</b>\n"
        "• Макс: 50 MB\n"
        "• 1 кредит = 1 тест\n\n"
        "💻 Больше на сайте:",
        parse_mode="HTML",
        reply_markup=create_web_keyboard()
    )

@router.message(F.video_note)
async def handle_video_note(message: Message):
    await process_media_file(message, message.video_note.file_id, 
                            f"video_note.mp4", is_audio=False)

@router.message(F.voice)
async def handle_voice(message: Message):
    await process_media_file(message, message.voice.file_id, 
                            f"voice.ogg", is_audio=True)

@router.message(F.audio)
async def handle_audio(message: Message):
    await process_media_file(message, message.audio.file_id, 
                            message.audio.file_name or "audio.mp3", is_audio=True)

@router.message(F.video)
async def handle_video(message: Message):
    await process_media_file(message, message.video.file_id, 
                            message.video.file_name or "video.mp4", is_audio=False)

@router.message(F.document)
async def handle_document(message: Message):
    doc = message.document
    file_name = doc.file_name.lower()
    
    supported = ('.pdf', '.docx', '.pptx', '.txt')
    if not any(file_name.endswith(ext) for ext in supported):
        await message.answer(
            "❌ <b>Неподдерживаемый формат</b>\n\nПоддерживаются: PDF, DOCX, PPTX",
            parse_mode="HTML"
        )
        return
    
    await process_document_file(message, doc.file_id, doc.file_name)

@router.message()
async def handle_other(message: Message):
    await message.answer(
        "🤔 Отправьте файл для создания теста!\n\n/help — справка",
        parse_mode="HTML"
    )

async def main():
    logging.basicConfig(level=logging.INFO)
    dp = Dispatcher()
    dp.include_router(router)
    await set_main_menu(bot)
    logging.info("🤖 Bot started!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
