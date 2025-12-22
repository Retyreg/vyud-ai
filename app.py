import streamlit as st
import os
from dotenv import load_dotenv

# ИМПОРТ НАШИХ МОДУЛЕЙ
import auth
import logic
import streamlit as st
import os
import time  # <--- ДОБАВИТЬ ЭТУ СТРОКУ
from dotenv import load_dotenv

# 1. НАСТРОЙКИ
st.set_page_config(page_title="Vyud AI", page_icon="🎓", layout="wide")
load_dotenv()

# Установка ключей в переменные окружения (для Logic)
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
os.environ["LLAMA_CLOUD_API_KEY"] = st.secrets["LLAMA_CLOUD_API_KEY"]

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
        "preview_label": "Предпросмотр теста:"
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
        "preview_label": "Quiz Preview:"
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

        st.header(t["branding_header"])
        company_logo = st.file_uploader(t["logo_label"], type=["png", "jpg", "jpeg"])
        if company_logo: st.image(company_logo, width=100)
        
        st.divider()
        st.header(t["settings_header"])
        quiz_lang = st.text_input(t["target_lang_label"], value="Russian" if ui_lang=="Русский" else "English")
        quiz_difficulty = st.radio(t["difficulty_label"], ["Easy", "Medium", "Hard"])
        quiz_count = st.slider(t["count_label"], 1, 10, 5)

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
                        # 1. Извлекаем текст (LOGIC)
                        text = logic.process_file_to_text(
                            uploaded_file, 
                            st.secrets["OPENAI_API_KEY"], 
                            st.secrets["LLAMA_CLOUD_API_KEY"]
                        )
                        
                        # 2. Генерируем тест (LOGIC)
                        if text:
                            quiz = logic.generate_quiz_ai(text, quiz_count, quiz_difficulty, quiz_lang)
                            st.session_state['quiz'] = quiz
                            
                            # 3. Списываем кредит (AUTH)
                            auth.deduct_credit()
                            
                            # --- [START] WOW-ЭФФЕКТ ---
                            st.balloons()          # Запускаем шарики
                            time.sleep(1.5)        # Ждем 1.5 секунды, чтобы пользователь их увидел
                            # --- [END] WOW-ЭФФЕКТ ---
                            
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
        
        # --- [START] КНОПКА СКАЧИВАНИЯ HTML ---
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(t["preview_label"])
        with col2:
            course_name_file = st.session_state.get('file_name', 'Course')
            # Генерируем HTML через функцию в logic.py
            try:
                html_data = logic.create_html_quiz(quiz, course_name_file)
                st.download_button(
                    label=t["btn_download_html"],
                    data=html_data,
                    file_name=f"Quiz_{course_name_file}.html",
                    mime="text/html"
                )
            except Exception as e:
                st.error(f"Ошибка генерации HTML: {e}")
        # --- [END] КНОПКА СКАЧИВАНИЯ HTML ---

        for i, q in enumerate(quiz.questions):
            st.write(f"**{i+1}. {q.scenario}**")
            
            # Защита от ошибок индекса
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