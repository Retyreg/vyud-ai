"""
VYUD AI — Prodamus Webhook Server
Автоматическое начисление кредитов после оплаты

Запуск: python webhook_prodamus.py
Порт: 8502
Endpoint: POST /webhook/prodamus

Конфигурация через .env или secrets.toml
"""

import hashlib
import hmac
import json
import os
import asyncio
from datetime import datetime, timedelta
from aiohttp import web
import aiohttp
from pathlib import Path

# ============================================================
# ЗАГРУЗКА КОНФИГУРАЦИИ
# ============================================================

def load_config():
    """
    Загружает конфигурацию из:
    1. .env файла (если есть)
    2. .streamlit/secrets.toml (если есть)
    3. Переменных окружения
    """
    config = {}
    
    # Попытка загрузить из .env
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip().strip('"').strip("'")
    
    # Попытка загрузить из secrets.toml
    secrets_path = Path(".streamlit/secrets.toml")
    if secrets_path.exists():
        try:
            import toml
            secrets = toml.load(secrets_path)
            config.update(secrets)
        except ImportError:
            pass  # toml не установлен
    
    # Переменные окружения имеют приоритет
    for key in ["PRODAMUS_SECRET_KEY", "SUPABASE_URL", "SUPABASE_KEY", 
                "TELEGRAM_BOT_TOKEN", "ADMIN_CHAT_ID"]:
        if os.getenv(key):
            config[key] = os.getenv(key)
    
    return config

CONFIG = load_config()

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

PRODAMUS_SECRET_KEY = CONFIG.get("PRODAMUS_SECRET_KEY", "")
SUPABASE_URL = CONFIG.get("SUPABASE_URL", "")
SUPABASE_KEY = CONFIG.get("SUPABASE_KEY", "")
TELEGRAM_BOT_TOKEN = CONFIG.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = CONFIG.get("ADMIN_CHAT_ID", "")

# ============================================================
# ТАРИФЫ VYUD AI
# ============================================================

PRODUCTS = {
    "starter": {
        "price_rub": 490,
        "credits": 20,
        "duration_days": None,  # Разовая покупка
        "name_ru": "Starter",
        "description": "20 генераций, базовые функции"
    },
    "pro": {
        "price_rub": 1490,
        "credits": 100,
        "duration_days": None,  # Разовая покупка
        "name_ru": "Pro",
        "description": "100 генераций, все форматы файлов"
    },
    "unlimited": {
        "price_rub": 2990,
        "credits": 999999,  # Безлимит
        "duration_days": 30,  # Подписка на месяц
        "name_ru": "Unlimited",
        "description": "Безлимит, до 10 пользователей"
    },
}

# ============================================================
# SUPABASE CLIENT
# ============================================================

_supabase_client = None

def get_supabase():
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


# ============================================================
# ВЕРИФИКАЦИЯ ПОДПИСИ PRODAMUS
# ============================================================

def verify_prodamus_signature(data: dict, signature: str) -> bool:
    """
    Prodamus использует HMAC-SHA256 для подписи webhook'ов.
    Документация: https://help.prodamus.ru/payform/integracii/webhook
    """
    if not signature or not PRODAMUS_SECRET_KEY:
        print("[WARN] No signature or secret key configured")
        return False
    
    # Убираем signature из данных для проверки
    data_to_check = {k: v for k, v in data.items() if k != "signature"}
    
    # Сортируем по ключам и формируем строку
    sorted_items = sorted(data_to_check.items())
    check_string = "&".join(f"{k}={v}" for k, v in sorted_items)
    
    expected = hmac.new(
        PRODAMUS_SECRET_KEY.encode("utf-8"),
        check_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected.lower(), signature.lower())


# ============================================================
# НАЧИСЛЕНИЕ КРЕДИТОВ
# ============================================================

async def process_payment(email: str, product_key: str, order_id: str) -> dict:
    """
    Начисляет кредиты пользователю.
    Возвращает информацию о результате.
    """
    supabase = get_supabase()
    product = PRODUCTS.get(product_key)
    
    if not product:
        # Fallback — Starter
        product = PRODUCTS["starter"]
        product_key = "starter"
    
    credits_to_add = product["credits"]
    
    # Для подписки (Unlimited) устанавливаем срок действия
    expires_at = None
    if product["duration_days"]:
        expires_at = datetime.utcnow() + timedelta(days=product["duration_days"])
    
    # Проверяем существует ли пользователь
    result = supabase.table("users_credits").select("*").eq("email", email).execute()
    
    if result.data:
        # Пользователь существует — добавляем кредиты
        current = result.data[0]
        new_credits = current.get("credits", 0) + credits_to_add
        
        update_data = {
            "credits": new_credits,
            "last_payment_at": datetime.utcnow().isoformat(),
            "last_product": product_key
        }
        
        if expires_at:
            update_data["subscription_expires"] = expires_at.isoformat()
        
        supabase.table("users_credits").update(update_data).eq("email", email).execute()
        previous_credits = current.get("credits", 0)
    else:
        # Новый пользователь
        insert_data = {
            "email": email,
            "credits": credits_to_add,
            "last_payment_at": datetime.utcnow().isoformat(),
            "last_product": product_key,
            "created_at": datetime.utcnow().isoformat()
        }
        
        if expires_at:
            insert_data["subscription_expires"] = expires_at.isoformat()
        
        supabase.table("users_credits").insert(insert_data).execute()
        previous_credits = 0
        new_credits = credits_to_add
    
    # Логируем платёж
    try:
        supabase.table("payments_log").insert({
            "email": email,
            "order_id": order_id,
            "product": product_key,
            "credits_added": credits_to_add,
            "amount_rub": product.get("price_rub", 0),
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"[WARN] Не удалось залогировать платёж: {e}")
    
    return {
        "email": email,
        "product": product,
        "product_key": product_key,
        "credits_added": credits_to_add,
        "previous_credits": previous_credits,
        "new_credits": new_credits,
        "expires_at": expires_at,
        "order_id": order_id
    }


# ============================================================
# УВЕДОМЛЕНИЯ
# ============================================================

async def get_user_chat_id(email: str) -> str | None:
    """Получает Telegram chat_id пользователя по email."""
    try:
        supabase = get_supabase()
        result = supabase.table("users").select("telegram_chat_id").eq("email", email).execute()
        if result.data and result.data[0].get("telegram_chat_id"):
            return str(result.data[0]["telegram_chat_id"])
    except Exception as e:
        print(f"[WARN] Не удалось получить chat_id для {email}: {e}")
    return None


async def send_telegram_message(chat_id: str, text: str):
    """Отправляет сообщение в Telegram."""
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            })
    except Exception as e:
        print(f"[WARN] Telegram send failed: {e}")


async def notify_all(payment_info: dict):
    """
    Отправляет уведомления:
    1. Telegram пользователю (если есть chat_id)
    2. Telegram админу
    """
    email = payment_info["email"]
    product = payment_info["product"]
    credits = payment_info["credits_added"]
    new_balance = payment_info["new_credits"]
    expires = payment_info["expires_at"]
    order_id = payment_info["order_id"]
    
    # 1. Telegram пользователю
    user_chat_id = await get_user_chat_id(email)
    if user_chat_id:
        expires_text = f"\n📅 Действует до: {expires.strftime('%d.%m.%Y')}" if expires else ""
        user_msg = (
            f"🎉 <b>Оплата прошла успешно!</b>\n\n"
            f"📦 Тариф: <b>{product['name_ru']}</b>\n"
            f"⚡ Начислено: <b>+{credits}</b> кредитов\n"
            f"💰 Ваш баланс: <b>{new_balance}</b> кредитов"
            f"{expires_text}\n\n"
            f"Спасибо, что выбрали VYUD AI! 🚀\n"
            f"Начать генерацию → /start"
        )
        await send_telegram_message(user_chat_id, user_msg)
    
    # 2. Telegram админу
    if ADMIN_CHAT_ID:
        admin_msg = (
            f"💰 <b>Новая оплата VYUD AI!</b>\n\n"
            f"📧 <code>{email}</code>\n"
            f"📦 {product['name_ru']} ({product.get('price_rub', '?')}₽)\n"
            f"⚡ +{credits} → баланс {new_balance}\n"
            f"🆔 {order_id}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}"
        )
        await send_telegram_message(ADMIN_CHAT_ID, admin_msg)


# ============================================================
# WEBHOOK HANDLER
# ============================================================

async def handle_prodamus_webhook(request: web.Request) -> web.Response:
    """
    Главный обработчик webhook от Prodamus.
    """
    try:
        # Получаем данные из POST
        if request.content_type == "application/json":
            data = await request.json()
        else:
            data = dict(await request.post())
        
        print(f"\n{'='*50}")
        print(f"[WEBHOOK] {datetime.now().isoformat()}")
        print(f"[WEBHOOK] Data: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Проверяем подпись
        signature = data.get("signature", "")
        if not verify_prodamus_signature(data, signature):
            print("[WEBHOOK] ❌ Invalid signature!")
            return web.Response(status=403, text="Invalid signature")
        
        # Проверяем статус
        status = data.get("payment_status", "")
        if status != "success":
            print(f"[WEBHOOK] Status is '{status}', skipping")
            return web.Response(status=200, text="OK, not success")
        
        # Извлекаем данные
        email = data.get("customer_email", "").lower().strip()
        product_name = data.get("product_name", "").lower()
        order_id = data.get("order_id", f"unknown_{datetime.now().timestamp()}")
        
        if not email:
            print("[WEBHOOK] ❌ No email!")
            return web.Response(status=400, text="No email")
        
        # Определяем продукт по названию
        product_key = "starter"  # default
        if "unlimited" in product_name:
            product_key = "unlimited"
        elif "pro" in product_name:
            product_key = "pro"
        elif "starter" in product_name:
            product_key = "starter"
        
        # Начисляем кредиты
        payment_info = await process_payment(email, product_key, order_id)
        
        print(f"[WEBHOOK] ✅ {email} +{payment_info['credits_added']} credits ({product_key})")
        print(f"[WEBHOOK] New balance: {payment_info['new_credits']}")
        
        # Отправляем уведомления (асинхронно)
        asyncio.create_task(notify_all(payment_info))
        
        return web.Response(status=200, text="OK")
        
    except Exception as e:
        print(f"[WEBHOOK] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return web.Response(status=500, text=f"Error: {e}")


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ENDPOINTS
# ============================================================

async def health_check(request: web.Request) -> web.Response:
    """Health check для мониторинга."""
    return web.json_response({
        "status": "ok",
        "service": "vyud-webhook",
        "timestamp": datetime.utcnow().isoformat(),
        "config": {
            "prodamus_configured": bool(PRODAMUS_SECRET_KEY),
            "supabase_configured": bool(SUPABASE_URL and SUPABASE_KEY),
            "telegram_configured": bool(TELEGRAM_BOT_TOKEN),
            "admin_notifications": bool(ADMIN_CHAT_ID)
        }
    })


async def test_webhook(request: web.Request) -> web.Response:
    """
    Тестовый endpoint для проверки без Prodamus.
    POST /test с JSON: {"email": "test@example.com", "product": "pro"}
    """
    try:
        data = await request.json()
        email = data.get("email", "test@example.com")
        product_key = data.get("product", "starter")
        
        payment_info = await process_payment(email, product_key, f"test_{datetime.now().timestamp()}")
        await notify_all(payment_info)
        
        return web.json_response({
            "status": "ok",
            "payment_info": {
                "email": payment_info["email"],
                "product": payment_info["product_key"],
                "credits_added": payment_info["credits_added"],
                "new_balance": payment_info["new_credits"]
            }
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


# ============================================================
# APP FACTORY
# ============================================================

def create_app() -> web.Application:
    app = web.Application()
    
    app.router.add_post("/webhook/prodamus", handle_prodamus_webhook)
    app.router.add_get("/health", health_check)
    app.router.add_post("/test", test_webhook)  # Убрать на проде!
    
    return app


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 VYUD Webhook Server")
    print("=" * 50)
    print(f"Port: 8502")
    print(f"Endpoints:")
    print(f"  POST /webhook/prodamus — Prodamus callbacks")
    print(f"  GET  /health          — Health check")
    print(f"  POST /test            — Test payment (dev only)")
    print("=" * 50)
    print(f"Config status:")
    print(f"  Prodamus Secret: {'✅ configured' if PRODAMUS_SECRET_KEY else '❌ missing'}")
    print(f"  Supabase: {'✅ configured' if SUPABASE_URL else '❌ missing'}")
    print(f"  Telegram Bot: {'✅ configured' if TELEGRAM_BOT_TOKEN else '❌ missing'}")
    print(f"  Admin Chat ID: {'✅ configured' if ADMIN_CHAT_ID else '❌ missing'}")
    print("=" * 50)
    
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=8502)
