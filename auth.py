import streamlit as st
from supabase import create_client
import os

# --- 1. ПОДКЛЮЧЕНИЕ К SUPABASE ---
try:
    # Пытаемся взять из Streamlit Secrets (для сайта)
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except:
    # Если не вышло (например, запускает бот), берем из ENV
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# Инициализация клиента
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None
    print("⚠️ WARNING: Supabase keys not found!")

# --- 2. ФУНКЦИИ АВТОРИЗАЦИИ (AUTH) ---

def register_user(email, password):
    """Регистрация нового пользователя в Supabase Auth + начисление кредитов."""
    if not supabase: return False
    try:
        # 1. Создаем пользователя в Auth
        res = supabase.auth.sign_up({
            "email": email, 
            "password": password
        })
        
        # 2. Если успешно — создаем запись в таблице кредитов
        if res.user:
            try:
                # Даем 3 кредита при регистрации
                supabase.table("users_credits").insert({"email": email, "credits": 3}).execute()
            except Exception as e:
                print(f"User DB creation info: {e}") # Может уже есть, не страшно
            return True
        return False
    except Exception as e:
        print(f"Registration Error: {e}")
        return False

def login_user(email, password):
    """Вход по email/паролю."""
    if not supabase: return None
    try:
        # Админский бэкдор (если нужно зайти быстро под админом без базы)
        try:
            if email == st.secrets["ADMIN_EMAIL"] and password == st.secrets["ADMIN_PASSWORD"]:
                return {"email": email, "id": "admin"}
        except:
            pass

        # Стандартный вход через Supabase
        res = supabase.auth.sign_in_with_password({
            "email": email, 
            "password": password
        })
        
        if res.user:
            return {"email": res.user.email, "id": res.user.id}
        return None
    except Exception as e:
        print(f"Login Error: {e}")
        return None

# --- 3. ФУНКЦИИ КРЕДИТОВ (WALLET) ---

def get_user_credits(email):
    """Получить баланс. Если юзера нет в таблице — создать."""
    if not supabase: return 999
    
    try:
        # Нормализуем email
        email = email.lower().strip()
        
        response = supabase.table("users_credits").select("credits").eq("email", email).execute()
        
        if not response.data:
            # Юзера нет в таблице кредитов? Создаем!
            init_credits = 3
            supabase.table("users_credits").insert({"email": email, "credits": init_credits}).execute()
            return init_credits
            
        return response.data[0]["credits"]
    except Exception as e:
        print(f"Credits Error: {e}")
        return 0

def deduct_credit(email, amount=1):
    """Списать кредиты."""
    if not supabase: return True

    try:
        email = email.lower().strip()
        current = get_user_credits(email)
        
        if current < amount:
            return False
        
        new_balance = current - amount
        supabase.table("users_credits").update({"credits": new_balance}).eq("email", email).execute()
        return True
    except Exception as e:
        print(f"Deduct Error: {e}")
        return False

# --- АЛИАСЫ (Чтобы бот и сайт не путались) ---
get_credits = get_user_credits
