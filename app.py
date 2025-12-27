import streamlit as st
import pandas as pd
import time
import logic
import auth

# --- 1. КОНФИГУРАЦИЯ СТРАНИЦЫ ---
st.set_page_config(page_title="VYUD AI", page_icon="🎓", layout="wide")

# --- 2. CSS HACK: ЯДЕРНЫЙ ВАРИАНТ ---
st.markdown("""
    <style>
        /* 1. ПРИНУДИТЕЛЬНЫЙ БЕЛЫЙ ФОН ДЛЯ ВСЕГО */
        .stApp, .stApp > header {
            background-color: #FFFFFF !important;
        }
        [data-testid="stSidebar"] {
            background-color: #F8F9FA !important;
            border-right: 1px solid #E6E6E6;
        }
        
        /* 2. ТЕКСТ - ЧЕРНЫЙ ВЕЗДЕ */
        h1, h2, h3, h4, h5, h6, p, li, span, label, div, .stMarkdown {
            color: #000000 !important;
        }

        /* 3. ЭКСПАНДЕРЫ (ВЫПАДАЮЩИЕ СПИСКИ) - ЛЕЧЕНИЕ */
        /* Заголовок */
        .streamlit-expanderHeader {
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 1px solid #cccccc !important;
        }
        /* Внутренности (Самое важное место) */
        [data-testid="stExpanderDetails"] {
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 1px solid #cccccc !important;
            border-top: none !important;
        }
        /* Иконка стрелочки */
        .streamlit-expanderHeader svg {
            fill: #000000 !important;
        }
        
        /* 4. УБИВАЕМ СТАНДАРТНЫЕ ЦВЕТА st.info / st.success */
        /* Фон для всех уведомлений делаем очень светлым */
        [data-testid="stAlert"] {
            background-color: #f0f2f6 !important;
            color: #000000 !important;
            border: 1px solid #d1d5db !important;
        }
        /* Текст внутри уведомлений */
        [data-testid="stAlert"] * {
            color: #000000 !important;
        }
        /* Иконки внутри уведомлений */
        [data-testid="stAlert"] svg {
            fill: #000000 !important;
        }

        /* 5. ПОЛЯ ВВОДА */
        input, textarea, select {
            color: #000000 !important;
            background-color: #FFFFFF !important;
        }
        .stTextInput > div > div {
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border-color: #cccccc !important;
        }

        /* 6. КНОПКИ */
        button {
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 1px solid #cccccc !important;
        }
        button[kind="primary"] {
            background-color: #FF4B4B !important;
            color: #FFFFFF !important;
            border: none !important;
        }
        button[kind="primary"] p {
            color: #FFFFFF !important;
        }
    </style>
""", unsafe_allow_html=True)

# Загружаем внешний CSS (если есть)
try:
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except:
    pass 

# --- 3. БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    try:
        st.image("assets/logo.png", width=200)
    except:
        st.title("VYUD AI")
    st.markdown("---")

# --- 4. ЛОГИКА АВТОРИЗАЦИИ ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

if not st.session_state['user']:
    # ЭКРАН ВХОДА
    tab1, tab2 = st.tabs(["Вход", "Регистрация"])
    
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Пароль", type="password", key="login_pass")
        if st.button("Войти", key="btn_login"):
            user = auth.login_user(email, password)
            if user:
                st.session_state['user'] = user['email']
                st.rerun()
            else:
                st.error("Ошибка входа")

    with tab2:
        new_email = st.text_input("Email", key="reg_email")
        new_pass = st.text_input("Пароль", type="password", key="reg_pass")
        if st.button("Создать аккаунт", key="btn_reg"):
            if auth.register_user(new_email, new_pass):
                st.success("Регистрация успешна! Теперь войдите.")
            else:
                st.error("Ошибка регистрации")

else:
    # --- ОСНОВНОЕ ПРИЛОЖЕНИЕ ---
    with st.sidebar:
        st.write(f"Вы вошли как: **{st.session_state['user']}**")
        try:
            credits = auth.get_user_credits(st.session_state['user'])
            st.metric("Доступно кредитов", credits)
        except:
            st.metric("Доступно кредитов", 0)

        if st.button("Выйти", key="btn_logout"):
            st.session_state['user'] = None
            st.rerun()

    st.title("Генератор Обучения AI 🧠")
    st.caption("Превратите документы и видео в интерактивные тесты за секунды.")

    # ЗАГРУЗКА ФАЙЛА
    uploaded_file = st.file_uploader(
        "Загрузите материал (PDF, Video, Audio)", 
        type=['pdf', 'docx', 'txt', 'pptx', 'mp4', 'mov', 'mp3', 'wav'],
        key="main_uploader"
    )

    if uploaded_file:
        st.success(f"Файл загружен: {uploaded_file.name}")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            q_count = st.slider("Количество вопросов", 1, 10, 5, key="slider_count")
        with col2:
            difficulty = st.radio("Сложность", ["Easy", "Medium", "Hard"], key="radio_diff")
        with col3:
            lang = st.selectbox("Язык", ["Russian", "English", "Kazakh"], key="select_lang")

        if st.button("🚀 Создать курс", type="primary", key="btn_generate_course"):
            current_credits = auth.get_user_credits(st.session_state['user'])
            
            if current_credits > 0:
                with st.spinner("ИИ анализирует материал... (это может занять до 1 минуты)"):
                    try:
                        # 1. Достаем текст
                        text = logic.process_file_to_text(
                            uploaded_file, 
                            st.secrets["OPENAI_API_KEY"], 
                            st.secrets.get("LLAMA_CLOUD_API_KEY", "")
                        )
                        
                        # 2. Генерируем JSON тест
                        quiz_data = logic.generate_quiz_ai(text, q_count, difficulty, lang)
                        
                        # 3. Подсказки методолога
                        hints = logic.generate_methodologist_hints(text, lang)

                        # 4. Сохраняем
                        st.session_state['quiz_data'] = quiz_data
                        st.session_state['course_name'] = uploaded_file.name
                        st.session_state['methodologist_hints'] = hints
                        st.session_state['quiz_finished'] = False
                        st.session_state['quiz_score'] = 0
                        
                        # 5. Списываем
                        auth.deduct_credit(st.session_state['user'])
                        
                        st.success("Готово! Прокрутите вниз.")
                        time.sleep(1)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Ошибка: {e}")
            else:
                st.error("Недостаточно кредитов! Пополните баланс.")

    # ОТОБРАЖЕНИЕ РЕЗУЛЬТАТА
    if st.session_state.get('quiz_data'):
        st.divider()
        st.subheader(f"🎓 Тест по материалу: {st.session_state.get('course_name')}")
        
        # [FIX] БЛОК СОВЕТОВ - ЗАМЕНИЛИ st.info на КАСТОМНЫЙ HTML
        if st.session_state.get('methodologist_hints'):
             with st.expander("💡 Советы AI-Методолога", expanded=False):
                # РИСУЕМ СВОЙ БЛОК, ЧТОБЫ ЦВЕТА НЕ ЛОМАЛИСЬ
                st.markdown(f"""
                <div style="background-color: #e6f3ff; padding: 15px; border-radius: 5px; border: 1px solid #b3d9ff; color: #000;">
                    {st.session_state['methodologist_hints']}
                </div>
                """, unsafe_allow_html=True)

        quiz = st.session_state['quiz_data']
        
        # ЕСЛИ ТЕСТ НЕ СДАН -> ФОРМА
        if not st.session_state.get('quiz_finished', False):
            with st.form("quiz_form"):
                score = 0
                user_answers = {}
                for i, q in enumerate(quiz.questions):
                    st.markdown(f"**{i+1}. {q.scenario}**")
                    user_answers[i] = st.radio("Выберите ответ:", q.options, key=f"quiz_q_{i}", index=None)
                    st.markdown("---")
                
                submitted = st.form_submit_button("Завершить тестирование")
                
                if submitted:
                    for i, q in enumerate(quiz.questions):
                        if user_answers.get(i) == q.options[q.correct_option_id]:
                            score += 1
                    
                    st.session_state['quiz_score'] = score
                    if score >= len(quiz.questions) * 0.7:
                        st.session_state['quiz_finished'] = True
                        st.rerun()
                    else:
                        st.error(f"Тест не сдан. Результат: {score}/{len(quiz.questions)}. Попробуйте еще раз.")
        
        # ЕСЛИ ТЕСТ СДАН -> РЕЗУЛЬТАТЫ
        else:
            # КАСТОМНЫЙ БЛОК УСПЕХА
            st.markdown(f"""
            <div style="background-color: #d1fae5; padding: 15px; border-radius: 5px; border: 1px solid #34d399; color: #064e3b; margin-bottom: 10px;">
                🎉 Поздравляем! Вы сдали тест. Результат: <b>{st.session_state['quiz_score']}/{len(quiz.questions)}</b>
            </div>
            """, unsafe_allow_html=True)
            st.balloons()
            
            c1, c2 = st.columns(2)
            with c1:
                try:
                    cert_pdf = logic.create_certificate(
                        st.session_state['user'], 
                        st.session_state['course_name']
                    )
                    st.download_button(
                        label="📜 Скачать Сертификат",
                        data=cert_pdf,
                        file_name="certificate.pdf",
                        mime="application/pdf",
                        key="dl_cert"
                    )
                except Exception as e:
                    st.error(f"Ошибка сертификата: {e}")
            
            with c2:
                if st.button("🔄 Пройти заново"):
                    st.session_state['quiz_finished'] = False
                    st.rerun()

        # БЛОК HTML
        try:
            with st.expander("🔧 Дополнительно (LMS Export)"):
                html_data = logic.create_html_quiz(quiz, st.session_state['course_name'])
                st.download_button(
                    "🌐 Скачать как HTML",
                    data=html_data.encode('utf-8'),
                    file_name="quiz.html",
                    mime="text/html",
                    key="dl_html"
                )
        except:
            pass

    # --- PROMO ---
    st.divider()
    with st.container():
        c_promo_1, c_promo_2 = st.columns([2, 1])
        with c_promo_1:
            st.subheader("⚡️ Vyud AI Bot")
            st.markdown("Запишите видео -> получите тест.")
            st.link_button("👉 Открыть Telegram Бота", "https://t.me/VyudAiBot", type="primary")
        with c_promo_2:
            st.markdown("""
            <div style="background-color: #e6f3ff; padding: 10px; border-radius: 5px; color: #000;">
                🎥 Работает с Video Notes
            </div>
            """, unsafe_allow_html=True)

    # Админка
    try:
        admin_email_conf = st.secrets.get("ADMIN_EMAIL", "admin@vyud.tech").lower().strip()
    except:
        admin_email_conf = "admin@vyud.tech"

    current_user_norm = st.session_state['user'].lower().strip() if st.session_state['user'] else ""

    if current_user_norm == admin_email_conf:
        if 'admin_unlocked' not in st.session_state: st.session_state['admin_unlocked'] = False
        
        if not st.session_state['admin_unlocked']:
            st.divider()
            st.subheader("🛡️ Admin Access")
            input_pass = st.text_input("Password", type="password", key="adm_pass")
            if st.button("Login"):
                if input_pass == st.secrets.get("ADMIN_PASSWORD", "admin"):
                    st.session_state['admin_unlocked'] = True
                    st.rerun()
                else: st.error("Wrong pass")
        else:
            st.divider()
            st.subheader("🔐 ADMIN PANEL")
            tab_users, tab_marketing = st.tabs(["👥 Пользователи", "📢 AI-Маркетолог"])
            
            with tab_users:
                try:
                    all_users = auth.supabase.table('users_credits').select("*").execute()
                    if all_users.data:
                        st.dataframe(pd.DataFrame(all_users.data), hide_index=True)
                except: st.warning("Нет данных")
                
                c1, c2 = st.columns(2)
                with c1: t_email = st.text_input("Email", key="adm_e")
                with c2: 
                    if st.button("💰 +50 Кредитов"):
                        res = auth.supabase.table('users_credits').select("*").eq('email', t_email).execute()
                        if res.data:
                            auth.supabase.table('users_credits').update({'credits': res.data[0]['credits'] + 50}).eq('email', t_email).execute()
                            st.success("Начислено!")

            with tab_marketing:
                topic = st.text_input("Тема поста")
                if st.button("Генерация"):
                    st.text_area("Результат", logic.generate_marketing_post(topic, "Telegram", "Hype"))