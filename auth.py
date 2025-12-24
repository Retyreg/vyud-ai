import os
import logging
from supabase import create_client, Client

# Инициализация Supabase
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

supabase: Client = None
if url and key:
    try:
        supabase = create_client(url, key)
    except Exception as e:
        logging.error(f"Supabase Init Error: {e}")

def get_user_credits(email: str) -> int:
    """Возвращает баланс пользователя."""
    if not supabase:
        return 5 

    try:
        response = supabase.table("users_credits").select("credits").eq("email", email).execute()
        if response.data:
            return response.data[0]["credits"]
        else:
            # Создаем нового пользователя с бонусом
            supabase.table("users_credits").insert({"email": email, "credits": 5}).execute()
            return 5
    except Exception as e:
        logging.error(f"DB Error (get_credits): {e}")
        return 0

def deduct_credits(email: str, amount: int = 1):
    """Списывает кредиты."""
    if not supabase:
        return

    try:
        current = get_user_credits(email)
        new_balance = max(0, current - amount)
        supabase.table("users_credits").update({"credits": new_balance}).eq("email", email).execute()
    except Exception as e:
        logging.error(f"DB Error (deduct_credits): {e}")

def check_password(email, password):
    """Проверка пароля (Заглушка + Админ)."""
    # 1. Хардкод админа
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@vyud.tech")
    admin_pass = os.environ.get("ADMIN_PASSWORD", "admin123")
    
    if email == admin_email and password == admin_pass:
        return True
    
    # 2. Для обычных юзеров в MVP пускаем всех, у кого пароль не пустой
    # (В будущем здесь будет supabase.auth.sign_in)
    if password and len(password) > 3:
        return True
        
    return False

# --- НОВАЯ ФУНКЦИЯ ДЛЯ APP.PY ---
def login_user(email, password):
    """
    Пытается залогинить юзера. 
    Возвращает словарь user (или None), чтобы app.py мог сохранить его в session_state.
    """
    if check_password(email, password):
        # Возвращаем объект пользователя
        return {"email": email, "role": "user"}
    
    return None