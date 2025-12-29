import streamlit as st
import time
import os

# Наши модули
import auth
import logic

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(
    page_title="Vyud AI Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS для красоты
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    .css-1d391kg { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)

# --- ИНИЦИАЛИЗАЦИЯ СЕССИИ ---
if "user" not in st.session_state:
    st.session_state.user = None
if "generated_quiz" not in st.session_state:
    st.session_state.generated_quiz = None
if "quiz_text_source" not in st.session_state:
    st.session_state.quiz_text_source = None

# Достаем ключи API
try:
    OPENAI_KEY = st.secrets["OPENAI_API_KEY"]
    LLAMA_KEY = st.secrets["LLAMA_CLOUD_API_KEY"]
except:
    st.error("❌ Не найдены API ключи в secrets.toml!")
    st.stop()

# --- 1. БОКОВАЯ ПАНЕЛЬ (АВТОРИЗАЦИЯ) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4712/4712035.png", width=60)
    st.title("Vyud AI")
    st.caption("AI-платформа для L&D и HR")
    
    st.divider()

    if not st.session_state.user:
        st.subheader("Вход в систему")
        email = st.text_input("Email")
        password = st.text_input("Пароль", type="password")
        
        if st.button("Войти", type="primary"):
            if auth.check_password(email, password):
                st.session_state.user = email
                st.rerun()
            else:
                st.error("Неверный email или пароль")
    else:
        st.success(f"👤 {st.session_state.user}")
        
        # Баланс
        credits = auth.get_credits(st.session_state.user)
        st.metric("Баланс кредитов", credits)
        
        if st.button("Выйти"):
            st.session_state.user = None
            st.session_state.generated_quiz = None
            st.rerun()
            
    st.divider()
    st.info("ℹ️ MVP v1.0: Поддерживает PDF, DOCX, MP4, MP3.")

# --- 2. ОСНОВНОЙ ИНТЕРФЕЙС ---

if not st.session_state.user:
    st.warning("🔒 Пожалуйста, авторизуйтесь в боковой панели, чтобы начать работу.")
    st.stop()

# Вкладки функционала
tab1, tab2 = st.tabs(["🎓 Генератор Обучения", "📢 Маркетинг Помощник"])

# === ВКЛАДКА 1: ГЕНЕРАТОР ТЕСТОВ ===
with tab1:
    st.header("Создание интерактивного курса")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("1. Загрузка материала")
        uploaded_file = st.file_uploader("Файл (PDF, Video, Audio)", type=['pdf', 'docx', 'txt', 'mp4', 'mp3', 'm4a'])
        
        st.subheader("2. Настройки AI")
        q_count = st.slider("Количество вопросов", 3, 10, 5)
        difficulty = st.select_slider("Сложность", options=["Easy", "Medium", "Hard"], value="Medium")
        lang = st.selectbox("Язык курса", ["Russian", "English", "Kazakh"])
        
        generate_btn = st.button("✨ Сгенерировать курс (1 кредит)", type="primary")

    with col2:
        # Логика генерации
        if generate_btn and uploaded_file:
            if auth.deduct_credit(st.session_state.user, 1):
                status = st.status("🚀 Запускаем AI двигатели...", expanded=True)
                try:
                    # 1. Извлечение текста
                    status.write("📂 Читаем файл и распознаем речь...")
                    text_content = logic.process_file_to_text(uploaded_file, OPENAI_KEY, LLAMA_KEY)
                    st.session_state.quiz_text_source = text_content[:1000] + "..."
                    
                    # 2. Генерация теста
                    status.write("🧠 Проектируем сценарии обучения...")
                    quiz_data = logic.generate_quiz_ai(text_content, q_count, difficulty, lang)
                    st.session_state.generated_quiz = quiz_data
                    
                    status.update(label="✅ Готово! Курс создан.", state="complete", expanded=False)
                    
                except Exception as e:
                    status.update(label="❌ Ошибка!", state="error")
                    st.error(f"Произошла ошибка: {e}")
            else:
                st.error("💳 Недостаточно кредитов! Пожалуйста, пополните баланс.")

        # Отображение результатов
        if st.session_state.generated_quiz:
            quiz = st.session_state.generated_quiz
            st.success("Курс успешно сгенерирован!")
            
            with st.expander("👀 Предпросмотр вопросов"):
                for idx, q in enumerate(quiz.questions):
                    st.markdown(f"**{idx+1}. {q.scenario}**")
                    for opt in q.options:
                        st.text(f"- {opt}")
                    st.caption(f"💡 *{q.explanation}*")
            
            st.divider()
            st.subheader("3. Экспорт материалов")
            
            c1, c2 = st.columns(2)
            
            with c1:
                # Скачать HTML
                course_name = f"Course_{int(time.time())}"
                html_data = logic.create_html_quiz(quiz, course_name)
                st.download_button(
                    label="📥 Скачать HTML-тест",
                    data=html_data,
                    file_name=f"{course_name}.html",
                    mime="text/html"
                )
            
            with c2:
                # Скачать PDF Сертификат
                student_name = st.text_input("Имя студента для сертификата", "Иван Иванов")
                if st.button("📄 Сгенерировать PDF Сертификат"):
                    pdf_buffer = logic.create_certificate(student_name, "Корпоративное обучение")
                    st.download_button(
                        label="⬇️ Скачать PDF",
                        data=pdf_buffer,
                        file_name="Certificate.pdf",
                        mime="application/pdf"
                    )

# === ВКЛАДКА 2: МАРКЕТИНГ ===
with tab2:
    st.header("Генератор постов для соцсетей")
    st.caption("Помогает продвигать созданные курсы")
    
    m_topic = st.text_input("О чем пишем?", "Запуск нового курса по безопасности")
    c1, c2 = st.columns(2)
    m_platform = c1.selectbox("Платформа", ["LinkedIn", "Instagram", "Telegram", "Email Newsletter"])
    m_tone = c2.selectbox("Тон", ["Professional", "Friendly", "Urgent", "Educational"])
    
    if st.button("✍️ Написать пост (1 кредит)"):
        if auth.deduct_credit(st.session_state.user, 1):
            with st.spinner("Копирайтер пишет текст..."):
                post_text = logic.generate_marketing_post(m_topic, m_platform, m_tone)
                st.text_area("Результат:", post_text, height=300)
        else:
            st.error("Недостаточно кредитов.")