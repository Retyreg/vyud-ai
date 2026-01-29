import asyncio
import logging
import os
import toml
from pathlib import Path
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, BotCommand, BotCommandScopeDefault, InlineKeyboardMarkup, InlineKeyboardButton

try:
    from logic import transcribe_for_bot as transcribe_audio, generate_quiz_ai as generate_quiz_struct, process_file_to_text_bot as process_file_to_text
    from auth import get_user_credits as get_credits, deduct_credit, save_quiz, get_user_quizzes
except ImportError as e:
    logging.error(f"CRITICAL IMPORT ERROR: {e}")
    def transcribe_audio(path): return "Error"
    def generate_quiz_struct(text, count, diff, lang): return None
    def process_file_to_text(file, api_key): return "Error"
    def get_credits(email): return 99
    def deduct_credit(email, n): pass
    def save_quiz(email, title, questions, hints): return "test123"
    def get_user_quizzes(email): return []

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

if not TOKEN: raise ValueError("BOT_TOKEN not found")
if not OPENAI_API_KEY: raise ValueError("OPENAI_API_KEY not found")

router = Router()
bot = Bot(token=TOKEN)
WEB_APP_URL = "https://app.vyud.online"
MAX_FILE_SIZE_MB = 20

async def set_main_menu(bot: Bot):
    await bot.set_my_commands([BotCommand(command='/start', description='Start'), BotCommand(command='/profile', description='Profile'), BotCommand(command='/mytests', description='My tests'), BotCommand(command='/help', description='Help')], scope=BotCommandScopeDefault())

def get_user_email(message: Message) -> str:
    username = message.from_user.username or f"user{message.from_user.id}"
    return f"{username}@telegram.io"

def create_web_keyboard(test_id: str = None) -> InlineKeyboardMarkup:
    buttons = []
    if test_id:
        buttons.append([InlineKeyboardButton(text="Open test", url=f"{WEB_APP_URL}/?test={test_id}")])
    buttons.append([InlineKeyboardButton(text="Web version", url=WEB_APP_URL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def process_media_background(message: Message, file_id: str, file_name: str, is_audio: bool = False):
    user_email = get_user_email(message)
    file_path = f"temp_{message.from_user.id}_{file_id[:8]}.{'mp3' if is_audio else 'mp4'}"
    status_msg = await message.answer("File accepted! Processing in background. You can send more files.", parse_mode="HTML")
    try:
        await status_msg.edit_text("Downloading...", parse_mode="HTML")
        file_info = await bot.get_file(file_id)
        await bot.download_file(file_info.file_path, file_path)
        await status_msg.edit_text("Transcribing...", parse_mode="HTML")
        transcript = await asyncio.to_thread(transcribe_audio, file_path)
        if not transcript or len(transcript) < 50:
            await status_msg.edit_text("Failed to transcribe", parse_mode="HTML")
            return
        await status_msg.edit_text("Generating quiz...", parse_mode="HTML")
        quiz_data = await asyncio.to_thread(generate_quiz_struct, transcript, 5, "Medium", "Russian")
        if not quiz_data or not quiz_data.questions:
            await status_msg.edit_text("Failed to create quiz", parse_mode="HTML")
            return
        test_title = f"Test from {'audio' if is_audio else 'video'}"
        questions_json = [{"scenario": q.scenario, "options": q.options, "correct_option_id": q.correct_option_id, "explanation": q.explanation} for q in quiz_data.questions]
        test_id = await asyncio.to_thread(save_quiz, user_email, test_title, questions_json, getattr(quiz_data, "hints", []))
        await asyncio.to_thread(deduct_credit, user_email, 1)
        new_balance = await asyncio.to_thread(get_credits, user_email)
        await status_msg.delete()
        await message.answer(f"Quiz ready! Balance: {new_balance}", parse_mode="HTML", reply_markup=create_web_keyboard(test_id))
        for i, q in enumerate(quiz_data.questions, 1):
            try:
                await bot.send_poll(chat_id=message.chat.id, question=f"{i}. {q.scenario[:250]}", options=[opt[:95] for opt in q.options], type='quiz', correct_option_id=q.correct_option_id, explanation=q.explanation[:195] if q.explanation else None, is_anonymous=False)
                await asyncio.sleep(0.3)
            except Exception as e:
                logging.error(f"Poll error: {e}")
    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.edit_text(f"Error: {str(e)[:100]}", parse_mode="HTML")
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

async def process_document_background(message: Message, file_id: str, file_name: str):
    user_email = get_user_email(message)
    file_path = f"temp_{message.from_user.id}_{file_id[:8]}_{file_name}"
    status_msg = await message.answer("Document accepted! Processing...", parse_mode="HTML")
    try:
        await status_msg.edit_text("Downloading...", parse_mode="HTML")
        file_info = await bot.get_file(file_id)
        await bot.download_file(file_info.file_path, file_path)
        await status_msg.edit_text("Reading document...", parse_mode="HTML")
        text = await asyncio.to_thread(process_file_to_text, file_path, file_name, OPENAI_API_KEY)
        if not text or len(text) < 100:
            await status_msg.edit_text("Failed to read document", parse_mode="HTML")
            return
        await status_msg.edit_text("Creating quiz...", parse_mode="HTML")
        quiz_data = await asyncio.to_thread(generate_quiz_struct, text, 7, "Medium", "Russian")
        if not quiz_data or not quiz_data.questions:
            await status_msg.edit_text("Failed to create quiz", parse_mode="HTML")
            return
        test_title = f"Test from document"
        questions_json = [{"scenario": q.scenario, "options": q.options, "correct_option_id": q.correct_option_id, "explanation": q.explanation} for q in quiz_data.questions]
        test_id = await asyncio.to_thread(save_quiz, user_email, test_title, questions_json, getattr(quiz_data, "hints", []))
        await asyncio.to_thread(deduct_credit, user_email, 1)
        new_balance = await asyncio.to_thread(get_credits, user_email)
        await status_msg.delete()
        await message.answer(f"Quiz ready! Balance: {new_balance}", parse_mode="HTML", reply_markup=create_web_keyboard(test_id))
        for i, q in enumerate(quiz_data.questions, 1):
            try:
                await bot.send_poll(chat_id=message.chat.id, question=f"{i}. {q.scenario[:250]}", options=[opt[:95] for opt in q.options], type='quiz', correct_option_id=q.correct_option_id, explanation=q.explanation[:195] if q.explanation else None, is_anonymous=False)
                await asyncio.sleep(0.3)
            except:
                pass
    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.edit_text(f"Error: {str(e)[:100]}", parse_mode="HTML")
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

@router.message(Command("start"))
async def cmd_start(message: Message):
    credits = get_credits(get_user_email(message))
    await message.answer(f"Hello! Send me a file. Balance: {credits}", parse_mode="HTML", reply_markup=create_web_keyboard())

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    credits = get_credits(get_user_email(message))
    await message.answer(f"Credits: {credits}", parse_mode="HTML", reply_markup=create_web_keyboard())

@router.message(Command("mytests"))
async def cmd_mytests(message: Message):
    tests = get_user_quizzes(get_user_email(message))
    if not tests:
        await message.answer("No tests yet", parse_mode="HTML")
        return
    await message.answer(f"Your tests: {len(tests)}", parse_mode="HTML", reply_markup=create_web_keyboard())

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer("Send me a file to create a quiz", parse_mode="HTML", reply_markup=create_web_keyboard())

@router.message(F.video_note)
async def handle_video_note(message: Message):
    if get_credits(get_user_email(message)) <= 0:
        await message.answer("No credits", parse_mode="HTML")
        return
    asyncio.create_task(process_media_background(message, message.video_note.file_id, "video_note.mp4", False))

@router.message(F.voice)
async def handle_voice(message: Message):
    if get_credits(get_user_email(message)) <= 0:
        await message.answer("No credits", parse_mode="HTML")
        return
    asyncio.create_task(process_media_background(message, message.voice.file_id, "voice.ogg", True))

@router.message(F.audio)
async def handle_audio(message: Message):
    if get_credits(get_user_email(message)) <= 0:
        await message.answer("No credits", parse_mode="HTML")
        return
    asyncio.create_task(process_media_background(message, message.audio.file_id, message.audio.file_name or "audio.mp3", True))

@router.message(F.video)
async def handle_video(message: Message):
    if get_credits(get_user_email(message)) <= 0:
        await message.answer("No credits", parse_mode="HTML")
        return
    asyncio.create_task(process_media_background(message, message.video.file_id, message.video.file_name or "video.mp4", False))

@router.message(F.document)
async def handle_document(message: Message):
    doc = message.document
    if not any(doc.file_name.lower().endswith(ext) for ext in ('.pdf', '.docx', '.pptx', '.txt')):
        await message.answer("Unsupported format", parse_mode="HTML")
        return
    if get_credits(get_user_email(message)) <= 0:
        await message.answer("No credits", parse_mode="HTML")
        return
    asyncio.create_task(process_document_background(message, doc.file_id, doc.file_name))

@router.message()
async def handle_other(message: Message):
    await message.answer("Send a file to create a quiz", parse_mode="HTML")

async def main():
    logging.basicConfig(level=logging.INFO)
    dp = Dispatcher()
    dp.include_router(router)
    await set_main_menu(bot)
    logging.info("Bot started with ASYNC background processing")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
