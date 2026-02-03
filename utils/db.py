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
    wait=wait_exponential(multiplier=1, min=1, max=10),
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
    def get_user_by_telegram_id(telegram_id: int):
        """Получает пользователя по Telegram ID с защитой от сбоев"""
        try:
            response = supabase.table("users_credits").select("*").eq("telegram_id", telegram_id).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching user by telegram_id {telegram_id}: {e}")
            raise e

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
    def get_user_credits(email: str) -> int:
        """Получает баланс кредитов пользователя"""
        try:
            response = supabase.table("users_credits").select("credits").eq("email", email).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]["credits"]
            return 0
        except Exception as e:
            logger.error(f"Error getting credits for {email}: {e}")
            raise e

    @staticmethod
    @RETRY_STRATEGY
    def deduct_credit(email: str, amount: int = 1) -> bool:
        """
        Списывает кредиты (или через проверку).
        Note: Not fully atomic - race conditions possible in high concurrency scenarios.
        For production, consider using database-level transactions or atomic UPDATE with WHERE.
        """
        try:
            current = Database.get_user_credits(email)
            if current >= amount:
                new_balance = current - amount
                supabase.table("users_credits").update({"credits": new_balance}).eq("email", email).execute()
                logger.info(f"Deducted {amount} credits from {email}. New balance: {new_balance}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deducting credits from {email}: {e}")
            raise e

    @staticmethod
    @RETRY_STRATEGY
    def add_credits(email: str, amount: int) -> bool:
        """
        Добавляет кредиты пользователю.
        Note: Not fully atomic - race conditions possible in high concurrency scenarios.
        """
        try:
            result = supabase.table("users_credits").select("credits").eq("email", email).execute()
            if result.data and len(result.data) > 0:
                new_balance = result.data[0]["credits"] + amount
                supabase.table("users_credits").update({"credits": new_balance}).eq("email", email).execute()
                logger.info(f"Added {amount} credits to {email}. New balance: {new_balance}")
            else:
                # Пользователь не существует, создаем с указанным балансом
                supabase.table("users_credits").insert({"email": email, "credits": amount}).execute()
                logger.info(f"Created user {email} with {amount} credits")
            return True
        except Exception as e:
            logger.error(f"Error adding credits to {email}: {e}")
            raise e

    @staticmethod
    @RETRY_STRATEGY
    def save_quiz(user_email: str, title: str, questions, hints=""):
        """Сохраняет тест в БД"""
        try:
            import uuid
            import json
            from datetime import datetime
            
            test_id = str(uuid.uuid4())[:8]
            
            data = {
                "id": test_id,
                "owner_email": user_email,
                "title": title,
                "questions": json.dumps(questions) if isinstance(questions, list) else questions,
                "hints": hints or "",
                "created_at": datetime.utcnow().isoformat(),
                "is_public": False
            }
            supabase.table("quizzes").insert(data).execute()
            logger.info(f"Quiz saved: {test_id} for {user_email}")
            return test_id
        except Exception as e:
            logger.error(f"Error saving quiz for {user_email}: {e}")
            raise e

    @staticmethod
    @RETRY_STRATEGY
    def get_user_quizzes(user_email: str, limit: int = 50):
        """Получает все тесты пользователя"""
        try:
            result = supabase.table("quizzes")\
                .select("*")\
                .eq("owner_email", user_email)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error getting quizzes for {user_email}: {e}")
            raise e

    @staticmethod
    @RETRY_STRATEGY
    def get_quiz_by_id(quiz_id: str):
        """Получает тест по ID"""
        try:
            import json
            result = supabase.table("quizzes")\
                .select("*")\
                .eq("id", quiz_id)\
                .single()\
                .execute()
            
            if result.data and result.data.get("questions"):
                if isinstance(result.data["questions"], str):
                    result.data["questions"] = json.loads(result.data["questions"])
            
            return result.data if result.data else None
        except Exception as e:
            logger.error(f"Error getting quiz {quiz_id}: {e}")
            raise e

    @staticmethod
    @RETRY_STRATEGY
    def get_public_test(slug: str):
        """Получает публичный тест по slug"""
        try:
            import json
            result = supabase.table("quizzes")\
                .select("*")\
                .eq("id", slug)\
                .eq("is_public", True)\
                .single()\
                .execute()
            
            if result.data and result.data.get("questions"):
                if isinstance(result.data["questions"], str):
                    result.data["questions"] = json.loads(result.data["questions"])
            
            return result.data if result.data else None
        except Exception as e:
            logger.error(f"Error getting public test {slug}: {e}")
            raise e

    @staticmethod
    @RETRY_STRATEGY
    def upsert_user(user_data: dict):
        """Создает или обновляет пользователя"""
        try:
            supabase.table("users_credits").upsert(user_data, on_conflict="telegram_id").execute()
            logger.info(f"User upserted: {user_data.get('email')}")
            return True
        except Exception as e:
            logger.error(f"Error upserting user: {e}")
            raise e

    @staticmethod
    @RETRY_STRATEGY
    def insert_generation_log(telegram_id: int, email: str, generation_type: str):
        """Записывает лог генерации"""
        try:
            supabase.table("generation_logs").insert({
                "telegram_id": telegram_id,
                "email": email,
                "generation_type": generation_type
            }).execute()
            logger.info(f"Generation log inserted for {email}")
            return True
        except Exception as e:
            logger.error(f"Error inserting generation log: {e}")
            raise e

    @staticmethod
    @RETRY_STRATEGY
    def get_all_users():
        """Получает всех пользователей (для админки)"""
        try:
            result = supabase.table("users_credits").select("*").execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            raise e

# Экспортируем экземпляр для удобства
db = Database()
