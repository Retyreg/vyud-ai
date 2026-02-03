import os
import time
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from supabase import create_client, Client
from postgrest.exceptions import APIError

# Настройка логгера для отладки инцидентов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SupabaseClient")

# Получаем секреты (поддержка и Streamlit secrets, и ENV для Systemd)
def get_secret(key):
    # Пытаемся взять из Streamlit (локально/cloud)
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except ImportError:
        pass
    # Пытаемся взять из переменных окружения (VPS/Systemd)
    return os.getenv(key)

URL = get_secret("SUPABASE_URL")
KEY = get_secret("SUPABASE_KEY") # Обычно это SERVICE_ROLE для backend-операций

if not URL or not KEY:
    raise ValueError("CRITICAL: Supabase credentials not found!")

# Инициализация клиента
supabase: Client = create_client(URL, KEY)

# --- RETRY LOGIC ---
# Ждем 2^x * 1 секунду. Максимум 10 секунд. Делаем 5 попыток.
# Это спасет от кратковременных падений Supavisor
RETRY_STRATEGY = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((APIError, ConnectionError, TimeoutError)),
    before_sleep=lambda retry_state: logger.warning(f"Supabase connection glitch. Retrying... {retry_state.attempt_number}")
)

class Database:
    """Обертка для надежной работы с данными"""

    @staticmethod
    @RETRY_STRATEGY
    def get_user(email: str):
        """Получает пользователя с защитой от сбоев"""
        try:
            # Используем single(), чтобы получить один объект или ошибку
            response = supabase.table("users_credits").select("*").eq("email", email).execute()
            # В supabase-py v2 response.data - это список
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching user {email}: {e}")
            raise e # Пробрасываем, чтобы сработал retry

    @staticmethod
    @RETRY_STRATEGY
    def create_user(email: str, default_credits: int = 3):
        """Создает пользователя, если его нет"""
        try:
            data = {"email": email, "credits": default_credits}
            supabase.table("users_credits").insert(data).execute()
            logger.info(f"New user created: {email}")
        except APIError as e:
            # Игнорируем ошибку дубликата, если вдруг возникла гонка
            if "duplicate key" not in str(e):
                raise e

    @staticmethod
    @RETRY_STRATEGY
    def deduct_credit(email: str) -> bool:
        """Списывает кредит атомарно (или через проверку)"""
        user = Database.get_user(email)
        if user and user['credits'] > 0:
            new_balance = user['credits'] - 1
            supabase.table("users_credits").update({"credits": new_balance}).eq("email", email).execute()
            return True
        return False

# Экспортируем экземпляр для удобства
db = Database()
