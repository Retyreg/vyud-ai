import streamlit as st
import os
import tempfile
import io
import time
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# --- БИБЛИОТЕКИ ДЛЯ ФУНКЦИОНАЛА (ТВОИ) ---
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader, Settings
from llama_index.llms.openai import OpenAI
from llama_index.core.program import LLMTextCompletionProgram
from pydantic import BaseModel, Field
from typing import List
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.utils import ImageReader

# ==========================================
# 1. НАСТРОЙКИ И ИНИЦИАЛИЗАЦИЯ
# ==========================================
st.set_page_config(page_title="Vyud AI", page_icon="🎓", layout="wide")
load_dotenv()

# Проверка ключей в secrets (должны быть в .streamlit/secrets.toml)
required_keys = ["OPENAI_API_KEY", "LLAMA_CLOUD_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]
missing_keys = [key for key in required_keys if key not in st.secrets]

if missing_keys:
    st.error(f"❌ Не найдены ключи в secrets.toml: {', '.join(missing_keys)}")
    st.stop()

# Инициализация клиентов
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
os.environ["LLAMA_CLOUD_API_KEY"] = st.secrets["LLAMA_CLOUD_API_KEY"]
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# Инициализация Session State
if 'user' not in st.session_state: st.session_state['user'] = None
if 'credits' not in st.session_state: st.session_state['credits'] = 0
if 'quiz' not in st.session_state: st.session_state['quiz'] = None

# ==========================================
# 2. ФУНКЦИИ АВТОРИЗАЦИИ И БИЛЛИНГА
# ==========================================
def login_user(email):
    """Вход или регистрация через Supabase"""
    email = email.lower().strip()
    # Проверка юзера
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
        try:
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
    email = st.session_state['user']
    current = st.session_state['credits']
    if current > 0:
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

# ==========================================
# 3. ТВОЙ ФУНКЦИОНАЛ (КЛАССЫ И ФУНКЦИИ)
# ==========================================

# Локализация
TRANSLATIONS = {
    "Русский": {
        "branding_header": "🏢 Брендинг",
        "logo_label": "Логотип компании (PNG/JPG)",
        "settings_header": "⚙️ Настройки генерации",
        "ui_lang_label": "Язык интерфейса:",
        "target_lang_label": "Язык теста:",
        "target_lang_placeholder": "Например: Italian, Hindi...",
        "target_lang_caption": "AI переведет материал на этот язык.",
        "difficulty_label": "Сложность:",
        "diff_easy": "Easy (Факты)",
        "diff_medium": "Medium (Понимание)",
        "diff_hard": "Hard (Кейсы)",
        "count_label": "Количество вопросов:",
        "contact_header": "📬 Поддержка",
        "upload_label": "Загрузи материал (PDF, PPTX, DOCX, XLSX, TXT)",
        "btn_create": "🚀 Создать Тест (1 кредит)",
        "spinner_read": "📄 Читаю документ (LlamaParse)...",
        "spinner_ai": "🧠 Генерирую вопросы...",
        "error_read": "Ошибка чтения файла.",
        "success_cert": "🏆 Сертификация",
        "cert_name_label": "Имя студента:",
        "cert_course_label": "Название курса:",
        "btn_download_cert": "📄 Скачать Сертификат",
        "no_credits": "⚠️ Недостаточно кредитов! Пополните баланс.",
        "q_correct": "Правильно:"
    },
    "English": {
        "branding_header": "🏢 Branding",
        "logo_label": "Company Logo (PNG/JPG)",
        "settings_header": "⚙️ Generation Settings",
        "ui_lang_label": "Interface Language:",
        "target_lang_label": "Target Quiz Language:",
        "target_lang_placeholder": "E.g.: Italian, Hindi...",
        "target_lang_caption": "AI translates content automatically.",
        "difficulty_label": "Difficulty:",
        "diff_easy": "Easy (Facts)",
        "diff_medium": "Medium (Understanding)",
        "diff_hard": "Hard (Case Studies)",
        "count_label": "Questions Count:",
        "contact_header": "📬 Support",
        "upload_label": "Upload material (PDF, PPTX, DOCX, XLSX, TXT)",
        "btn_create": "🚀 Create Quiz (1 credit)",
        "spinner_read": "📄 Reading document (LlamaParse)...",
        "spinner_ai": "🧠 Generating questions...",
        "error_read": "Error reading file.",
        "success_cert": "🏆 Certification",
        "cert_name_label": "Student Name:",
        "cert_course_label": "Course Title:",
        "btn_download_cert": "📄 Download Certificate",
        "no_credits": "⚠️ Not enough credits! Please top up.",
        "q_correct": "Correct:"
    }
}

class QuizQuestion(BaseModel):
    scenario: str = Field(..., description="Question text")
    options: List[str] = Field(..., description="4 options")
    correct_option_id: int = Field(..., description="Index 0-3")
    explanation: str = Field(..., description="Explanation")

class Quiz(BaseModel):
    questions: List[QuizQuestion]

def create_certificate(student_name, course_name, logo_file=None):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)
    
    c.setStrokeColorRGB(0.2, 0.2, 0.2)
    c.setLineWidth(5)
    c.rect(30, 30, width-60, height-60)
    
    if logo_file:
        try:
            logo_file.seek(0)
            logo = ImageReader(logo_file)
            c.drawImage(logo, width/2 - 50, height - 140, width=100, preserveAspectRatio=True, mask='auto')
        except:
            pass

    c.setFont("Helvetica-Bold", 40)
    c.drawCentredString(width/2, height/2 + 40, "CERTIFICATE")
    c.setFont("Helvetica", 20)
    c.drawCentredString(width/2, height/2, "OF COMPLETION")
    c.setFont("Helvetica", 16)
    c.drawCentredString(width/2, height/2 - 30, "This is to certify that")
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(width/2, height/2 - 70, student_name)
    c.setFont("Helvetica", 16)
    c.drawCentredString(width/2, height/2 - 100, "has successfully completed the course")
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, height/2 - 130, course_name)
    c.setFont("Helvetica", 12)
    date_str = datetime.now().strftime("%Y-%m-%d")
    c.drawString(50, 50, f"Date: {date_str}")
    c.drawRightString(width-50, 50, "Authorized by Vyud AI")
    c.save()
    buffer.seek(0)
    return buffer

# ==========================================
# 4. ЛОГИКА ИНТЕРФЕЙСА (ГЛАВНАЯ)
# ==========================================

# --- СЦЕНАРИЙ 1: НЕ АВТОРИЗОВАН ---
if st.session_state['user'] is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🎓 Vyud AI")
        st.info("Пожалуйста, войдите, чтобы начать создание курсов.")
        email_input = st.text_input("Ваш Email")
        if st.button("Войти / Регистрация"):
            if "@" in email_input:
                login_user(email_input)
            else:
                st.warning("Некорректный Email")
        st.caption("Новым пользователям: 3 генерации бесплатно.")

# --- СЦЕНАРИЙ 2: АВТОРИЗОВАН (ТВОЙ КОД) ---
else:
    # Сайдбар: Профиль + Твои настройки
    with st.sidebar:
        st.write(f"👤 **{st.session_state['user']}**")
        st.metric("Доступно кредитов", st.session_state['credits'])
        if st.button("Выйти"): logout()
        st.divider()

        # ТВОИ НАСТРОЙКИ
        ui_language = st.selectbox("🌐 Language", list(TRANSLATIONS.keys()), index=0)
        t = TRANSLATIONS[ui_language]

        st.header(t["branding_header"])
        company_logo = st.file_uploader(t["logo_label"], type=["png", "jpg", "jpeg"])
        if company_logo: st.image(company_logo, width=100)
        
        st.divider()
        st.header(t["settings_header"])
        
        quiz_lang = st.text_input(t["target_lang_label"], value="Русский" if ui_language == "Русский" else "English", placeholder=t["target_lang_placeholder"])
        st.caption(t["target_lang_caption"])
        
        quiz_difficulty = st.radio(t["difficulty_label"], [t["diff_easy"], t["diff_medium"], t["diff_hard"]], index=1)
        quiz_count = st.slider(t["count_label"], 1, 10, 5)
        
        st.divider()
        st.markdown(f"**{t['contact_header']}**: [Telegram](https://t.me/retyreg)")

    # Основной экран
    st.title("🎓 Vyud AI")
    
    uploaded_file = st.file_uploader(t["upload_label"], type=["pdf", "pptx", "docx", "xlsx", "txt"])
    if uploaded_file and 'file_name' not in st.session_state:
        st.session_state['file_name'] = uploaded_file.name

    if uploaded_file:
        # ПРОВЕРКА КНОПКИ ГЕНЕРАЦИИ И КРЕДИТОВ
        if st.button(t["btn_create"]):
            if st.session_state['credits'] > 0:
                # 1. Читаем файл (LlamaParse)
                file_ext = os.path.splitext(uploaded_file.name)[1].lower()
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name

                text = ""
                with st.spinner(t["spinner_read"]):
                    try:
                        parser = LlamaParse(result_type="markdown", api_key=os.environ["LLAMA_CLOUD_API_KEY"])
                        file_extractor = {".pdf": parser, ".pptx": parser, ".docx": parser, ".xlsx": parser, ".txt": parser}
                        docs = SimpleDirectoryReader(input_files=[tmp_path], file_extractor=file_extractor).load_data()
                        if docs: text = docs[0].text
                        else: st.error(t["error_read"]); st.stop()
                    except Exception as e:
                        st.error(f"Error: {e}"); st.stop()

                # 2. Генерируем тест (OpenAI)
                target_lang = quiz_lang if quiz_lang.strip() else "English"
                with st.spinner(f"{t['spinner_ai']} ({target_lang})..."):
                    try:
                        Settings.llm = OpenAI(model="gpt-4o", temperature=0.1)
                        prompt = (
                            f"You are an expert instructional designer. "
                            f"1. Analyze content. 2. Create quiz in '{target_lang}'. "
                            f"3. Questions: {quiz_count}. 4. Diff: {quiz_difficulty}. "
                            "Return STRICTLY JSON format matching the Quiz schema."
                        )
                        program = LLMTextCompletionProgram.from_defaults(
                            output_cls=Quiz,
                            prompt_template_str=prompt + " Content: {text}",
                            llm=Settings.llm
                        )
                        result = program(text=text[:25000])
                        st.session_state['quiz'] = result
                        
                        # 3. СПИСЫВАЕМ КРЕДИТ (Только если всё успешно)
                        deduct_credit()
                        st.rerun() # Перезагрузка, чтобы обновить счетчик
                        
                    except Exception as e:
                        st.error(f"AI Error: {e}")
            else:
                st.error(t["no_credits"])

    # ВЫВОД РЕЗУЛЬТАТА (Если тест уже сгенерирован)
    if st.session_state['quiz']:
        t = TRANSLATIONS[ui_language] # Обновляем перевод для этой части
        st.divider()
        st.success(f"✅ Тест готов! Остаток кредитов: {st.session_state['credits']}")
        
        quiz = st.session_state['quiz']
        for i, q in enumerate(quiz.questions):
            st.subheader(f"{i+1}. {q.scenario}")
            st.radio("Варианты:", q.options, key=f"q{i}")
            with st.expander("Показать ответ"):
                st.write(f"{t['q_correct']} {q.options[q.correct_option_id]}")
                st.info(q.explanation)

        st.divider()
        st.subheader(t["success_cert"])
        
        c1, c2 = st.columns(2)
        with c1: student_name = st.text_input(t["cert_name_label"], "Ivan Ivanov")
        with c2: 
            course_def = st.session_state.get('file_name', 'Course')
            course_title = st.text_input(t["cert_course_label"], course_def)
            
        if st.button(t["btn_download_cert"]):
            pdf_data = create_certificate(student_name, course_title, company_logo)
            st.download_button(
                label="📥 Скачать PDF",
                data=pdf_data,
                file_name=f"Certificate_{student_name}.pdf",
                mime="application/pdf"
            )