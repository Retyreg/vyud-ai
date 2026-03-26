"""
Telegram-бот VYUD AI.
Отвечает за: приём файлов, AI-генерацию, платежи Telegram Stars.
Общается с Mini App только через Supabase — никаких прямых HTTP-вызовов.
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from shared.config import TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, LLAMA_CLOUD_API_KEY
from shared import supabase_client as db
import logic

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

router = Router()
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# ---------------------------------------------------------------------------
# Credit plans (зеркало Dashboard.tsx PLANS и api/main.py PLANS)
# ---------------------------------------------------------------------------
PLANS = {
    "credits_10":  {"base": 10, "bonus": 1,  "price_xtr": 50,  "label": "Стартовый"},
    "credits_50":  {"base": 50, "bonus": 12, "price_xtr": 200, "label": "Оптимальный"},
    "credits_100": {"base": 100, "bonus": 50, "price_xtr": 500, "label": "Профи"},
}

# ---------------------------------------------------------------------------
# Вспомогательные классы
# ---------------------------------------------------------------------------

class LocalFileWrapper:
    """Обёртка для локального файла, совместимая с logic.process_file_to_text."""
    def __init__(self, path: str):
        self.name = path
        with open(path, "rb") as f:
            self._data = f.read()

    def getvalue(self) -> bytes:
        return self._data

# ---------------------------------------------------------------------------
# Команды
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(m: Message):
    args = m.text.split(maxsplit=1)[1] if len(m.text.split()) > 1 else ""

    user = db.get_or_create_user(m.from_user.id, m.from_user.username)

    # Реферальная программа: start=inv_<referrer_id>
    if args.startswith("inv_"):
        try:
            referrer_id = int(args[4:])
            if referrer_id != m.from_user.id:
                db.add_credits(referrer_id, 2)   # рефереру +2
                db.add_credits(m.from_user.id, 1) # новому +1
                await m.answer(
                    "🎁 Вы пришли по реферальной ссылке — вам начислен +1 бонусный кредит!\n\n"
                    "Отправьте файл (PDF/DOCX), голосовое или видео, и я создам тест."
                )
                return
        except ValueError:
            pass

    mini_app_url = "https://vyud-tma.vercel.app"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📱 Открыть Mini App", web_app={"url": mini_app_url})
    ]])
    await m.answer(
        f"👋 Привет, {m.from_user.first_name}!\n\n"
        f"Я VYUD AI — превращаю лекции, PDF и аудио в интерактивные тесты.\n\n"
        f"💳 Баланс: *{user.get('credits', 0)} кредитов*\n\n"
        f"Пришли файл прямо сюда или открой Mini App:",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


@router.message(Command("balance"))
async def cmd_balance(m: Message):
    credits = db.get_credits(m.from_user.id)
    streak = db.get_or_create_user(m.from_user.id).get("current_streak", 0)
    await m.answer(
        f"💳 Баланс: *{credits} кредитов*\n"
        f"🔥 Серия: *{streak} дней*",
        parse_mode="Markdown",
    )

# ---------------------------------------------------------------------------
# Обработка файлов → генерация квиза
# ---------------------------------------------------------------------------

@router.message(F.video_note | F.voice | F.audio | F.video | F.document)
async def handle_files(m: Message):
    telegram_id = m.from_user.id

    if db.get_credits(telegram_id) <= 0:
        await m.answer("🚫 Недостаточно кредитов.\n\nКупи кредиты в Mini App (/start).")
        return

    msg = await m.answer("📥 Скачиваю файл...")

    if m.video_note:   fid = m.video_note.file_id
    elif m.voice:      fid = m.voice.file_id
    elif m.audio:      fid = m.audio.file_id
    elif m.video:      fid = m.video.file_id
    elif m.document:   fid = m.document.file_id
    else:              return

    path = f"/tmp/vyud_{telegram_id}_{fid}"

    try:
        f_info = await bot.get_file(fid)
        ext = f_info.file_path.rsplit(".", 1)[-1]
        path = f"{path}.{ext}"
        await bot.download_file(f_info.file_path, path)

        await bot.edit_message_text("👂 Изучаю содержимое...", m.chat.id, msg.message_id)
        text = await asyncio.to_thread(
            logic.process_file_to_text, LocalFileWrapper(path), OPENAI_API_KEY, LLAMA_CLOUD_API_KEY
        )

        if not text:
            await bot.edit_message_text("❌ Не удалось извлечь текст из файла.", m.chat.id, msg.message_id)
            return

        await bot.edit_message_text("🧠 Генерирую вопросы...", m.chat.id, msg.message_id)
        quiz = await asyncio.to_thread(logic.generate_quiz_ai, text=text, count=5, difficulty="Medium", lang="Russian")

        db.deduct_credit(telegram_id, 1)
        db.increment_generations(telegram_id)  # стрик + счётчик + бонус каждые 5 дней

        await bot.delete_message(m.chat.id, msg.message_id)
        await m.answer("✅ Готово! Вот ваш тест:")

        for q in quiz.questions:
            try:
                await bot.send_poll(
                    chat_id=m.chat.id,
                    question=q.scenario[:299],
                    options=[o[:99] for o in q.options],
                    type="quiz",
                    correct_option_id=q.correct_option_id,
                    explanation=q.explanation[:199],
                )
                await asyncio.sleep(0.5)
            except Exception as e:
                log.error("Poll error: %s", e)

    except Exception as e:
        log.error("handle_files error: %s", e)
        await m.answer(f"❌ Ошибка: {e}")
    finally:
        if os.path.exists(path):
            os.remove(path)

# ---------------------------------------------------------------------------
# Telegram Stars — платежи
# ---------------------------------------------------------------------------

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    """Всегда подтверждаем — реальная валидация в successful_payment."""
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(m: Message):
    """
    Зачисляем кредиты после успешной оплаты.
    payload формат: "credits_10:123456789"
    """
    payment = m.successful_payment
    try:
        plan_id, paid_telegram_id_str = payment.invoice_payload.split(":")
        paid_telegram_id = int(paid_telegram_id_str)
    except (ValueError, AttributeError):
        log.error("Bad payment payload: %s", payment.invoice_payload)
        await m.answer("✅ Оплата получена! Кредиты будут зачислены в ближайшее время.")
        return

    plan = PLANS.get(plan_id)
    if not plan:
        log.error("Unknown plan_id in payment: %s", plan_id)
        return

    total = plan["base"] + plan["bonus"]
    new_balance = db.add_credits(paid_telegram_id, total)

    log.info("Payment success: user=%s plan=%s credits_added=%s new_balance=%s",
             paid_telegram_id, plan_id, total, new_balance)

    await m.answer(
        f"🎉 Оплата прошла успешно!\n\n"
        f"✨ Зачислено: *+{total} кредитов* ({plan['base']} + {plan['bonus']} бонус)\n"
        f"💳 Новый баланс: *{new_balance} кредитов*\n\n"
        f"Откройте Mini App — баланс уже обновился.",
        parse_mode="Markdown",
    )

# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------

async def main():
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    log.info("🤖 VYUD Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
