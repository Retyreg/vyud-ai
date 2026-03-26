"""
Единая загрузка конфигурации из переменных окружения.
Поддерживает .env файл для локальной разработки и Railway env vars для продакшна.
"""
import os
from pathlib import Path

# Загружаем .env если существует (локальная разработка)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# Telegram
TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]

# OpenAI / LlamaCloud
OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
LLAMA_CLOUD_API_KEY: str = os.getenv("LLAMA_CLOUD_API_KEY", "")

# Supabase
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]          # service_role key (для бота и API)
SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", SUPABASE_KEY)

# API security
# Список допустимых ключей для Mini App → API, через запятую
API_KEYS: list[str] = [
    k.strip()
    for k in os.getenv("API_KEYS", "").split(",")
    if k.strip()
]

# Stars payments
PAYMENT_PROVIDER_TOKEN: str = os.getenv("PAYMENT_PROVIDER_TOKEN", "")  # пустой = XTR (Telegram Stars)
