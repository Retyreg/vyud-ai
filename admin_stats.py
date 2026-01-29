import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if not st.session_state.admin_logged_in:
    st.set_page_config(page_title="VYUD Admin", page_icon="📊", layout="wide")
    st.title("🔐 Админ-панель VYUD AI")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        admin_pass = st.text_input("Пароль:", type="password", key="pass")
        if st.button("Войти", use_container_width=True):
            if admin_pass == st.secrets.get("ADMIN_PASSWORD", "admin123"):
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("❌ Неверный пароль")
    st.stop()

st.set_page_config(page_title="VYUD Analytics", page_icon="📊", layout="wide")

try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"❌ Ошибка подключения: {e}")
    st.stop()

@st.cache_data(ttl=60)
def get_users():
    response = supabase.table("users_credits").select("*").execute()
    return pd.DataFrame(response.data)

@st.cache_data(ttl=60)
def get_logs():
    try:
        response = supabase.table("generation_logs").select("*").execute()
        return pd.DataFrame(response.data)
    except:
        return pd.DataFrame()

df_users = get_users()
df_logs = get_logs()

if df_users.empty:
    st.warning("⚠️ Нет данных")
    st.stop()

if 'last_seen' in df_users.columns:
    df_users['last_seen'] = pd.to_datetime(df_users['last_seen'], errors='coerce')

st.title("📊 Аналитика @VyudAiBot")
st.markdown("---")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("👥 Пользователей", len(df_users))

with col2:
    premium = df_users.get("telegram_premium", pd.Series([False])).sum()
    pct = (premium / len(df_users) * 100) if len(df_users) > 0 else 0
    st.metric("⭐ Premium", f"{premium} ({pct:.1f}%)")

with col3:
    if 'last_seen' in df_users.columns:
        active = len(df_users[df_users['last_seen'] > datetime.now() - timedelta(days=7)])
        st.metric("🔥 Активных 7д", active)
    else:
        st.metric("🔥 Активных 7д", "N/A")

with col4:
    total_gens = df_users.get("total_generations", pd.Series([0])).sum()
    st.metric("🎯 Генераций", int(total_gens))

with col5:
    credits = df_users.get("credits", pd.Series([0])).sum()
    st.metric("💳 Кредитов", int(credits))

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["👥 Пользователи", "⭐ Premium", "📊 Активность"])

with tab1:
    st.subheader("🏆 Топ-10 по активности")
    if 'total_generations' in df_users.columns:
        top = df_users.nlargest(10, 'total_generations')
        cols = ['username', 'first_name', 'telegram_premium', 'total_generations', 'credits', 'last_seen']
        cols = [c for c in cols if c in top.columns]
        display = top[cols].copy()
        if 'telegram_premium' in display.columns:
            display['telegram_premium'] = display['telegram_premium'].map({True: '⭐', False: '—'})
        if 'last_seen' in display.columns:
            display['last_seen'] = display['last_seen'].dt.strftime('%d.%m %H:%M')
        st.dataframe(display, use_container_width=True, hide_index=True)
    
    st.subheader("📋 Все пользователи")
    cols = ['telegram_id', 'username', 'first_name', 'telegram_premium', 'total_generations', 'credits', 'last_seen']
    cols = [c for c in cols if c in df_users.columns]
    display = df_users[cols].copy()
    if 'telegram_premium' in display.columns:
        display['telegram_premium'] = display['telegram_premium'].map({True: '⭐', False: '—'})
    if 'last_seen' in display.columns:
        display = display.sort_values('last_seen', ascending=False)
        display['last_seen'] = display['last_seen'].dt.strftime('%d.%m %H:%M')
    st.dataframe(display, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("⭐ Premium vs Regular")
    if 'telegram_premium' in df_users.columns:
        col1, col2 = st.columns(2)
        with col1:
            counts = df_users['telegram_premium'].value_counts()
            fig = px.pie(values=counts.values, names=['Regular', 'Premium'], 
                        color_discrete_sequence=['#808080', '#FFD700'])
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            if 'total_generations' in df_users.columns:
                stats = df_users.groupby('telegram_premium')['total_generations'].agg(['mean', 'sum', 'count']).reset_index()
                stats['telegram_premium'] = stats['telegram_premium'].map({True: 'Premium', False: 'Regular'})
                stats.columns = ['Тип', 'Среднее', 'Всего', 'Кол-во']
                st.dataframe(stats, use_container_width=True, hide_index=True)

with tab3:
    if not df_logs.empty and 'created_at' in df_logs.columns:
        df_logs['created_at'] = pd.to_datetime(df_logs['created_at'])
        df_logs['date'] = df_logs['created_at'].dt.date
        daily = df_logs.groupby('date').size().reset_index(name='count')
        fig = px.line(daily, x='date', y='count', title='Генерации по дням', markers=True)
        st.plotly_chart(fig, use_container_width=True)
        
        if 'generation_type' in df_logs.columns:
            types = df_logs['generation_type'].value_counts()
            fig = px.pie(values=types.values, names=types.index, title="Типы контента")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📭 Нет данных о генерациях")

st.markdown("---")
col1, col2 = st.columns([1, 5])
with col1:
    if st.button("🔄 Обновить"):
        st.cache_data.clear()
        st.rerun()
with col2:
    if st.button("🚪 Выйти"):
        st.session_state.admin_logged_in = False
        st.rerun()
