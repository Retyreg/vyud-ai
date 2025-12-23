import streamlit as st
import pandas as pd
import time
import logic
import auth

# --- КОНФИГУРАЦИЯ СТРАНИЦЫ ---
st.set_page_config(page_title="VYUD AI", page_icon="🎓", layout="wide")

# Загружаем CSS для красоты
try:
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except:
    pass # Если файла нет, не падаем

# --- БОКОВАЯ ПАНЕЛЬ (ЛОГОТИП) ---
with st.sidebar:
    # Пробуем загрузить лого, если есть
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
    # --- ОСНОВНОЕ ПРИЛОЖЕНИЕ (ЕСЛИ ЗАЛОГИНЕН) ---
    
    # Кнопка выхода в сайдбаре
    with st.sidebar:
        st.write(f"Вы вошли как: **{st.session_state['user']}**")
        
        # Баланс кредитов
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
        
        # Настройки генерации
        col1, col2, col3 = st.columns(3)
        with col1:
            q_count = st.slider("Количество вопросов", 1, 10, 5, key="slider_count")
        with col2:
            difficulty = st.radio("Сложность", ["Easy", "Medium", "Hard"], key="radio_diff")
        with col3:
            lang = st.selectbox("Язык", ["Russian", "English", "Kazakh"], key="select_lang")

        # КНОПКА ГЕНЕРАЦИИ
        if st.button("🚀 Создать курс", type="primary", key="btn_generate_course"):
            current_credits = auth.get_user_credits(st.session_state['user'])
            
            if current_credits > 0:
                with st.spinner("ИИ анализирует материал... (это может занять до 1 минуты)"):
                    try:
                        # 1. Достаем текст (включая транскрибацию видео)
                        text = logic.process_file_to_text(
                            uploaded_file, 
                            st.secrets["OPENAI_API_KEY"], 
                            st.secrets["LLAMA_CLOUD_API_KEY"]
                        )
                        
                        # 2. Генерируем JSON с тестом
                        quiz_data = logic.generate_quiz_ai(text, q_count, difficulty, lang)
                        
                        # 3. Сохраняем в сессию
                        st.session_state['quiz_data'] = quiz_data
                        st.session_state['course_name'] = uploaded_file.name
                        
                        # 4. Списываем кредит
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
        
        quiz = st.session_state['quiz_data']
        
        # Форма для прохождения
        with st.form("quiz_form"):
            score = 0
            for i, q in enumerate(quiz.questions):
                st.markdown(f"**{i+1}. {q.scenario}**")
                # Уникальный ключ для каждого вопроса
                answer = st.radio("Выберите ответ:", q.options, key=f"quiz_q_{i}")
                
                if answer == q.options[q.correct_option_id]:
                    score += 1
                
                st.markdown("---")
            
            submitted = st.form_submit_button("Завершить тестирование")
            
            if submitted:
                if score >= len(quiz.questions) * 0.7:
                    st.success(f"Поздравляем! Вы сдали. Результат: {score}/{len(quiz.questions)}")
                    st.balloons()
                    
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
                else:
                    st.error(f"Тест не сдан. Результат: {score}/{len(quiz.questions)}. Попробуйте еще раз.")
        
        # Скачивание HTML версии (SCORM Lite)
        try:
            html_data = logic.create_html_quiz(quiz, st.session_state['course_name'])
            st.download_button(
                "🌐 Скачать как HTML (для LMS)",
                data=html_data,
                file_name="quiz.html",
                mime="text/html",
                key="dl_html"
            )
        except:
            pass

    # --- БЛОК PROMO: TELEGRAM БОТ ---
    st.divider()
    with st.container():
        c_promo_1, c_promo_2 = st.columns([2, 1])
        with c_promo_1:
            st.subheader("⚡️ Обучайте сотрудников на бегу")
            st.markdown(
                """
                **Нет времени сидеть за ноутбуком?** Мы запустили **Vyud AI Bot** в Telegram.
                
                1. 🤳 **Запишите "кружочек"** с инструкцией.
                2. 🤖 ИИ мгновенно превратит его в **тест**.
                3. 🚀 Перешлите тест сотрудникам.
                """
            )
            # ВАЖНО: Убедитесь, что ссылка правильная
            st.link_button("👉 Открыть Telegram Бота", "https://t.me/VyudAiBot", type="primary")

        with c_promo_2:
            st.info("🎥 Запишите видео -> ✅ Тест готов!")

    # --- ЗАЩИЩЕННАЯ АДМИН ПАНЕЛЬ ---
    
    # 1. Проверяем Email админа
    try:
        admin_email_conf = st.secrets.get("ADMIN_EMAIL", "admin@vyud.tech").lower().strip()
    except:
        admin_email_conf = "admin@vyud.tech"

    current_user_norm = st.session_state['user'].lower().strip()

    if current_user_norm == admin_email_conf:
        
        # Инициализация блокировки
        if 'admin_unlocked' not in st.session_state:
            st.session_state['admin_unlocked'] = False

        # ЭКРАН ВВОДА ПАРОЛЯ
        if not st.session_state['admin_unlocked']:
            st.divider()
            st.subheader("🛡️ Доступ к системе управления")
            
            try:
                true_admin_pass = st.secrets["ADMIN_PASSWORD"]
            except:
                st.error("⚠️ В secrets.toml не задан ADMIN_PASSWORD!")
                st.stop()
            
            # ВАЖНО: Уникальный ключ для пароля
            input_pass = st.text_input("Введите Мастер-Пароль", type="password", key="admin_master_pass_input")
            
            if st.button("🔓 Войти в Админку", key="btn_admin_login"):
                if input_pass == true_admin_pass:
                    st.session_state['admin_unlocked'] = True
                    st.success("Доступ разрешен!")
                    st.rerun()
                else:
                    st.error("Неверный пароль!")
        
        # ЭКРАН АДМИНКИ (ЕСЛИ РАЗБЛОКИРОВАНО)
        else:
            st.divider()
            if st.button("🔒 Заблокировать панель", key="btn_admin_lock"):
                st.session_state['admin_unlocked'] = False
                st.rerun()

            with st.expander("🔐 ADMIN PANEL (v3.3 Fixed)", expanded=True):
                tab_users, tab_marketing = st.tabs(["👥 Пользователи", "📢 AI-Маркетолог"])
                
                # --- Вкладка 1: Пользователи ---
                with tab_users:
                    try:
                        all_users = auth.supabase.table('users_credits').select("*").execute()
                        if all_users.data:
                            df = pd.DataFrame(all_users.data)
                            st.dataframe(df, hide_index=True)
                        else:
                            st.warning("Пользователей пока нет")
                    except Exception as e:
                        st.error(f"Ошибка: {e}")

                    st.markdown("---")
                    st.write("**Начислить кредиты:**")
                    c1, c2, c3 = st.columns([2, 1, 1])
                    
                    # ВАЖНО: Уникальные ключи (adm_...)
                    with c1: target_email = st.text_input("Email клиента", key="adm_credit_email_input")
                    with c2: amount = st.number_input("Кол-во", value=50, key="adm_credit_amount_input")
                    with c3: 
                        st.write("") 
                        st.write("")
                        btn_add = st.button("💰 Начислить", key="adm_credit_add_btn")
                    
                    if btn_add:
                        try:
                            tgt = target_email.lower().strip()
                            res = auth.supabase.table('users_credits').select("*").eq('email', tgt).execute()
                            if res.data:
                                current = res.data[0]['credits']
                                new_val = current + amount
                                auth.supabase.table('users_credits').update({'credits': new_val}).eq('email', tgt).execute()
                                st.success(f"Успешно! {tgt}: {current} -> {new_val}")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Email не найден!")
                        except Exception as e:
                            st.error(f"Ошибка: {e}")

                # --- Вкладка 2: Маркетинг ---
                with tab_marketing:
                    st.subheader("Генератор контента 🚀")
                    
                    # ВАЖНО: Уникальные ключи для ВСЕХ полей (adm_market_...)
                    m_topic = st.text_input(
                        "О чем пишем? (Тема)", 
                        "Обновление: теперь поддерживаем видео", 
                        key="adm_market_topic"
                    )
                    m_context = st.text_area(
                        "Детали / Контекст (опционально)", 
                        "Добавили загрузку mp4, mov. ИИ сам транскрибирует.", 
                        key="adm_market_context"
                    )
                    
                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        m_platform = st.selectbox(
                            "Платформа", 
                            ["Telegram (дружелюбно)", "LinkedIn (деловой)", "Email рассылка"], 
                            key="adm_market_platform"
                        )
                    with col_m2:
                        m_tone = st.selectbox(
                            "Тон", 
                            ["Дружелюбный/Хайповый", "Экспертный/Строгий", "Продающий/Дерзкий"], 
                            key="adm_market_tone"
                        )
                    
                    if st.button("✨ Сгенерировать пост", key="adm_market_gen_btn"):
                        with st.spinner("AI-маркетолог пишет текст..."):
                            try:
                                post_text = logic.generate_marketing_post(m_topic, m_platform, m_tone, m_context)
                                st.text_area(
                                    "Результат (копируй отсюда):", 
                                    value=post_text, 
                                    height=300, 
                                    key="adm_market_result_area"
                                )
                            except Exception as e:
                                st.error(f"Ошибка генерации: {e}")