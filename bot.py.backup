import asyncio
import logging
import os
import toml
from pathlib import Path
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, BotCommand, BotCommandScopeDefault, InlineKeyboardMarkup, InlineKeyboardButton
from supabase import create_client
from datetime import datetime

try:
    from logic import transcribe_for_bot as transcribe_audio, generate_quiz_ai as generate_quiz_struct, process_file_to_text_bot as process_file_to_text
    from auth import get_user_credits as get_credits, deduct_credit, save_quiz, get_user_quizzes
except ImportError as e:
    logging.error(f"CRITICAL IMPORT ERROR: {e}")
    def transcribe_audio(path): return "Error"
    def generate_quiz_struct(text, count, diff, lang): return None
    def process_file_to_text(file, file_name, api_key): return "Error"
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

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

router = Router()
bot = Bot(token=TOKEN)
WEB_APP_URL = "https://app.vyud.online"
MAX_FILE_SIZE_MB = 20

logging.basicConfig(level=logging.INFO)

async def update_user_profile(user, generation_type: str = None):
    try:
        user_email = f"{user.username or f'user{user.id}'}@telegram.io"
        existing = supabase.table("users_credits").select("total_generations, tariff").eq("telegram_id", user.id).execute()
        total_gens = 0
        current_tariff = "free"
        if existing.data and len(existing.data) > 0:
            total_gens = existing.data[0].get("total_generations", 0)
            current_tariff = existing.data[0].get("tariff", "free")
        if generation_type:
            total_gens += 1
            supabase.table("generation_logs").insert({"telegram_id": user.id, "email": user_email, "generation_type": generation_type}).execute()
        user_data = {"telegram_id": user.id, "email": user_email, "username": user.username, "first_name": user.first_name, "telegram_premium": user.is_premium or False, "last_seen": datetime.utcnow().isoformat(), "total_generations": total_gens, "tariff": current_tariff}
        supabase.table("users_credits").upsert(user_data, on_conflict="telegram_id").execute()
        logging.info(f"✅ Updated profile for {user.username} (Premium: {user.is_premium})")
        return True
    except Exception as e:
        logging.error(f"❌ Error updating profile: {e}")
        return False

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
    status_msg = await message.answer("✅ File accepted! Processing in background.", parse_mode="HTML")
    try:
        await status_msg.edit_text("📥 Downloading...", parse_mode="HTML")
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, file_path)
        await status_msg.edit_text("🎙️ Transcribing...", parse_mode="HTML")
        text = await asyncio.to_thread(transcribe_audio, file_path)
        if not text or text == "Error":
            await status_msg.edit_text("❌ Transcription failed")
            return
        await status_msg.edit_text("🧠 Generating quiz...", parse_mode="HTML")
        quiz_data = await asyncio.to_thread(generate_quiz_struct, text, 5, "medium", "Russian")
        if not quiz_data:
            await status_msg.edit_text("❌ Quiz generation failed")
            return
        questions_json = [{"question": q.question, "options": q.options, "correct_option_id": q.correct_option_id, "explanation": q.explanation} for q in quiz_data.questions]
        test_title = f"Audio test {datetime.now().strftime('%d.%m %H:%M')}"
        test_id = await asyncio.to_thread(save_quiz, user_email, test_title, questions_json, getattr(quiz_data, "hints", []))
        await update_user_profile(message.from_user, generation_type="audio" if is_audio else "video")
        await deduct_credit(user_email, 1)
        await status_msg.edit_text(f"✅ <b>Test ready!</b>\n\n📝 {len(questions_json)} questions", parse_mode="HTML", reply_markup=create_web_keyboard(test_id))
    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)[:100]}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@router.message(Command("start"))
async def cmd_start(message: Message):
    await update_user_profile(message.from_user)
    user_email = get_user_email(message)
    credits = await asyncio.to_thread(get_credits, user_email)
    premium_badge = "⭐ Premium" if message.from_user.is_premium else ""
    await message.answer(f"👋 Welcome to <b>VYUD AI</b>! {premium_badge}\n\n💳 Credits: <b>{credits}</b>\n\n📤 Send me:\n• Document (PDF/DOCX/PPTX)\n• Audio/Video\n• Voice message\n\nI'll create an interactive quiz!", parse_mode="HTML", reply_markup=create_web_keyboard())

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    await update_user_profile(message.from_user)
    user_email = get_user_email(message)
    credits = await asyncio.to_thread(get_credits, user_email)
    quizzes = await asyncio.to_thread(get_user_quizzes, user_email)
    premium_status = "⭐ <b>Telegram Premium</b>" if message.from_user.is_premium else "Regular user"
    await message.answer(f"👤 <b>Your Profile</b>\n\n📧 Email: <code>{user_email}</code>\n💳 Credits: <b>{credits}</b>\n📚 Tests created: <b>{len(quizzes)}</b>\n🎖️ Status: {premium_status}", parse_mode="HTML", reply_markup=create_web_keyboard())

@router.message(Command("mytests"))
async def cmd_mytests(message: Message):
    await update_user_profile(message.from_user)
    user_email = get_user_email(message)
    quizzes = await asyncio.to_thread(get_user_quizzes, user_email)
    if not quizzes:
        await message.answer("📭 No tests yet. Create your first one!", reply_markup=create_web_keyboard())
        return
    text = "📚 <b>Your tests:</b>\n\n"
    for i, q in enumerate(quizzes[:10], 1):
        text += f"{i}. {q.get('title', 'Untitled')}\n"
    await message.answer(text, parse_mode="HTML", reply_markup=create_web_keyboard())

@router.message(Command("help"))
async def cmd_help(message: Message):
    await update_user_profile(message.from_user)
    await message.answer(f"ℹ️ <b>How to use:</b>\n\n1️⃣ Send document/audio/video\n2️⃣ Wait for processing\n3️⃣ Get interactive quiz!\n\nMax file size: {MAX_FILE_SIZE_MB}MB", parse_mode="HTML", reply_markup=create_web_keyboard())

@router.message(F.document)
async def handle_document(message: Message):
    await update_user_profile(message.from_user)
    user_email = get_user_email(message)
    credits = await asyncio.to_thread(get_credits, user_email)
    if credits < 1:
        await message.answer("❌ Not enough credits!", reply_markup=create_web_keyboard())
        return
    doc = message.document
    if doc.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await message.answer(f"❌ File too large! Max {MAX_FILE_SIZE_MB}MB")
        return
    status_msg = await message.answer("📥 Processing document...", parse_mode="HTML")
    try:
        file_path = f"temp_{message.from_user.id}_{doc.file_id[:8]}.{doc.file_name.split('.')[-1]}"
        file = await bot.get_file(doc.file_id)
        await bot.download_file(file.file_path, file_path)
        await status_msg.edit_text("📖 Extracting text...", parse_mode="HTML")
        text = await asyncio.to_thread(process_file_to_text, file_path, doc.file_name, OPENAI_API_KEY)
        if not text or text == "Error":
            await status_msg.edit_text("❌ Text extraction failed")
            return
        await status_msg.edit_text("🧠 Generating quiz...", parse_mode="HTML")
        quiz_data = await asyncio.to_thread(generate_quiz_struct, text, 5, "medium", "Russian")
        if not quiz_data:
            await status_msg.edit_text("❌ Quiz generation failed")
            return
        questions_json = [{"question": q.question, "options": q.options, "correct_option_id": q.correct_option_id, "explanation": q.explanation} for q in quiz_data.questions]
        test_title = doc.file_name or "Document test"
        test_id = await asyncio.to_thread(save_quiz, user_email, test_title, questions_json, getattr(quiz_data, "hints", []))
        await update_user_profile(message.from_user, generation_type="document")
        await deduct_credit(user_email, 1)
        await status_msg.edit_text(f"✅ <b>Test ready!</b>\n\n📝 {len(questions_json)} questions", parse_mode="HTML", reply_markup=create_web_keyboard(test_id))
    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)[:100]}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@router.message(F.audio | F.voice)
async def handle_audio(message: Message):
    await update_user_profile(message.from_user)
    user_email = get_user_email(message)
    credits = await asyncio.to_thread(get_credits, user_email)
    if credits < 1:
        await message.answer("❌ Not enough credits!", reply_markup=create_web_keyboard())
        return
    audio = message.audio or message.voice
    if audio.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await message.answer(f"❌ File too large! Max {MAX_FILE_SIZE_MB}MB")
        return
    file_name = getattr(audio, 'file_name', 'audio.mp3')
    asyncio.create_task(process_media_background(message, audio.file_id, file_name, is_audio=True))

@router.message(F.video | F.video_note)
async def handle_video(message: Message):
    await update_user_profile(message.from_user)
    user_email = get_user_email(message)
    credits = await asyncio.to_thread(get_credits, user_email)
    if credits < 1:
        await message.answer("❌ Not enough credits!", reply_markup=create_web_keyboard())
        return
    video = message.video or message.video_note
    if video.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await message.answer(f"❌ File too large! Max {MAX_FILE_SIZE_MB}MB")
        return
    file_name = getattr(video, 'file_name', 'video.mp4')
    asyncio.create_task(process_media_background(message, video.file_id, file_name, is_audio=False))

async def main():
    dp = Dispatcher()
    dp.include_router(router)
    await set_main_menu(bot)
    logging.info("🤖 Bot started with user tracking and Premium detection!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
