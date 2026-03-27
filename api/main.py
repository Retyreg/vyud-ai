"""
REST API для Mini App VYUD + Telegram Bot webhook.
Все API endpoints требуют заголовок x-api-key.
Бот работает через webhook — не нужен отдельный worker-процесс.
"""
import hashlib
import hmac
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import unquote, parse_qsl

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared.config import API_KEYS, TELEGRAM_BOT_TOKEN
from shared import supabase_client as db
import logic

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bot setup — защищённый импорт: API стартует даже если bot упал
# ---------------------------------------------------------------------------
_bot: Bot | None = None
_dp: Dispatcher | None = None

try:
    from bot.main import router as bot_router
    _bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
    _dp = Dispatcher()
    _dp.include_router(bot_router)
    log.info("Bot router loaded successfully")
except Exception as _bot_err:
    log.error("Bot failed to load (webhook will return 503): %s", _bot_err)

# Render автоматически задаёт RENDER_EXTERNAL_URL = https://vyud-api.onrender.com
WEBHOOK_BASE = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_PATH = "/bot/webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "vyud-webhook-secret")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: регистрируем webhook
    if WEBHOOK_BASE:
        webhook_url = f"{WEBHOOK_BASE}{WEBHOOK_PATH}"
        await _bot.set_webhook(webhook_url, secret_token=WEBHOOK_SECRET, drop_pending_updates=True)
        log.info("Webhook set: %s", webhook_url)
    else:
        log.warning("RENDER_EXTERNAL_URL не задан — webhook не зарегистрирован (локальная разработка?)")
    yield
    # Shutdown: удаляем webhook
    await _bot.delete_webhook()
    await _bot.session.close()


app = FastAPI(title="VYUD API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def verify_api_key(x_api_key: str = Header(...)):
    if API_KEYS and x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


def validate_init_data(init_data: str) -> dict | None:
    """
    HMAC-SHA256 валидация Telegram initData.
    Возвращает распарсенный словарь или None если невалидно.
    """
    if not init_data:
        return None
    try:
        parsed = dict(parse_qsl(unquote(init_data), keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None

        data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected, received_hash):
            return None
        return parsed
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ProfileRequest(BaseModel):
    telegram_id: int
    username: Optional[str] = None


class InvoiceRequest(BaseModel):
    telegram_id: int
    plan_id: str  # credits_10 | credits_50 | credits_100


class ProgressRequest(BaseModel):
    telegram_id: int
    quiz_id: str
    score: int
    total: int
    mastery_pct: int
    wrong_question_ids: list[int] = []


class GenerateQuizRequest(BaseModel):
    text: str
    count: int = 5
    difficulty: str = "Medium"
    lang: str = "Russian"
    telegram_id: int


# ---------------------------------------------------------------------------
# Credit plans (должны совпадать с PLANS в Dashboard.tsx)
# ---------------------------------------------------------------------------

PLANS = {
    "credits_10":  {"base": 10, "bonus": 1,  "price_xtr": 50},
    "credits_50":  {"base": 50, "bonus": 12, "price_xtr": 200},
    "credits_100": {"base": 100, "bonus": 50, "price_xtr": 500},
}

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """Принимает обновления от Telegram и передаёт aiogram."""
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    from aiogram.types import Update
    data = await request.json()
    update = Update.model_validate(data)
    await _dp.feed_update(bot=_bot, update=update)
    return {"ok": True}


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/api/profile")
async def get_profile(
    req: ProfileRequest,
    x_api_key: str = Depends(verify_api_key),
    x_telegram_init_data: str = Header(default=""),
):
    """
    Возвращает профиль пользователя, создаёт если не существует.
    initData валидируется когда передан (в dev-режиме можно без него).
    """
    # Валидация initData (пропускаем если пустой — dev/fallback)
    if x_telegram_init_data:
        parsed = validate_init_data(x_telegram_init_data)
        if parsed is None:
            raise HTTPException(status_code=403, detail="Invalid Telegram initData")

    user = db.get_or_create_user(req.telegram_id, req.username)
    return {
        "success": True,
        "credits": user.get("credits", 0),
        "current_streak": user.get("current_streak", 0),
        "total_generations": user.get("total_generations", 0),
        "username": user.get("username"),
    }


@app.post("/api/invoice")
async def create_invoice(
    req: InvoiceRequest,
    x_api_key: str = Depends(verify_api_key),
    x_telegram_init_data: str = Header(default=""),
):
    """
    Создаёт инвойс Telegram Stars через Bot API.
    Возвращает invoice_link для передачи в WebApp.openInvoice().
    """
    if x_telegram_init_data:
        parsed = validate_init_data(x_telegram_init_data)
        if parsed is None:
            raise HTTPException(status_code=403, detail="Invalid Telegram initData")

    plan = PLANS.get(req.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan_id: {req.plan_id}")

    total_credits = plan["base"] + plan["bonus"]

    import aiohttp
    async with aiohttp.ClientSession() as session:
        payload = {
            "chat_id": req.telegram_id,
            "title": f"VYUD AI — {total_credits} кредитов",
            "description": f"{plan['base']} кредитов + {plan['bonus']} бонусных ({plan['bonus'] * 100 // plan['base']}%)",
            "payload": f"{req.plan_id}:{req.telegram_id}",
            "currency": "XTR",
            "prices": [{"label": f"{total_credits} кредитов", "amount": plan["price_xtr"]}],
        }
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/createInvoiceLink"
        async with session.post(url, json=payload) as resp:
            data = await resp.json()

    if not data.get("ok"):
        raise HTTPException(status_code=502, detail=f"Telegram API error: {data.get('description')}")

    return {"success": True, "invoice_link": data["result"]}


@app.post("/api/progress")
async def save_progress(
    req: ProgressRequest,
    x_api_key: str = Depends(verify_api_key),
    x_telegram_init_data: str = Header(default=""),
):
    """Сохраняет результат прохождения теста в user_progress."""
    if x_telegram_init_data:
        parsed = validate_init_data(x_telegram_init_data)
        if parsed is None:
            raise HTTPException(status_code=403, detail="Invalid Telegram initData")

    db.save_progress(
        telegram_id=req.telegram_id,
        quiz_id=req.quiz_id,
        score=req.score,
        total=req.total,
        mastery_pct=req.mastery_pct,
        wrong_question_ids=req.wrong_question_ids,
    )
    return {"success": True}


@app.post("/api/generate-quiz")
async def generate_quiz(
    req: GenerateQuizRequest,
    x_api_key: str = Depends(verify_api_key),
    x_telegram_init_data: str = Header(default=""),
):
    """Генерирует квиз из текста, списывает 1 кредит."""
    if x_telegram_init_data:
        parsed = validate_init_data(x_telegram_init_data)
        if parsed is None:
            raise HTTPException(status_code=403, detail="Invalid Telegram initData")

    if db.get_credits(req.telegram_id) <= 0:
        raise HTTPException(status_code=402, detail="Недостаточно кредитов")

    if len(req.text.strip()) < 50:
        raise HTTPException(status_code=400, detail="Текст слишком короткий (минимум 50 символов)")

    if req.count < 3 or req.count > 15:
        raise HTTPException(status_code=400, detail="count должен быть от 3 до 15")

    quiz_data = logic.generate_quiz_ai(req.text, req.count, req.difficulty, req.lang)

    db.deduct_credit(req.telegram_id, 1)
    db.increment_generations(req.telegram_id)

    return {
        "success": True,
        "questions": [
            {
                "scenario": q.scenario,
                "options": q.options,
                "correct_option_id": q.correct_option_id,
                "explanation": q.explanation,
            }
            for q in quiz_data.questions
        ],
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
