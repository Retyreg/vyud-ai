import streamlit as st
import pandas as pd
import time
import logic
import auth

# --- КОНФИГУРАЦИЯ СТРАНИЦЫ ---
st.set_page_config(page_title="VYUD AI", page_icon="🎓", layout="wide")

# --- ⬇️ ВСТАВИТЬ СРАЗУ ПОСЛЕ st.set_page_config(...) ⬇️ ---

# ПРИНУДИТЕЛЬНАЯ СВЕТЛАЯ ТЕМА (CSS HACK)
# Красим всё в белый/светлый, игнорируя настройки браузера
st.markdown("""
    <style>
        /* 1. Главный фон приложения - делаем белым */
        .stApp {
            background-color: #FFFFFF !important;
        }
        
        /* 2. Сайдбар - делаем светло-серым */
        [data-testid="stSidebar"] {
            background-color: #F0F2F6 !important;
        }
        
        /* 3. Весь текст - делаем черным/темно-серым */
        h1, h2, h3, h4, h5, h6, p, li, label, div, span, .stMarkdown {
            color: #262730 !important;
        }
        
        /* 4. Поля ввода (Input) - белый фон, черный текст */
        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
            color: #262730 !important;
            background-color: #FFFFFF !important;
            border-color: #D3D3D3 !important;
        }
        
        /* 5. Убираем странные цвета в выпадающих списках */
        ul[data-baseweb="menu"] {
            background-color: #FFFFFF !important;
        }
        
        /* 6. Адаптация кнопок (чтобы текст был виден) */
        button {
            color: #262730 !important; 
        }
        /* Но кнопки Primary (акцентные) оставляем белым текстом */
        button[kind="primary"] {
            color: #FFFFFF !important;
        }
        
        /* 7. Заголовки экспандеров */
        .streamlit-expanderHeader {
            background-color: #FFFFFF !important;
            color: #262730 !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- ⬆️ КОНЕЦ ВСТАВКИ ⬆️ ---

# Загружаем CSS
try:
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except:
    pass 

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    try:
        st.image("assets/logo.png", width=200)
    except:
        st.title("VYUD AI")
    st.markdown("---")

# --- ЛОГИКА АВТОРИЗАЦИИ ---
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

    # 1. ЗАГРУЗКА ФАЙЛА
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
                        
                        # 3. Доп фичи (методолог)
                        hints = logic.generate_methodologist_hints(text, lang)

                        # 4. Сохраняем ВСЁ в сессию
                        st.session_state['quiz_data'] = quiz_data
                        st.session_state['course_name'] = uploaded_file.name
                        st.session_state['methodologist_hints'] = hints
                        
                        # Сбрасываем флаг прохождения теста (чтобы форма появилась снова)
                        st.session_state['quiz_finished'] = False
                        st.session_state['quiz_score'] = 0
                        
                        # 5. Списываем кредит
                        auth.deduct_credit(st.session_state['user'])
                        
                        st.success("Готово! Прокрутите вниз.")
                        time.sleep(1)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Ошибка: {e}")
            else:
                st.error("Недостаточно кредитов! Пополните баланс.")

    # 2. ОТОБРАЖЕНИЕ РЕЗУЛЬТАТА
    if st.session_state.get('quiz_data'):
        st.divider()
        st.subheader(f"🎓 Тест по материалу: {st.session_state.get('course_name')}")
        
        # Подсказки методолога
        if st.session_state.get('methodologist_hints'):
             with st.expander("💡 Советы AI-Методолога", expanded=False):
                st.info(st.session_state['methodologist_hints'])

        quiz = st.session_state['quiz_data']
        
        # Если тест ЕЩЕ НЕ сдан -> Показываем форму
        if not st.session_state.get('quiz_finished', False):
            with st.form("quiz_form"):
                score = 0
                # Временное хранилище ответов
                user_answers = {}
                
                for i, q in enumerate(quiz.questions):
                    st.markdown(f"**{i+1}. {q.scenario}**")
                    user_answers[i] = st.radio("Выберите ответ:", q.options, key=f"quiz_q_{i}", index=None)
                    st.markdown("---")
                
                submitted = st.form_submit_button("Завершить тестирование")
                
                if submitted:
                    # Считаем баллы ПОСЛЕ нажатия
                    for i, q in enumerate(quiz.questions):
                        if user_answers.get(i) == q.options[q.correct_option_id]:
                            score += 1
                    
                    st.session_state['quiz_score'] = score
                    
                    if score >= len(quiz.questions) * 0.7:
                        # УСПЕХ: Ставим флаг и перезагружаем страницу, чтобы выйти из формы
                        st.session_state['quiz_finished'] = True
                        st.rerun()
                    else:
                        st.error(f"Тест не сдан. Результат: {score}/{len(quiz.questions)}. Попробуйте еще раз.")
        
        # Если тест СДАН -> Показываем результаты и КНОПКИ (вне формы)
        else:
            st.success(f"🎉 Поздравляем! Вы сдали. Результат: {st.session_state['quiz_score']}/{len(quiz.questions)}")
            st.balloons()
            
            c1, c2 = st.columns(2)
            with c1:
                # Генерация сертификата
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

        # Скачивание HTML (доступно всегда внизу)
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

    # --- PROMO & ADMIN ---
    # (Оставляю твой код без изменений внизу)
    st.divider()
    with st.container():
        c_promo_1, c_promo_2 = st.columns([2, 1])
        with c_promo_1:
            st.subheader("⚡️ Обучайте сотрудников на бегу")
            st.markdown("**Нет времени?** Используйте **Vyud AI Bot** в Telegram.")
            st.link_button("👉 Открыть Telegram Бота", "https://t.me/VyudAiBot", type="primary")
        with c_promo_2:
            st.info("🎥 Запишите видео -> ✅ Тест готов!")

    # Админка
    try:
        admin_email_conf = st.secrets.get("ADMIN_EMAIL", "admin@vyud.tech").lower().strip()
    except:
        admin_email_conf = "admin@vyud.tech"

    current_user_norm = st.session_state['user'].lower().strip()

    if current_user_norm == admin_email_conf:
        if 'admin_unlocked' not in st.session_state: st.session_state['admin_unlocked'] = False
        
        if not st.session_state['admin_unlocked']:
            st.divider()
            st.subheader("🛡️ Доступ к системе управления")
            input_pass = st.text_input("Пароль Админа", type="password", key="adm_pass")
            if st.button("Войти"):
                if input_pass == st.secrets.get("ADMIN_PASSWORD", "admin"):
                    st.session_state['admin_unlocked'] = True
                    st.rerun()
                else: st.error("Неверно")
        else:
            st.divider()
            st.subheader("🔐 ADMIN PANEL")
            # Тут твой код админки (пользователи и маркетинг), он в порядке
            # Я сократил для экономии места, но вставь сюда свой кусок с Tabs
