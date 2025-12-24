import os
import logging
from supabase import create_client, Client

# Инициализация Supabase
# Ключи берутся из переменных окружения (которые мы грузим в main)
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

supabase: Client = None
if url and key:
    try:
        supabase = create_client(url, key)
    except Exception as e:
        logging.error(f"Supabase Init Error: {e}")

def get_user_credits(email: str) -> int:
    """Возвращает баланс пользователя. Если юзера нет — создает с 5 кредитами."""
    if not supabase:
        return 5  # Режим без базы (тестовый)

    try:
        # Ищем пользователя
        response = supabase.table("users_credits").select("credits").eq("email", email).execute()
        
        # Если нашли — отдаем баланс
        if response.data:
            return response.data[0]["credits"]
        
        # Если не нашли — создаем нового
        else:
            supabase.table("users_credits").insert({"email": email, "credits": 5}).execute()
            return 5
            
    except Exception as e:
        logging.error(f"DB Error (get_credits): {e}")
        return 0

def deduct_credits(email: str, amount: int = 1):
    """Списывает кредиты у пользователя."""
    if not supabase:
        return

    try:
        # 1. Получаем текущий баланс
        current = get_user_credits(email)
        
        # 2. Вычитаем (не уходим в минус)
        new_balance = max(0, current - amount)
        
        # 3. Обновляем в базе
        supabase.table("users_credits").update({"credits": new_balance}).eq("email", email).execute()
        logging.info(f"Credits deducted for {email}. New balance: {new_balance}")
        
    except Exception as e:
        logging.error(f"DB Error (deduct_credits): {e}")

def check_password(email, password):
    """Проверка пароля админа (Заглушка для MVP)"""
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@vyud.tech")
    admin_pass = os.environ.get("ADMIN_PASSWORD", "admin123")
    
    if email == admin_email and password == admin_pass:
        return True
    return False