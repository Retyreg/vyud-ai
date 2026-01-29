import streamlit as st
import logic
import auth
import os
import pandas as pd

# 1. КОНФИГУРАЦИЯ
st.set_page_config(page_title="VYUD AI", page_icon="��", layout="wide")

# 2. CSS
st.markdown("""
<style>
    .stApp {background-color:#FFFFFF!important}
    [data-testid="stSidebar"] {background-color:#F8F9FA!important; border-right:1px solid #E6E6E6}
    h1,h2,h3,h4,h5,h6,p,li,span,div,label, .stMarkdown {color:#262730!important}
    details {background-color:#FFFFFF!important; border:1px solid #d1d5db!important; border-radius:5px; margin-bottom:10px}
    summary {background-color:#fcfcfc!important; color:black!important; font-weight:600}
    input, textarea {background-color:white!important; color:black!important; border:1px solid #ccc!important}
    button[kind="primary"] {background-color:#FF4B4B!important; color:white!important; border:none!important}
    .stAlert {background-color: #f0f2f6 !important; color: #000000 !important;}
</style>""", unsafe_allow_html=True)

# 3. САЙДБАР
with st.sidebar:
    st.title("VYUD AI 🎓")
    st.markdown("### ⚙️ Настройки")
    logo_file = st.file_uploader("Логотип компании", type=['png', 'jpg', 'jpeg'])
    signature_file = st.file_uploader("Подпись руководителя", type=['png', 'jpg', 'jpeg'])
    if logo_file: st.image(logo_file, width=150)
    if signature_file: st.image(signature_file, width=100)
    st.markdown("---")

# 4. АВТОРИЗАЦИЯ
if 'user' not in st.session_state: st.session_state['user'] = None

if not st.session_state['user']:
    t1, t2 = st.tabs(["Вход", "Регистрация"])
    with t1:
        e = st.text_input("Email", key="l_e"); p = st.text_input("Пароль", type="password", key="l_p")
        if st.button("Войти"):
            if auth.login_user(e, p): st.session_state['user']=e; st.rerun()
            else: st.error("Ошибка входа")
    with t2:
        e2 = st.text_input("Email", key="r_e"); p2 = st.text_input("Пароль", type="password", key="r_p")
        if st.button("Создать"):
            if auth.register_user(e2, p2): st.success("Аккаунт создан! Войдите."); 
            else: st.error("Ошибка")
else:
    # 5. ПРИЛОЖЕНИЕ
    with st.sidebar:
        st.write(f"Вы: **{st.session_state['user']}**")
        try: cr = auth.get_user_credits(st.session_state['user'])
        except: cr = 0
        
        col_b1, col_b2 = st.columns([2, 1])
        with col_b1: st.metric("Баланс", cr)
        with col_b2: st.write("")
        
        st.link_button("💎 Тарифы", "https://vyud.online/#pricing", type="primary", use_container_width=True)

        if st.button("Выход", use_container_width=True): 
            st.session_state['user']=None; st.rerun()


    st.title("Генератор Обучения AI 🧠")
    
    uf = st.file_uploader("Загрузите файл (PDF, Video, Audio, DOCX...)", type=['pdf','docx','pptx','txt','xlsx','csv','mp4','mov','mp3','wav','mpeg4','mkv','avi','webm','wmv'])

    if uf:
        st.success(f"Файл: {uf.name}")
        c1, c2, c3 = st.columns(3)
        with c1: diff = st.radio("Сложность", ["Easy", "Medium", "Hard"])
        with c2: lang = st.selectbox("Язык", ["Russian", "English", "Kazakh", "Uzbek", "Kyrgyz", "Turkish"])
        with c3: cnt = st.slider("Вопросы", 1, 20, 5)

        if st.button("🚀 Создать тест", type="primary"):
            if auth.get_user_credits(st.session_state['user']) > 0:
                with st.spinner("Анализ..."):
                    try:
                        txt = logic.process_file_to_text(uf, st.secrets["OPENAI_API_KEY"])
                        st.session_state['q'] = logic.generate_quiz_ai(txt, cnt, diff, lang)
                        st.session_state['h'] = logic.generate_methodologist_hints(txt, lang)
                        st.session_state['fn'] = uf.name
                        st.session_state['done'] = False
                        st.session_state['score'] = 0
                        auth.deduct_credit(st.session_state['user'])
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
            else: st.error("Недостаточно кредитов! Пополните баланс в меню слева.")

    if st.session_state.get('q'):
        st.divider()
        if st.session_state.get('h'):
            with st.expander("💡 Подсказки Методолога", expanded=True): st.info(st.session_state['h'])

        q = st.session_state['q']
        if not st.session_state.get('done'):
            with st.form("qz"):
                s = 0; ans = {}
                for i, qu in enumerate(q.questions):
                    st.markdown(f"**{i+1}. {qu.scenario}**")
                    ans[i] = st.radio("Ответ:", qu.options, key=f"q{i}")
                    st.divider()
                if st.form_submit_button("Завершить"):
                    for i, qu in enumerate(q.questions):
                        if ans.get(i) == qu.options[qu.correct_option_id]: s+=1
                    st.session_state['score'] = s
                    if s >= len(q.questions)*0.7: st.session_state['done'] = True; st.rerun()
                    else: st.error(f"Не сдал: {s}/{len(q.questions)}")
        else:
            st.success(f"Сдано! Результат: {st.session_state['score']}")
            st.subheader("📜 Сертификат / Экспорт")
            c_n, c_c = st.columns(2)
            with c_n: 
                d_n = st.session_state['user'].split('@')[0]
                name = st.text_input("ФИО Студента", value=d_n)
            with c_c: 
                d_c = st.session_state['fn'].split('.')[0]
                course = st.text_input("Название курса", value=d_c)
            
            try:
                pdf = logic.create_certificate(name, course, logo_file, signature_file)
                st.download_button("📥 Скачать Сертификат (PDF)", pdf, "cert.pdf", "application/pdf", type="primary")
            except Exception as e: st.error(f"Ошибка PDF: {e}")
            
            try: st.download_button("🌐 Скачать Тест (HTML Offline)", logic.create_html_quiz(q, st.session_state['fn']), "quiz.html", "text/html")
            except: pass

            if st.button("Заново"): st.session_state['done']=False; st.rerun()

    st.divider()
    st.markdown("""<div style="background-color:#f0f9ff; padding:15px; border-radius:10px; border:1px solid #bae6fd">
    <h4>🤖 Обучение на бегу</h4>
    <p>Используйте Telegram Бота: <a href="https://t.me/VyudAiBot" target="_blank">@VyudAiBot</a></p></div>""", unsafe_allow_html=True)

    if st.session_state['user'] == "vatyutovd@gmail.com":
        st.divider(); st.subheader("🛡️ Админ Панель")
        if st.button("🔴 ПЕРЕЗАГРУЗИТЬ СЕРВЕР (Update Code)"): os.system("pkill -9 -f streamlit")
             
        if st.button("Показать пользователей"):
            try:
                data = auth.supabase.table('users_credits').select("*").execute()
                st.dataframe(pd.DataFrame(data.data))
            except: st.error("Ошибка БД")
        c_a1, c_a2 = st.columns(2)
        with c_a1: t_e = st.text_input("Email пользователя")
        with c_a2: 
            if st.button("💰 +50 Кредитов"):
                try:
                    res = auth.supabase.table('users_credits').select("*").eq('email', t_e).execute()
                    if res.data:
                        auth.supabase.table('users_credits').update({'credits': res.data[0]['credits'] + 50}).eq('email', t_e).execute()
                        st.success("Начислено!")
                except: st.error("Ошибка")
