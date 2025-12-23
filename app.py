import streamlit as st
import os
import time
import pandas as pd # Добавили pandas для красивой таблицы
from dotenv import load_dotenv

# ИМПОРТ НАШИХ МОДУЛЕЙ
import auth
import logic

# 1. НАСТРОЙКИ
st.set_page_config(page_title="Vyud AI", page_icon="🎓", layout="wide")
load_dotenv()

# Установка ключей
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
os.environ["LLAMA_CLOUD_API_KEY"] = st.secrets["LLAMA_CLOUD_API_KEY"]

# --- КОНФИГУРАЦИЯ БИЗНЕСА ---
PAYMENT_LINK = "https://t.me/retyreg" 
ADMIN_EMAIL = "vatyutovd@gmail.com"  # <--- ВАШ EMAIL (только он увидит админку)

# Инициализация сессии
if 'user' not in st.session_state: st.session_state['user'] = None
if 'credits' not in st.session_state: st.session_state['credits'] = 0
if 'quiz' not in st.session_state: st.session_state['quiz'] = None

# СЛОВАРЬ ПЕРЕВОДОВ
TRANSLATIONS = {
    "Русский": {
        "branding_header": "🏢 Брендинг",
        "logo_label": "Логотип компании (PNG/JPG)",
        "settings_header": "⚙️ Настройки генерации",
        "target_lang_label": "Язык теста:",
        "difficulty_label": "Сложность:",
        "count_label": "Количество вопросов:",
        "upload_label": "Загрузи материал (PDF, Видео, Аудио)",
        "btn_create": "🚀 Создать Тест (1 кредит)",
        "success_cert": "🏆 Сертификация",
        "btn_download_cert": "📄 Скачать Сертификат",
        "btn_download_html": "🌐 Скачать Тест (HTML)",
        "no_credits": "⚠️ Недостаточно кредитов!",
        "q_correct": "Правильно:",
        "preview_label": "Предпросмотр теста:",
        "buy_credits": "💎 Купить пакет (50 шт)",
        "buy_desc": "Снимите лимиты и генерируйте тесты без ограничений."
    },
    "English": {
        "branding_header": "🏢 Branding",
        "logo_label": "Company Logo (PNG/JPG)",
        "settings_header": "⚙️ Generation Settings",
        "target_lang_label": "Target Quiz Language:",
        "difficulty_label": "Difficulty:",
        "count_label": "Questions Count:",
        "upload_label": "Upload material (PDF, Video, Audio)",
        "btn_create": "🚀 Create Quiz (1 credit)",
        "success_cert": "🏆 Certification",
        "btn_download_cert": "📄 Download Certificate",
        "btn_download_html": "🌐 Download Quiz (HTML)",
        "no_credits": "⚠️ Not enough credits!",
        "q_correct": "Correct:",
        "preview_label": "Quiz Preview:",
        "buy_credits": "💎 Buy Credits (50 pack)",
        "buy_desc": "Remove limits and generate unlimited quizzes."
    }
}

# --- ИНТЕРФЕЙС ---

# 1. ЭКРАН ВХОДА
if st.session_state['user'] is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🎓 Vyud AI")
        st.info("Пожалуйста, войдите в систему.")
        email_input = st.text_input("Ваш Email")
        if st.button("Войти / Регистрация"):
            if "@" in email_input:
                auth.login_user(email_input)
            else:
                st.warning("Некорректный Email")

# 2. ОСНОВНОЕ ПРИЛОЖЕНИЕ
else:
    # Сайдбар
    with st.sidebar:
        st.write(f"👤 **{st.session_state['user']}**")
        st.metric("Кредиты", st.session_state['credits'])
        if st.button("Выйти"): auth.logout()
        st.divider()

        ui_lang = st.selectbox("🌐 Language", ["Русский", "English"])
        t = TRANSLATIONS[ui_lang]

        # --- БЛОК ОПЛАТЫ ---
        st.info(t["buy_desc"])
        st.link_button(t["buy_credits"], PAYMENT_LINK)
        st.divider()

        st.header(t["branding_header"])
        company_logo = st.file_uploader(t["logo_label"], type=["png", "jpg", "jpeg"])
        if company_logo: st.image(company_logo, width=100)
        
        st.divider()
        st.header(t["settings_header"])
        quiz_lang = st.text_input(t["target_lang_label"], value="Russian" if ui_lang=="Русский" else "English")
        quiz_difficulty = st.radio(t["difficulty_label"], ["Easy", "Medium", "Hard"])
        quiz_count = st.slider(t["count_label"], 1, 10, 5)

        # --- АДМИН ПАНЕЛЬ (ЗАЩИЩЕННАЯ) ---
        if st.session_state['user'] == ADMIN_EMAIL:
            
            # Инициализируем состояние блокировки
            if 'admin_unlocked' not in st.session_state:
                st.session_state['admin_unlocked'] = False

            # Если еще не разблокировано - показываем "Дверь"
            if not st.session_state['admin_unlocked']:
                st.divider()
                st.subheader("🛡️ Доступ к системе управления")
                
                # Читаем пароль из секретов
                try:
                    true_admin_pass = st.secrets["ADMIN_PASSWORD"]
                except:
                    st.error("⚠️ В secrets.toml не задан ADMIN_PASSWORD!")
                    st.stop()
                
                # Поле ввода пароля
                input_pass = st.text_input("Введите Мастер-Пароль", type="password")
                
                if st.button("🔓 Войти в Админку"):
                    if input_pass == true_admin_pass:
                        st.session_state['admin_unlocked'] = True
                        st.success("Доступ разрешен!")
                        st.rerun()
                    else:
                        st.error("Неверный пароль!")
            
            # Если разблокировано - показываем "Пульт управления"
            else:
                st.divider()
                # Кнопка выхода (блокировки)
                if st.button("🔒 Заблокировать панель"):
                    st.session_state['admin_unlocked'] = False
                    st.rerun()

                with st.expander("🔐 ADMIN PANEL (v3.1 Secure)", expanded=True):
                    # Вкладки внутри админки
                    tab_users, tab_marketing = st.tabs(["👥 Пользователи", "📢 AI-Маркетолог"])
                    
                    # --- ВКЛАДКА 1: ПОЛЬЗОВАТЕЛИ ---
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
                        with c1: target_email = st.text_input("Email клиента")
                        with c2: amount = st.number_input("Кол-во", value=50)
                        with c3: 
                            st.write("") 
                            st.write("")
                            btn_add = st.button("💰 Начислить")
                        
                        if btn_add:
                            try:
                                res = auth.supabase.table('users_credits').select("*").eq('email', target_email.lower().strip()).execute()
                                if res.data:
                                    current = res.data[0]['credits']
                                    new_val = current + amount
                                    auth.supabase.table('users_credits').update({'credits': new_val}).eq('email', target_email.lower().strip()).execute()
                                    st.success(f"Успешно! {target_email}: {current} -> {new_val}")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Email не найден!")
                            except Exception as e:
                                st.error(f"Ошибка: {e}")

                    # --- ВКЛАДКА 2: ГЕНЕРАТОР ПОСТОВ ---
                    with tab_marketing:
                        st.subheader("Генератор контента 🚀")
                        
                        m_topic = st.text_input("О чем пишем? (Тема)", "Обновление: теперь поддерживаем видео")
                        m_context = st.text_area("Детали / Контекст (опционально)", "Добавили загрузку mp4, mov. ИИ сам транскрибирует.")
                        
                        col_m1, col_m2 = st.columns(2)
                        with col_m1:
                            m_platform = st.selectbox("Платформа", ["Telegram (дружелюбно)", "LinkedIn (деловой)", "Email рассылка"])
                        with col_m2:
                            m_tone = st.selectbox("Тон", ["Дружелюбный/Хайповый", "Экспертный/Строгий", "Продающий/Дерзкий"])
                        
                        if st.button("✨ Сгенерировать пост"):
                            with st.spinner("AI-маркетолог пишет текст..."):
                                try:
                                    post_text = logic.generate_marketing_post(m_topic, m_platform, m_tone, m_context)
                                    st.text_area("Результат (копируй отсюда):", value=post_text, height=300)
                                except Exception as e:
                                    st.error(f"Ошибка генерации: {e}")

                # --- ВКЛАДКА 2: ГЕНЕРАТОР ПОСТОВ ---
                with tab_marketing:
                    st.subheader("Генератор контента 🚀")
                    
                    m_topic = st.text_input("О чем пишем? (Тема)", "Обновление: теперь поддерживаем видео")
                    m_context = st.text_area("Детали / Контекст (опционально)", "Добавили загрузку mp4, mov. ИИ сам транскрибирует.")
                    
                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        m_platform = st.selectbox("Платформа", ["Telegram (дружелюбно)", "LinkedIn (деловой)", "Email рассылка"])
                    with col_m2:
                        m_tone = st.selectbox("Тон", ["Дружелюбный/Хайповый", "Экспертный/Строгий", "Продающий/Дерзкий"])
                    
                    if st.button("✨ Сгенерировать пост"):
                        with st.spinner("AI-маркетолог пишет текст..."):
                            try:
                                # Вызываем функцию из logic.py
                                post_text = logic.generate_marketing_post(m_topic, m_platform, m_tone, m_context)
                                st.text_area("Результат (копируй отсюда):", value=post_text, height=300)
                            except Exception as e:
                                st.error(f"Ошибка генерации: {e}")
        # ---------------------------------
# --- БЛОК PROMO: TELEGRAM БОТ ---
    st.divider()
    
    # Контейнер с легким акцентом
    with st.container():
        c_promo_1, c_promo_2 = st.columns([2, 1])
        
        with c_promo_1:
            st.subheader("⚡️ Обучайте сотрудников на бегу")
            st.markdown(
                """
                **Нет времени сидеть за ноутбуком?** Мы запустили **Vyud AI Bot** в Telegram.
                
                1. 🤳 **Запишите "кружочек"** с инструкцией (или перешлите голосовое).
                2. 🤖 ИИ мгновенно превратит его в **тест**.
                3. 🚀 Перешлите тест сотрудникам за 30 секунд.
                
                Идеально для полевых сотрудников, отделов продаж и быстрых апдейтов.
                """
            )
            # Замените 'VyudBot' на реальный юзернейм вашего бота!
            st.link_button("👉 Открыть Telegram Бота", "https://t.me/VyudAiBot", type="primary")

        with c_promo_2:
            # Визуализация (можно потом заменить на скриншот телефона)
            st.info(
                """
                **Попробуйте прямо сейчас:**
                
                🎥 Запишите видео:
                *"Коллеги, с понедельника новый скрипт..."*
                
                👇
                
                ✅ **Тест готов!**
                """
            )

    # Главное окно
    st.title("🎓 Vyud AI")
    uploaded_file = st.file_uploader(t["upload_label"], type=["pdf", "pptx", "docx", "txt", "mp4", "mp3", "mov", "m4a"])
    
    if uploaded_file and 'file_name' not in st.session_state:
        st.session_state['file_name'] = uploaded_file.name

    if uploaded_file:
        if st.button(t["btn_create"]):
            if st.session_state['credits'] > 0:
                with st.spinner("⏳ Анализирую файл и создаю тест..."):
                    try:
                        # 1. Logic
                        text = logic.process_file_to_text(
                            uploaded_file, 
                            st.secrets["OPENAI_API_KEY"], 
                            st.secrets["LLAMA_CLOUD_API_KEY"]
                        )
                        
                        # 2. Generate
                        if text:
                            quiz = logic.generate_quiz_ai(text, quiz_count, quiz_difficulty, quiz_lang)
                            st.session_state['quiz'] = quiz
                            
                            # 3. Credits
                            auth.deduct_credit()
                            
                            st.balloons()
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error("Текст не найден.")
                            
                    except Exception as e:
                        st.error(f"Ошибка: {e}")
            else:
                st.error(t["no_credits"])

    # ВЫВОД РЕЗУЛЬТАТА
    if st.session_state['quiz']:
        t = TRANSLATIONS[ui_lang]
        st.divider()
        st.success(f"✅ Тест готов! Остаток: {st.session_state['credits']}")
        
        quiz = st.session_state['quiz']
        
        # HTML кнопка
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(t["preview_label"])
        with col2:
            course_name_file = st.session_state.get('file_name', 'Course')
            try:
                html_data = logic.create_html_quiz(quiz, course_name_file)
                st.download_button(
                    label=t["btn_download_html"],
                    data=html_data,
                    file_name=f"Quiz_{course_name_file}.html",
                    mime="text/html"
                )
            except Exception as e:
                st.error(f"Ошибка HTML: {e}")

        for i, q in enumerate(quiz.questions):
            st.write(f"**{i+1}. {q.scenario}**")
            
            if not q.options: continue
            safe_id = q.correct_option_id
            if safe_id >= len(q.options) or safe_id < 0: safe_id = 0
            
            st.radio("Ответы:", q.options, key=f"q{i}", label_visibility="collapsed")
            with st.expander("Показать правильный ответ"):
                st.write(f"**{t['q_correct']}** {q.options[safe_id]}")
                st.info(q.explanation)
            st.markdown("---")

        st.subheader(t["success_cert"])
        c1, c2 = st.columns(2)
        with c1: s_name = st.text_input("Student Name", "Ivan Ivanov")
        with c2: c_title = st.text_input("Course Name", st.session_state.get('file_name', 'Course'))
        
        if st.button(t["btn_download_cert"]):
            pdf_data = logic.create_certificate(s_name, c_title, company_logo)
            st.download_button("📥 PDF Сертификат", pdf_data, "certificate.pdf", "application/pdf")