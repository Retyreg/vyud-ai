import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

# --- 1. ПОДКЛЮЧЕНИЕ К SUPABASE ---
try:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    else:
        supabase = None
except Exception as e:
    # Если ключей нет, работаем в демо-режиме (без базы)
    print(f"⚠️ Supabase error: {e}")
    supabase = None

# --- 2. АВТОРИЗАЦИЯ ---
def check_password(email, password):
    """
    Простая проверка. Админа пускаем по паролю,
    обычных пользователей — просто по email (для MVP).
    """
    # Админ (данные в env)
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_pass = os.getenv("ADMIN_PASSWORD")

    if admin_email and admin_pass and email == admin_email and password == admin_pass:
        return True
    
    # Для MVP пускаем всех, кто ввел email
    if email:
        return True
        
    return False

# --- 3. БАЛАНС И СПИСАНИЕ ---

def get_credits(email):
    """Получить текущий баланс. Если юзера нет — создать."""
    if not supabase: return 999 # Если базы нет, даем безлимит
    
    try:
        # Ищем юзера
        response = supabase.table("users_credits").select("credits").eq("email", email).execute()
        
        # Если не найден — создаем с приветственным бонусом (5 кредитов)
        if not response.data:
            init_credits = 5
            supabase.table("users_credits").insert({"email": email, "credits": init_credits}).execute()
            return init_credits
            
        return response.data[0]["credits"]
    except Exception as e:
        print(f"Ошибка получения кредитов: {e}")
        return 0

def deduct_credit(email, amount=1):
    """
    Списывает кредиты.
    Возвращает True (успех) или False (нет денег).
    """
    if not supabase: return True # Если базы нет, разрешаем

    try:
        current = get_credits(email)
        
        if current < amount:
            return False # Недостаточно средств
        
        # Списываем
        new_balance = current - amount
        supabase.table("users_credits").update({"credits": new_balance}).eq("email", email).execute()
        return True
    except Exception as e:
        print(f"Ошибка списания: {e}")
        return False