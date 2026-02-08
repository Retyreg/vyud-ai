import asyncio
import logging
import os
import json
import toml
from pathlib import Path
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    Message, BotCommand, BotCommandScopeDefault,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from supabase import create_client
from datetime import datetime, timedelta

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
    ADMIN_TELEGRAM_ID = secrets.get("ADMIN_TELEGRAM_ID", "")
else:
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", "")

if not TOKEN: raise ValueError("BOT_TOKEN not found")
if not OPENAI_API_KEY: raise ValueError("OPENAI_API_KEY not found")

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# ============================================
# CONSTANTS
# ============================================

WELCOME_CREDITS = 5
MAX_FILE_SIZE_MB = 20
WEB_APP_URL = "https://app.vyud.online"

# Настройки генерации по умолчанию
DEFAULT_QUESTIONS = 5
DEFAULT_DIFFICULTY = "medium"
DEFAULT_LANG = "Russian"

logging.basicConfig(level=logging.INFO)

router = Router()
bot = Bot(token=TOKEN)


# ============================================
# FSM: ПОШАГОВОЕ СОЗДАНИЕ КУРСА (/create)
# ============================================

class CreateCourse(StatesGroup):
    waiting_for_title = State()
    waiting_for_source = State()      # файл или текст
    waiting_for_text = State()        # если выбрал "ввести текст"
    waiting_for_settings = State()    # кол-во вопросов + сложность
    waiting_for_file = State()        # если выбрал "загрузить файл"


# ============================================
# FSM: НАСТРОЙКИ ПОСЛЕ ЗАГРУЗКИ ФАЙЛА
# ============================================

class FileSettings(StatesGroup):
    waiting_for_config = State()  # ожидаем выбор настроек через inline-кнопки


# ============================================
# WELCOME CREDITS
# ============================================

async def ensure_user_credits(telegram_id: int, username: str = None):
    """Проверяет/создаёт пользователя в БД с welcome-кредитами."""
    try:
        response = supabase.table('users_credits') \
            .select('credits') \
            .eq('telegram_id', telegram_id) \
            .execute()
        
        if response.data:
            return response.data[0]['credits']
        else:
            user_email = f"{telegram_id}@telegram.io"
            supabase.table('users_credits').insert({
                'email': user_email,
                'telegram_id': telegram_id,
                'username': username or 'unknown',
                'credits': WELCOME_CREDITS,
                'role': 'user',
                'tariff': 'free',
                'telegram_premium': False,
                'total_generations': 0
            }).execute()
            
            logging.info(f"✅ Новый пользователь {telegram_id} (@{username}) получил {WELCOME_CREDITS} кредитов")
            return WELCOME_CREDITS
            
    except Exception as e:
        import traceback
        logging.error(f"❌ Ошибка БД для user {telegram_id}: {e}\n{traceback.format_exc()}")
    return 0


# ============================================
# РЕФЕРАЛЬНАЯ СИСТЕМА (без изменений)
# ============================================

async def notify_admin(text: str):
    if ADMIN_TELEGRAM_ID:
        try:
            await bot.send_message(chat_id=int(ADMIN_TELEGRAM_ID), text=text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Ошибка уведомления админа: {e}")


def extract_ref_code(start_param: str) -> str | None:
    if start_param and start_param.startswith("ref_"):
        return start_param
    return None


def get_partner_by_ref_code(ref_code: str) -> dict | None:
    try:
        result = supabase.table("partners") \
            .select("id, name, commission_percent, commission_months") \
            .eq("ref_code", ref_code) \
            .eq("is_active", True) \
            .execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logging.error(f"Ошибка поиска партнёра: {e}")
        return None


async def save_referral(telegram_id: int, ref_code: str, username: str = None) -> dict:
    try:
        partner = get_partner_by_ref_code(ref_code)
        if not partner:
            return {"success": False, "partner_name": None}
        
        existing = supabase.table("referrals").select("id").eq("telegram_id", telegram_id).execute()
        if existing.data:
            return {"success": False, "partner_name": None}
        
        supabase.table("referrals").insert({
            "partner_id": partner["id"],
            "telegram_id": telegram_id,
            "ref_code": ref_code,
            "user_email": f"tg_{telegram_id}"
        }).execute()
        
        notification = (
            f"🎯 <b>Новый реферал!</b>\n\n"
            f"Партнёр: {partner['name']} ({ref_code})\n"
            f"TG ID: <code>{telegram_id}</code>\n"
            f"Username: @{username or 'нет'}"
        )
        
        return {"success": True, "partner_name": partner["name"], "notification": notification}
    except Exception as e:
        logging.error(f"Ошибка сохранения реферала: {e}")
        return {"success": False, "partner_name": None}


async def process_referral_payment(telegram_id: int, payment_amount: float) -> dict:
    try:
        referral = supabase.table("referrals") \
            .select("id, partner_id, ref_code, first_payment_at, commission_expires_at") \
            .eq("telegram_id", telegram_id).execute()
        
        if not referral.data:
            return {"success": False, "commission": 0}
        
        ref = referral.data[0]
        partner = supabase.table("partners") \
            .select("id, name, commission_percent, is_active") \
            .eq("id", ref["partner_id"]).execute()
        
        if not partner.data or not partner.data[0]["is_active"]:
            return {"success": False, "commission": 0}
        
        p = partner.data[0]
        now = datetime.now()
        
        if not ref["first_payment_at"]:
            commission_expires = now + timedelta(days=90)
            supabase.table("referrals").update({
                "first_payment_at": now.isoformat(),
                "commission_expires_at": commission_expires.isoformat()
            }).eq("id", ref["id"]).execute()
        else:
            expires_str = ref["commission_expires_at"]
            if expires_str:
                expires_at = datetime.fromisoformat(expires_str.replace("Z", "").split("+")[0])
                if now > expires_at:
                    return {"success": False, "commission": 0, "message": "Срок комиссии истёк"}
        
        commission = payment_amount * p["commission_percent"] / 100
        
        supabase.table("partner_commissions").insert({
            "partner_id": p["id"],
            "referral_id": ref["id"],
            "payment_amount": payment_amount,
            "commission_amount": commission
        }).execute()
        
        current = supabase.table("partners").select("total_earned").eq("id", p["id"]).execute()
        new_total = float(current.data[0]["total_earned"] or 0) + commission
        supabase.table("partners").update({"total_earned": new_total}).eq("id", p["id"]).execute()
        
        notification = (
            f"💰 <b>Платёж реферала!</b>\n\n"
            f"Партнёр: {p['name']} ({ref['ref_code']})\n"
            f"Сумма платежа: {payment_amount}₽\n"
            f"Комиссия ({p['commission_percent']}%): {commission:.2f}₽\n"
            f"TG ID клиента: <code>{telegram_id}</code>"
        )
        
        return {"success": True, "commission": commission, "notification": notification}
    except Exception as e:
        logging.error(f"Ошибка обработки платежа реферала: {e}")
        return {"success": False, "commission": 0}


# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

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
            supabase.table("generation_logs").insert({
                "telegram_id": user.id,
                "email": user_email,
                "generation_type": generation_type
            }).execute()
        user_data = {
            "telegram_id": user.id,
            "email": user_email,
            "username": user.username,
            "first_name": user.first_name,
            "telegram_premium": user.is_premium or False,
            "last_seen": datetime.utcnow().isoformat(),
            "total_generations": total_gens,
            "tariff": current_tariff
        }
        supabase.table("users_credits").upsert(user_data, on_conflict="telegram_id").execute()
        return True
    except Exception as e:
        logging.error(f"❌ Error updating profile: {e}")
        return False


async def set_main_menu(bot_instance: Bot):
    await bot_instance.set_my_commands([
        BotCommand(command='/start', description='Начало работы'),
        BotCommand(command='/create', description='Создать курс пошагово'),
        BotCommand(command='/profile', description='Мой профиль'),
        BotCommand(command='/mytests', description='Мои тесты'),
        BotCommand(command='/help', description='Помощь'),
    ], scope=BotCommandScopeDefault())


def get_user_email(message: Message) -> str:
    username = message.from_user.username or f"user{message.from_user.id}"
    return f"{username}@telegram.io"


def create_web_keyboard(test_id: str = None) -> InlineKeyboardMarkup:
    buttons = []
    if test_id:
        buttons.append([InlineKeyboardButton(text="🌐 Открыть тест", url=f"{WEB_APP_URL}/?test={test_id}")])
    buttons.append([InlineKeyboardButton(text="💻 Веб-версия", url=WEB_APP_URL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================
# INLINE-КНОПКИ НАСТРОЕК ГЕНЕРАЦИИ
# ============================================

def create_settings_keyboard(
    questions: int = 5,
    difficulty: str = "medium",
    lang: str = "ru"
) -> InlineKeyboardMarkup:
    """Клавиатура выбора параметров генерации теста."""
    
    # Кнопки количества вопросов
    q_buttons = []
    for q in [5, 10, 15]:
        label = f"{'✅ ' if questions == q else ''}{q} вопросов"
        q_buttons.append(InlineKeyboardButton(
            text=label,
            callback_data=f"set_q:{q}:{difficulty}:{lang}"
        ))
    
    # Кнопки сложности
    diff_map = {"easy": "Лёгкий", "medium": "Средний", "hard": "Сложный"}
    d_buttons = []
    for d_key, d_label in diff_map.items():
        label = f"{'✅ ' if difficulty == d_key else ''}{d_label}"
        d_buttons.append(InlineKeyboardButton(
            text=label,
            callback_data=f"set_d:{questions}:{d_key}:{lang}"
        ))
    
    # Кнопки языка
    lang_map = {"ru": "🇷🇺 Рус", "en": "🇬🇧 Eng"}
    l_buttons = []
    for l_key, l_label in lang_map.items():
        label = f"{'✅ ' if lang == l_key else ''}{l_label}"
        l_buttons.append(InlineKeyboardButton(
            text=label,
            callback_data=f"set_l:{questions}:{difficulty}:{l_key}"
        ))
    
    # Кнопка генерации
    generate_btn = [InlineKeyboardButton(
        text="🚀 Сгенерировать!",
        callback_data=f"generate:{questions}:{difficulty}:{lang}"
    )]
    
    return InlineKeyboardMarkup(inline_keyboard=[
        q_buttons,
        d_buttons,
        l_buttons,
        generate_btn
    ])


def parse_settings_callback(data: str) -> dict:
    """Парсит callback_data настроек: action:questions:difficulty:lang"""
    parts = data.split(":")
    return {
        "action": parts[0],
        "questions": int(parts[1]),
        "difficulty": parts[2],
        "lang": parts[3]
    }


# ============================================
# ПРЕВЬЮ КУРСА
# ============================================

async def send_course_preview(
    chat_id: int,
    test_title: str,
    questions_json: list,
    quiz_data,
    test_id: str,
    difficulty: str = "medium"
):
    """Отправляет красивое превью курса перед поллами."""
    
    diff_labels = {"easy": "🟢 Лёгкий", "medium": "🟡 Средний", "hard": "🔴 Сложный"}
    diff_label = diff_labels.get(difficulty, "🟡 Средний")
    
    # Собираем темы из вопросов (первые слова)
    topics = set()
    for q in questions_json[:5]:
        words = q["question"].split()[:3]
        topics.add(" ".join(words))
    
    preview_text = (
        f"📋 <b>{test_title}</b>\n"
        f"{'━' * 24}\n\n"
        f"📝 Вопросов: <b>{len(questions_json)}</b>\n"
        f"📊 Сложность: {diff_label}\n"
    )
    
    # Если есть hints — добавляем инфо
    hints = getattr(quiz_data, "hints", [])
    if hints:
        preview_text += f"💡 Подсказок: <b>{len(hints)}</b>\n"
    
    preview_text += (
        f"\n{'━' * 24}\n"
        f"⬇️ Тест отправлен ниже — можно пройти прямо в Telegram!\n"
        f"🌐 Или открой в веб-версии для полного опыта."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Открыть в браузере", url=f"{WEB_APP_URL}/?test={test_id}")],
        [InlineKeyboardButton(text="📤 Поделиться тестом", switch_inline_query=f"test_{test_id}")]
    ])
    
    await bot.send_message(
        chat_id=chat_id,
        text=preview_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


# ============================================
# ГЕНЕРАЦИЯ ТЕСТА (общая логика)
# ============================================

async def generate_and_send_quiz(
    message: Message,
    text: str,
    title: str,
    num_questions: int = 5,
    difficulty: str = "medium",
    lang: str = "ru",
    generation_type: str = "document",
    status_msg: Message = None
):
    """
    Общая функция генерации теста.
    Используется и при загрузке файла, и при /create.
    """
    user_email = get_user_email(message)
    lang_full = "Russian" if lang == "ru" else "English"
    
    try:
        if status_msg:
            await status_msg.edit_text("🧠 Генерирую тест...", parse_mode="HTML")
        else:
            status_msg = await message.answer("🧠 Генерирую тест...", parse_mode="HTML")
        
        quiz_data = await asyncio.to_thread(
            generate_quiz_struct, text, num_questions, difficulty, lang_full
        )
        
        if not quiz_data:
            await status_msg.edit_text("❌ Не удалось сгенерировать тест. Попробуйте другой файл.")
            return
        
        questions_json = [{
            "question": q.scenario,
            "options": q.options,
            "correct_option_id": q.correct_option_id,
            "explanation": q.explanation
        } for q in quiz_data.questions]
        
        test_id = await asyncio.to_thread(
            save_quiz, user_email, title, questions_json,
            getattr(quiz_data, "hints", [])
        )
        
        await update_user_profile(message.from_user, generation_type=generation_type)
        await asyncio.to_thread(deduct_credit, user_email, 1)
        
        # Удаляем статусное сообщение
        await status_msg.delete()
        
        # Отправляем превью курса
        await send_course_preview(
            chat_id=message.chat.id,
            test_title=title,
            questions_json=questions_json,
            quiz_data=quiz_data,
            test_id=test_id,
            difficulty=difficulty
        )
        
        # Отправляем поллы
        for i, q in enumerate(quiz_data.questions, 1):
            try:
                await bot.send_poll(
                    chat_id=message.chat.id,
                    question=f"{i}. {q.scenario[:250]}",
                    options=[opt[:95] for opt in q.options],
                    type="quiz",
                    correct_option_id=q.correct_option_id,
                    explanation=q.explanation[:195] if q.explanation else None,
                    is_anonymous=False
                )
                await asyncio.sleep(0.3)
            except Exception as e:
                logging.error(f"Poll error: {e}")
        
    except Exception as e:
        logging.error(f"Error in generate_and_send_quiz: {e}")
        if status_msg:
            await status_msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")


# ============================================
# ОБРАБОТКА МЕДИА (аудио/видео — фоновый процесс)
# ============================================

async def process_media_background(
    message: Message,
    file_id: str,
    file_name: str,
    is_audio: bool = False,
    num_questions: int = 5,
    difficulty: str = "medium",
    lang: str = "ru"
):
    user_email = get_user_email(message)
    file_path = f"temp_{message.from_user.id}_{file_id[:8]}.{'mp3' if is_audio else 'mp4'}"
    status_msg = await message.answer("✅ Файл принят! Обрабатываю...", parse_mode="HTML")
    
    try:
        await status_msg.edit_text("📥 Скачиваю файл...", parse_mode="HTML")
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, file_path)
        
        await status_msg.edit_text("🎙️ Транскрибирую...", parse_mode="HTML")
        text = await asyncio.to_thread(transcribe_audio, file_path)
        
        if not text or text == "Error":
            await status_msg.edit_text("❌ Не удалось расшифровать аудио/видео")
            return
        
        title = f"{'Аудио' if is_audio else 'Видео'} тест {datetime.now().strftime('%d.%m %H:%M')}"
        gen_type = "audio" if is_audio else "video"
        
        await generate_and_send_quiz(
            message=message,
            text=text,
            title=title,
            num_questions=num_questions,
            difficulty=difficulty,
            lang=lang,
            generation_type=gen_type,
            status_msg=status_msg
        )
        
    except Exception as e:
        logging.error(f"Media processing error: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


# ============================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================

@router.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    # Сбрасываем любое FSM-состояние
    await state.clear()
    
    telegram_id = message.from_user.id
    username = message.from_user.username
    
    # Реферальная обработка
    ref_code = extract_ref_code(command.args) if command.args else None
    partner_name = None
    
    if ref_code:
        result = await save_referral(telegram_id, ref_code, username)
        if result["success"]:
            partner_name = result["partner_name"]
            await notify_admin(result["notification"])
    
    credits = await ensure_user_credits(telegram_id, username)
    
    # Проверяем, новый ли пользователь
    response = supabase.table('users_credits') \
        .select('created_at') \
        .eq('telegram_id', telegram_id) \
        .execute()
    
    is_new_user = False
    if response.data:
        created_at = datetime.fromisoformat(response.data[0]['created_at'].replace('Z', '+00:00'))
        is_new_user = datetime.now(created_at.tzinfo) - created_at < timedelta(seconds=10)
    
    if is_new_user:
        welcome_text = f"🎁 Добро пожаловать в VYUD AI!\n\n"
        if partner_name:
            welcome_text += f"🤝 Вас пригласил: {partner_name}\n\n"
        welcome_text += (
            f"Тебе начислено {WELCOME_CREDITS} бесплатных кредитов.\n\n"
            f"<b>Как это работает:</b>\n"
            f"📤 Отправь документ (PDF/DOCX), аудио или видео\n"
            f"⚙️ Выбери параметры теста\n"
            f"✅ Получи интерактивный курс за секунды!\n\n"
            f"Или используй /create для пошагового создания.\n\n"
            f"💳 Баланс: {credits} кредитов"
        )
    else:
        welcome_text = (
            f"С возвращением! 👋\n\n"
            f"💳 Твой баланс: {credits} кредитов\n\n"
            f"📤 Отправь файл — выбери настройки — получи тест\n"
            f"📝 Или /create для пошагового создания курса"
        )
    
    await message.answer(welcome_text, parse_mode="HTML")


# ============================================
# /create — ПОШАГОВЫЙ ВИЗАРД
# ============================================

@router.message(Command("create"))
async def cmd_create(message: Message, state: FSMContext):
    await update_user_profile(message.from_user)
    
    # Проверяем кредиты
    user_email = get_user_email(message)
    credits = await asyncio.to_thread(get_credits, user_email)
    if credits < 1:
        await message.answer("❌ Недостаточно кредитов!", reply_markup=create_web_keyboard())
        return
    
    await state.set_state(CreateCourse.waiting_for_title)
    await message.answer(
        "📝 <b>Создание курса — шаг 1/3</b>\n\n"
        "Введи название курса:\n\n"
        "<i>Например: «Онбординг новых сотрудников» или «Основы Python»</i>\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нечего отменять 🤷")
        return
    
    await state.clear()
    await message.answer("❌ Создание курса отменено.\n\nОтправь файл или используй /create чтобы начать заново.")


@router.message(CreateCourse.waiting_for_title)
async def create_step_title(message: Message, state: FSMContext):
    title = message.text.strip() if message.text else ""
    
    if not title or len(title) < 3:
        await message.answer("⚠️ Название слишком короткое. Введи хотя бы 3 символа:")
        return
    
    if len(title) > 100:
        title = title[:100]
    
    await state.update_data(title=title)
    await state.set_state(CreateCourse.waiting_for_source)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Загрузить файл", callback_data="create_src:file")],
        [InlineKeyboardButton(text="✏️ Ввести текст", callback_data="create_src:text")],
    ])
    
    await message.answer(
        f"✅ Название: <b>{title}</b>\n\n"
        f"📝 <b>Шаг 2/3</b> — Источник материала:\n\n"
        f"Выбери, откуда взять контент для курса:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("create_src:"))
async def create_step_source(callback: CallbackQuery, state: FSMContext):
    source = callback.data.split(":")[1]
    await callback.answer()
    
    if source == "text":
        await state.set_state(CreateCourse.waiting_for_text)
        await callback.message.edit_text(
            "✏️ <b>Шаг 2/3</b> — Введи текст\n\n"
            "Вставь текст, на основе которого создать тест.\n"
            "Минимум 100 символов.\n\n"
            "Отмена: /cancel",
            parse_mode="HTML"
        )
    else:  # file
        await state.set_state(CreateCourse.waiting_for_file)
        await callback.message.edit_text(
            "📄 <b>Шаг 2/3</b> — Загрузи файл\n\n"
            "Поддерживаемые форматы:\n"
            "• PDF, DOCX — документы\n"
            "• MP3, OGG — аудио\n"
            "• MP4 — видео\n\n"
            f"Макс. размер: {MAX_FILE_SIZE_MB}MB\n\n"
            "Отмена: /cancel",
            parse_mode="HTML"
        )


@router.message(CreateCourse.waiting_for_text)
async def create_step_text_input(message: Message, state: FSMContext):
    text = message.text or ""
    
    if len(text) < 100:
        await message.answer(
            f"⚠️ Текст слишком короткий ({len(text)} символов).\n"
            f"Нужно минимум 100 символов для качественного теста."
        )
        return
    
    await state.update_data(source_text=text)
    data = await state.get_data()
    
    # Переходим к настройкам
    await state.set_state(CreateCourse.waiting_for_settings)
    
    await message.answer(
        f"✅ Текст принят ({len(text)} символов)\n\n"
        f"⚙️ <b>Шаг 3/3</b> — Настройки теста\n\n"
        f"Выбери параметры и нажми «Сгенерировать»:",
        parse_mode="HTML",
        reply_markup=create_settings_keyboard()
    )


@router.message(CreateCourse.waiting_for_file, F.document)
async def create_step_file_upload(message: Message, state: FSMContext):
    doc = message.document
    
    if doc.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await message.answer(f"❌ Файл слишком большой! Максимум {MAX_FILE_SIZE_MB}MB")
        return
    
    await state.update_data(
        file_id=doc.file_id,
        file_name=doc.file_name,
        source_type="document"
    )
    
    await state.set_state(CreateCourse.waiting_for_settings)
    
    await message.answer(
        f"✅ Файл принят: <b>{doc.file_name}</b>\n\n"
        f"⚙️ <b>Шаг 3/3</b> — Настройки теста\n\n"
        f"Выбери параметры и нажми «Сгенерировать»:",
        parse_mode="HTML",
        reply_markup=create_settings_keyboard()
    )


@router.message(CreateCourse.waiting_for_file, F.audio | F.voice)
async def create_step_audio_upload(message: Message, state: FSMContext):
    audio = message.audio or message.voice
    
    if audio.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await message.answer(f"❌ Файл слишком большой! Максимум {MAX_FILE_SIZE_MB}MB")
        return
    
    await state.update_data(
        file_id=audio.file_id,
        file_name=getattr(audio, 'file_name', 'audio.mp3'),
        source_type="audio"
    )
    
    await state.set_state(CreateCourse.waiting_for_settings)
    
    await message.answer(
        f"✅ Аудио принято\n\n"
        f"⚙️ <b>Шаг 3/3</b> — Настройки теста\n\n"
        f"Выбери параметры и нажми «Сгенерировать»:",
        parse_mode="HTML",
        reply_markup=create_settings_keyboard()
    )


@router.message(CreateCourse.waiting_for_file, F.video | F.video_note)
async def create_step_video_upload(message: Message, state: FSMContext):
    video = message.video or message.video_note
    
    if video.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await message.answer(f"❌ Файл слишком большой! Максимум {MAX_FILE_SIZE_MB}MB")
        return
    
    await state.update_data(
        file_id=video.file_id,
        file_name=getattr(video, 'file_name', 'video.mp4'),
        source_type="video"
    )
    
    await state.set_state(CreateCourse.waiting_for_settings)
    
    await message.answer(
        f"✅ Видео принято\n\n"
        f"⚙️ <b>Шаг 3/3</b> — Настройки теста\n\n"
        f"Выбери параметры и нажми «Сгенерировать»:",
        parse_mode="HTML",
        reply_markup=create_settings_keyboard()
    )


# ============================================
# CALLBACK: НАСТРОЙКИ (обновление кнопок)
# ============================================

@router.callback_query(F.data.startswith("set_q:") | F.data.startswith("set_d:") | F.data.startswith("set_l:"))
async def handle_settings_update(callback: CallbackQuery):
    """Обновляет inline-клавиатуру при переключении настроек."""
    settings = parse_settings_callback(callback.data)
    
    await callback.message.edit_reply_markup(
        reply_markup=create_settings_keyboard(
            questions=settings["questions"],
            difficulty=settings["difficulty"],
            lang=settings["lang"]
        )
    )
    await callback.answer()


# ============================================
# CALLBACK: ГЕНЕРАЦИЯ ИЗ /create ВИЗАРДА
# ============================================

@router.callback_query(F.data.startswith("generate:"))
async def handle_generate_from_wizard(callback: CallbackQuery, state: FSMContext):
    """Запуск генерации из визарда /create."""
    settings = parse_settings_callback(callback.data)
    data = await state.get_data()
    
    await callback.answer("🚀 Запускаю генерацию...")
    await state.clear()
    
    title = data.get("title", "Тест")
    source_text = data.get("source_text")
    file_id = data.get("file_id")
    file_name = data.get("file_name")
    source_type = data.get("source_type", "document")
    
    message = callback.message
    
    if source_text:
        # Текст уже есть — генерируем напрямую
        await generate_and_send_quiz(
            message=message,
            text=source_text,
            title=title,
            num_questions=settings["questions"],
            difficulty=settings["difficulty"],
            lang=settings["lang"],
            generation_type="text"
        )
    elif file_id:
        # Нужно скачать и обработать файл
        if source_type in ("audio", "video"):
            await process_media_background(
                message=message,
                file_id=file_id,
                file_name=file_name,
                is_audio=(source_type == "audio"),
                num_questions=settings["questions"],
                difficulty=settings["difficulty"],
                lang=settings["lang"]
            )
        else:
            # Документ
            status_msg = await message.answer("📥 Скачиваю файл...", parse_mode="HTML")
            file_path = f"temp_{callback.from_user.id}_{file_id[:8]}.{file_name.split('.')[-1] if file_name else 'pdf'}"
            
            try:
                file = await bot.get_file(file_id)
                await bot.download_file(file.file_path, file_path)
                
                await status_msg.edit_text("📖 Извлекаю текст...", parse_mode="HTML")
                text = await asyncio.to_thread(process_file_to_text, file_path, file_name, OPENAI_API_KEY)
                
                if not text or text == "Error":
                    await status_msg.edit_text("❌ Не удалось извлечь текст из файла")
                    return
                
                await generate_and_send_quiz(
                    message=message,
                    text=text,
                    title=title,
                    num_questions=settings["questions"],
                    difficulty=settings["difficulty"],
                    lang=settings["lang"],
                    generation_type="document",
                    status_msg=status_msg
                )
            except Exception as e:
                logging.error(f"Wizard document error: {e}")
                await status_msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)
    else:
        await message.answer("⚠️ Нет исходных данных. Начни заново: /create")


# ============================================
# CALLBACK: ГЕНЕРАЦИЯ ИЗ БЫСТРОЙ ЗАГРУЗКИ
# ============================================

@router.callback_query(F.data.startswith("quickgen:"))
async def handle_quick_generate(callback: CallbackQuery, state: FSMContext):
    """Запуск генерации из быстрой загрузки файла (без /create)."""
    settings = parse_settings_callback(callback.data)
    data = await state.get_data()
    
    await callback.answer("🚀 Запускаю генерацию...")
    await state.clear()
    
    file_id = data.get("file_id")
    file_name = data.get("file_name", "document")
    source_type = data.get("source_type", "document")
    
    message = callback.message
    
    if not file_id:
        await message.answer("⚠️ Файл не найден. Отправь его ещё раз.")
        return
    
    title = file_name or f"Тест {datetime.now().strftime('%d.%m %H:%M')}"
    
    if source_type in ("audio", "video"):
        await process_media_background(
            message=message,
            file_id=file_id,
            file_name=file_name,
            is_audio=(source_type == "audio"),
            num_questions=settings["questions"],
            difficulty=settings["difficulty"],
            lang=settings["lang"]
        )
    else:
        status_msg = await message.answer("📥 Скачиваю файл...", parse_mode="HTML")
        file_path = f"temp_{callback.from_user.id}_{file_id[:8]}.{file_name.split('.')[-1] if '.' in file_name else 'pdf'}"
        
        try:
            file = await bot.get_file(file_id)
            await bot.download_file(file.file_path, file_path)
            
            await status_msg.edit_text("📖 Извлекаю текст...", parse_mode="HTML")
            text = await asyncio.to_thread(process_file_to_text, file_path, file_name, OPENAI_API_KEY)
            
            if not text or text == "Error":
                await status_msg.edit_text("❌ Не удалось извлечь текст")
                return
            
            await generate_and_send_quiz(
                message=message,
                text=text,
                title=title,
                num_questions=settings["questions"],
                difficulty=settings["difficulty"],
                lang=settings["lang"],
                generation_type="document",
                status_msg=status_msg
            )
        except Exception as e:
            logging.error(f"Quick generate error: {e}")
            await status_msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)


# ============================================
# БЫСТРАЯ ЗАГРУЗКА: НАСТРОЙКИ ЧЕРЕЗ INLINE
# ============================================

def create_quick_settings_keyboard(
    questions: int = 5,
    difficulty: str = "medium",
    lang: str = "ru"
) -> InlineKeyboardMarkup:
    """Та же клавиатура, но с callback prefix 'quickgen' вместо 'generate'."""
    
    q_buttons = []
    for q in [5, 10, 15]:
        label = f"{'✅ ' if questions == q else ''}{q} вопр."
        q_buttons.append(InlineKeyboardButton(
            text=label,
            callback_data=f"qset_q:{q}:{difficulty}:{lang}"
        ))
    
    diff_map = {"easy": "Лёгкий", "medium": "Средний", "hard": "Сложный"}
    d_buttons = []
    for d_key, d_label in diff_map.items():
        label = f"{'✅ ' if difficulty == d_key else ''}{d_label}"
        d_buttons.append(InlineKeyboardButton(
            text=label,
            callback_data=f"qset_d:{questions}:{d_key}:{lang}"
        ))
    
    lang_map = {"ru": "🇷🇺 Рус", "en": "🇬🇧 Eng"}
    l_buttons = []
    for l_key, l_label in lang_map.items():
        label = f"{'✅ ' if lang == l_key else ''}{l_label}"
        l_buttons.append(InlineKeyboardButton(
            text=label,
            callback_data=f"qset_l:{questions}:{difficulty}:{l_key}"
        ))
    
    generate_btn = [InlineKeyboardButton(
        text="🚀 Сгенерировать!",
        callback_data=f"quickgen:{questions}:{difficulty}:{lang}"
    )]
    
    return InlineKeyboardMarkup(inline_keyboard=[q_buttons, d_buttons, l_buttons, generate_btn])


@router.callback_query(F.data.startswith("qset_q:") | F.data.startswith("qset_d:") | F.data.startswith("qset_l:"))
async def handle_quick_settings_update(callback: CallbackQuery):
    """Обновляет quick-клавиатуру."""
    parts = callback.data.split(":")
    settings = {
        "questions": int(parts[1]),
        "difficulty": parts[2],
        "lang": parts[3]
    }
    
    await callback.message.edit_reply_markup(
        reply_markup=create_quick_settings_keyboard(
            questions=settings["questions"],
            difficulty=settings["difficulty"],
            lang=settings["lang"]
        )
    )
    await callback.answer()


# ============================================
# ОБРАБОТЧИКИ ФАЙЛОВ (с inline-настройками)
# ============================================

@router.message(F.document)
async def handle_document(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    await ensure_user_credits(telegram_id, message.from_user.username)
    await update_user_profile(message.from_user)
    
    user_email = get_user_email(message)
    credits = await asyncio.to_thread(get_credits, user_email)
    if credits < 1:
        await message.answer("❌ Недостаточно кредитов!", reply_markup=create_web_keyboard())
        return
    
    doc = message.document
    if doc.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await message.answer(f"❌ Файл слишком большой! Максимум {MAX_FILE_SIZE_MB}MB")
        return
    
    # Сохраняем file_id в FSM и показываем настройки
    await state.update_data(
        file_id=doc.file_id,
        file_name=doc.file_name,
        source_type="document"
    )
    
    await message.answer(
        f"📄 <b>{doc.file_name}</b>\n\n"
        f"⚙️ Настрой параметры теста и нажми «Сгенерировать»:",
        parse_mode="HTML",
        reply_markup=create_quick_settings_keyboard()
    )


@router.message(F.audio | F.voice)
async def handle_audio(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    await ensure_user_credits(telegram_id, message.from_user.username)
    await update_user_profile(message.from_user)
    
    user_email = get_user_email(message)
    credits = await asyncio.to_thread(get_credits, user_email)
    if credits < 1:
        await message.answer("❌ Недостаточно кредитов!", reply_markup=create_web_keyboard())
        return
    
    audio = message.audio or message.voice
    if audio.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await message.answer(f"❌ Файл слишком большой! Максимум {MAX_FILE_SIZE_MB}MB")
        return
    
    await state.update_data(
        file_id=audio.file_id,
        file_name=getattr(audio, 'file_name', 'audio.mp3'),
        source_type="audio"
    )
    
    await message.answer(
        f"🎙️ <b>Аудио принято</b>\n\n"
        f"⚙️ Настрой параметры теста и нажми «Сгенерировать»:",
        parse_mode="HTML",
        reply_markup=create_quick_settings_keyboard()
    )


@router.message(F.video | F.video_note)
async def handle_video(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    await ensure_user_credits(telegram_id, message.from_user.username)
    await update_user_profile(message.from_user)
    
    user_email = get_user_email(message)
    credits = await asyncio.to_thread(get_credits, user_email)
    if credits < 1:
        await message.answer("❌ Недостаточно кредитов!", reply_markup=create_web_keyboard())
        return
    
    video = message.video or message.video_note
    if video.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await message.answer(f"❌ Файл слишком большой! Максимум {MAX_FILE_SIZE_MB}MB")
        return
    
    await state.update_data(
        file_id=video.file_id,
        file_name=getattr(video, 'file_name', 'video.mp4'),
        source_type="video"
    )
    
    await message.answer(
        f"🎬 <b>Видео принято</b>\n\n"
        f"⚙️ Настрой параметры теста и нажми «Сгенерировать»:",
        parse_mode="HTML",
        reply_markup=create_quick_settings_keyboard()
    )


# ============================================
# ОСТАЛЬНЫЕ КОМАНДЫ
# ============================================

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    await update_user_profile(message.from_user)
    user_email = get_user_email(message)
    credits = await asyncio.to_thread(get_credits, user_email)
    quizzes = await asyncio.to_thread(get_user_quizzes, user_email)
    premium_status = "⭐ Telegram Premium" if message.from_user.is_premium else "Обычный"
    
    await message.answer(
        f"👤 <b>Твой профиль</b>\n\n"
        f"📧 Email: <code>{user_email}</code>\n"
        f"💳 Кредиты: <b>{credits}</b>\n"
        f"📚 Создано тестов: <b>{len(quizzes)}</b>\n"
        f"🎖️ Статус: {premium_status}",
        parse_mode="HTML",
        reply_markup=create_web_keyboard()
    )


@router.message(Command("mytests"))
async def cmd_mytests(message: Message):
    await update_user_profile(message.from_user)
    user_email = get_user_email(message)
    quizzes = await asyncio.to_thread(get_user_quizzes, user_email)
    
    if not quizzes:
        await message.answer(
            "📭 Тестов пока нет.\n\n"
            "Отправь файл или используй /create!",
            reply_markup=create_web_keyboard()
        )
        return
    
    text = "📚 <b>Твои тесты:</b>\n\n"
    for i, q in enumerate(quizzes[:10], 1):
        title = q.get('title', 'Без названия')
        test_id = q.get('id', '')
        text += f"{i}. {title}\n"
        if test_id:
            text += f"   🔗 {WEB_APP_URL}/?test={test_id}\n"
    
    if len(quizzes) > 10:
        text += f"\n...и ещё {len(quizzes) - 10} тестов"
    
    await message.answer(text, parse_mode="HTML", reply_markup=create_web_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message):
    await update_user_profile(message.from_user)
    await message.answer(
        f"ℹ️ <b>Как пользоваться VYUD AI</b>\n\n"
        f"<b>Быстрый способ:</b>\n"
        f"📤 Отправь файл → выбери настройки → получи тест\n\n"
        f"<b>Пошаговый визард:</b>\n"
        f"/create → назови курс → загрузи материал → настрой → готово!\n\n"
        f"<b>Поддерживаемые форматы:</b>\n"
        f"• 📄 PDF, DOCX — документы\n"
        f"• 🎙️ MP3, голосовые — аудио\n"
        f"• 🎬 MP4, видеокружки — видео\n\n"
        f"<b>Команды:</b>\n"
        f"/create — создать курс пошагово\n"
        f"/profile — баланс и статистика\n"
        f"/mytests — список тестов\n\n"
        f"📏 Макс. размер файла: {MAX_FILE_SIZE_MB}MB",
        parse_mode="HTML",
        reply_markup=create_web_keyboard()
    )


# ============================================
# АДМИНСКИЕ КОМАНДЫ (РЕФЕРАЛЬНАЯ СИСТЕМА)
# ============================================

@router.message(Command("add_partner"))
async def cmd_add_partner(message: Message, command: CommandObject):
    if str(message.from_user.id) != ADMIN_TELEGRAM_ID:
        return
    
    args = command.args.split() if command.args else []
    if len(args) < 2:
        await message.answer(
            "📝 Формат: <code>/add_partner Имя ref_CODE [telegram_id]</code>\n\n"
            "Примеры:\n"
            "<code>/add_partner Иван ref_IVAN</code>\n"
            "<code>/add_partner Мария ref_MARIA 123456789</code>",
            parse_mode="HTML"
        )
        return
    
    name = args[0]
    ref_code = args[1] if args[1].startswith("ref_") else f"ref_{args[1]}"
    tg_id = int(args[2]) if len(args) > 2 else None
    
    try:
        data = {"name": name, "ref_code": ref_code}
        if tg_id:
            data["telegram_id"] = tg_id
        supabase.table("partners").insert(data).execute()
        
        bot_info = await bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={ref_code}"
        
        await message.answer(
            f"✅ Партнёр добавлен!\n\n"
            f"Имя: {name}\nКод: {ref_code}\nСсылка: {ref_link}",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", parse_mode="HTML")


@router.message(Command("partners"))
async def cmd_partners_stats(message: Message):
    if str(message.from_user.id) != ADMIN_TELEGRAM_ID:
        return
    
    try:
        partners = supabase.table("partners") \
            .select("id, name, ref_code, total_earned, total_paid, is_active") \
            .order("total_earned", desc=True).execute()
        
        if not partners.data:
            await message.answer("Партнёров пока нет")
            return
        
        referrals = supabase.table("referrals").select("partner_id").execute()
        ref_counts = {}
        for ref in referrals.data:
            pid = ref["partner_id"]
            ref_counts[pid] = ref_counts.get(pid, 0) + 1
        
        text = "📊 <b>Статистика партнёров</b>\n\n"
        for p in partners.data:
            status = "✅" if p["is_active"] else "⏸"
            balance = float(p["total_earned"] or 0) - float(p["total_paid"] or 0)
            ref_count = ref_counts.get(p["id"], 0)
            text += (
                f"{status} <b>{p['name']}</b> ({p['ref_code']})\n"
                f"   Рефералов: {ref_count}\n"
                f"   Заработано: {p['total_earned'] or 0}₽\n"
                f"   Выплачено: {p['total_paid'] or 0}₽\n"
                f"   К выплате: {balance:.2f}₽\n\n"
            )
        
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", parse_mode="HTML")


@router.message(Command("pay_partner"))
async def cmd_pay_partner(message: Message, command: CommandObject):
    if str(message.from_user.id) != ADMIN_TELEGRAM_ID:
        return
    
    args = command.args.split() if command.args else []
    if len(args) < 2:
        await message.answer(
            "📝 Формат: <code>/pay_partner ref_CODE сумма</code>\n\n"
            "Пример: <code>/pay_partner ref_IVAN 500</code>",
            parse_mode="HTML"
        )
        return
    
    ref_code = args[0]
    amount = float(args[1])
    
    try:
        partner = supabase.table("partners").select("id, total_paid").eq("ref_code", ref_code).execute()
        if not partner.data:
            await message.answer(f"❌ Партнёр {ref_code} не найден")
            return
        
        new_total = float(partner.data[0]["total_paid"] or 0) + amount
        supabase.table("partners").update({"total_paid": new_total}).eq("id", partner.data[0]["id"]).execute()
        await message.answer(f"✅ Выплата {amount}₽ партнёру {ref_code} отмечена")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


# ============================================
# ЗАПУСК БОТА
# ============================================

async def main():
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    await set_main_menu(bot)
    logging.info("🤖 Bot started with inline settings + /create wizard!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
