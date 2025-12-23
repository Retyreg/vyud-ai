import streamlit as st
from supabase import create_client, Client
import logging

# --- ИНИЦИАЛИЗАЦИЯ SUPABASE ---
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        logging.error(f"Supabase Init Error: {e}")
        return None

supabase = init_supabase()

# --- ФУНКЦИИ АВТОРИЗАЦИИ (ИСПРАВЛЕННЫЕ) ---

# Теперь принимает 2 аргумента, чтобы не было ошибки TypeError
def login_user(email, password):
    """
    Проверяет существование пользователя.
    """
    try:
        # Приводим к нижнему регистру
        clean_email = email.lower().strip()
        
        # Ищем пользователя в базе
        res = supabase.table('users_credits').select("*").eq('email', clean_email).execute()
        
        if res.data:
            user = res.data[0]
            # ПРИМЕЧАНИЕ: Если вы добавите колонку 'password' в Supabase,
            # раскомментируйте строки ниже для проверки пароля:
            # if user.get('password') == password:
            #     return user
            
            # Пока возвращаем пользователя просто по факту наличия email (для Демо)
            return user
            
        return None
    except Exception as e:
        print(f"Login Error: {e}")
        return None

# Теперь принимает 2 аргумента
def register_user(email, password):
    """
    Регистрирует нового пользователя
    """
    try:
        clean_email = email.lower().strip()
        
        # 1. Проверяем, есть ли уже такой
        existing = supabase.table('users_credits').select("*").eq('email', clean_email).execute()
        if existing.data:
            return False # Уже есть

        # 2. Создаем (Пароль пока не сохраняем в БД, чтобы не ломать старую таблицу)
        new_user_data = {
            'email': clean_email,
            'credits': 3 # Даем 3 кредита при регистрации
        }
        
        supabase.table('users_credits').insert(new_user_data).execute()
        return True
    except Exception as e:
        print(f"Register Error: {e}")
        return False

# --- ФУНКЦИИ БАЛАНСА (ДЛЯ БОТА И САЙТА) ---
def get_user_credits(email):
    try:
        clean_email = email.lower().strip()
        res = supabase.table('users_credits').select("*").eq('email', clean_email).execute()
        if res.data:
            return res.data[0]['credits']
        return 0
    except:
        return 0

def deduct_credit(email):
    try:
        clean_email = email.lower().strip()
        current = get_user_credits(clean_email)
        if current > 0:
            supabase.table('users_credits').update({'credits': current - 1}).eq('email', clean_email).execute()
            return True
        return False
    except:
        return False