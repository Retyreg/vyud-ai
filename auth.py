import streamlit as st
import time
from supabase import create_client, Client

# Инициализация Supabase (берем ключи из секретов Streamlit)
# Используем @st.cache_resource, чтобы не переподключаться каждый раз
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

def login_user(email):
    """Вход или регистрация через Supabase"""
    email = email.lower().strip()
    # Проверка юзера
    try:
        response = supabase.table('users_credits').select("*").eq('email', email).execute()
        
        if len(response.data) > 0:
            # Юзер есть
            user_data = response.data[0]
            st.session_state['user'] = user_data['email']
            st.session_state['credits'] = user_data['credits']
            st.success("Вход выполнен!")
            time.sleep(0.5)
            st.rerun()
        else:
            # Регистрация
            new_user = {'email': email, 'credits': 3} # 3 бесплатных кредита
            supabase.table('users_credits').insert(new_user).execute()
            st.session_state['user'] = email
            st.session_state['credits'] = 3
            st.success("Регистрация успешна! Вам начислено 3 кредита.")
            time.sleep(0.5)
            st.rerun()
            
    except Exception as e:
        st.error(f"Ошибка базы данных: {e}")

def deduct_credit():
    """Списание 1 кредита"""
    email = st.session_state.get('user')
    current = st.session_state.get('credits', 0)
    
    if email and current > 0:
        new_val = current - 1
        supabase.table('users_credits').update({'credits': new_val}).eq('email', email).execute()
        st.session_state['credits'] = new_val
        return True
    return False

def logout():
    st.session_state['user'] = None
    st.session_state['credits'] = 0
    st.session_state['quiz'] = None
    st.rerun()