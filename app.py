import streamlit as st
import os
import tempfile
import base64
import io
from datetime import datetime
from dotenv import load_dotenv
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader, Settings
from llama_index.llms.openai import OpenAI
from llama_index.core.program import LLMTextCompletionProgram
from pydantic import BaseModel, Field
from typing import List
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="V.Tech_AI Course Factory", page_icon="🎓", layout="wide")
load_dotenv()

# --- СТРУКТУРА ДАННЫХ ---
class QuizQuestion(BaseModel):
    scenario: str = Field(..., description="Описание ситуации")
    options: List[str] = Field(..., description="4 варианта ответа")
    correct_option_id: int = Field(..., description="Индекс правильного ответа (0-3)")
    explanation: str = Field(..., description="Объяснение")

class Quiz(BaseModel):
    questions: List[QuizQuestion]

# --- ФУНКЦИЯ ГЕНЕРАЦИИ СЕРТИФИКАТА (PDF) ---
def create_certificate(student_name, course_name, logo_file=None):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)
    
    # Рамка
    c.setStrokeColorRGB(0.2, 0.2, 0.2)
    c.setLineWidth(5)
    c.rect(30, 30, width-60, height-60)
    
    # Логотип (если есть)
    if logo_file:
        try:
            logo_file.seek(0)
            logo = ImageReader(logo_file)
            # Рисуем лого по центру сверху
            c.drawImage(logo, width/2 - 50, height - 140, width=100, preserveAspectRatio=True, mask='auto')
        except:
            pass # Если ошибка с картинкой, просто пропускаем

    # Текст сертификата
    # Примечание: ReportLab по умолчанию не поддерживает кириллицу без шрифтов.
    # Для MVP используем транслит или английский, либо стандартный шрифт (который может не показать русские буквы).
    # Чтобы не усложнять установкой шрифтов сейчас, сделаем текст на английском/универсальным.
    
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
    c.drawRightString(width-50, 50, "Authorized by AI CourseFlow")
    
    c.save()
    buffer.seek(0)
    return buffer

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.header("🏢 Брендинг")
    company_logo = st.file_uploader("Логотип компании (PNG/JPG)", type=["png", "jpg", "jpeg"])
    if company_logo:
        st.image(company_logo, width=100)

    st.divider()
    st.header("⚙️ Настройки")
    
    quiz_lang = st.selectbox(
        "Язык теста:",
        ["Русский", "English", "Қазақша", "O'zbekcha", "Кыргызча", "Español", "Deutsch"],
        index=0
    )
    
    quiz_difficulty = st.radio(
        "Сложность:",
        ["Easy (Факты)", "Hard (Кейсы)"],
        index=1
    )
    
    quiz_count = st.slider("Количество вопросов:", 1, 10, 3)

# --- ОСНОВНОЙ ЭКРАН ---
st.title("🎓 FlowCourse AI - Test Generator")

# БЕЗОПАСНАЯ ПРОВЕРКА КЛЮЧЕЙ
has_llama = bool(os.getenv("LLAMA_CLOUD_API_KEY"))
has_openai = bool(os.getenv("OPENAI_API_KEY"))

if has_llama and has_openai:
    st.success("✅ Ключи активны (Secure Mode)")
else:
    st.warning("⚠️ Ключи не найдены. Введите их вручную:")
    new_llama = st.text_input("LlamaCloud Key", type="password")
    new_openai = st.text_input("OpenAI Key", type="password")
    
    if new_llama and new_openai:
        os.environ["LLAMA_CLOUD_API_KEY"] = new_llama
        os.environ["OPENAI_API_KEY"] = new_openai
        st.rerun()

uploaded_file = st.file_uploader("ЗАГРУЗТЕ ФАЙЛ (PDF или PPTX)", type=["pdf", "pptx"])

# Храним название файла в сессии
if uploaded_file and 'file_name' not in st.session_state:
    st.session_state['file_name'] = uploaded_file.name

if uploaded_file:
    if st.button("🚀 Создать Тест/Make a Test"):
        
        if not os.environ.get("LLAMA_CLOUD_API_KEY"):
            st.error("Нет ключей!")
            st.stop()

        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        with st.spinner("📄 Читаю слайды и текст/Reading slides and text..."):
            try:
                parser = LlamaParse(result_type="markdown", language="ru", api_key=os.environ["LLAMA_CLOUD_API_KEY"])
                file_extractor = {".pdf": parser, ".pptx": parser}
                docs = SimpleDirectoryReader(input_files=[tmp_path], file_extractor=file_extractor).load_data()
                if not docs:
                    st.error("Ошибка чтения файла.")
                    st.stop()
                text = docs[0].text
            except Exception as e:
                st.error(f"Ошибка парсинга: {e}")
                st.stop()

        with st.spinner(f"🧠 Анализирую контент/Analysing content ({quiz_lang})..."):
            try:
                Settings.llm = OpenAI(model="gpt-4o", temperature=0.1)
                prompt = (
                    f"Проанализируй этот учебный материал. Создай тест на языке: {quiz_lang}. "
                    f"Количество вопросов: {quiz_count}. "
                    f"Сложность: {quiz_difficulty}. "
                    "Верни СТРОГО JSON."
                )
                program = LLMTextCompletionProgram.from_defaults(
                    output_cls=Quiz,
                    prompt_template_str=prompt + " Текст: {text}",
                    llm=Settings.llm
                )
                result = program(text=text[:20000])
                st.session_state['quiz'] = result
            except Exception as e:
                st.error(f"Ошибка AI: {e}")
                st.stop()

# --- ВЫВОД РЕЗУЛЬТАТА ---
if 'quiz' in st.session_state:
    st.divider()
    
    # 1. СЕКЦИЯ ВОПРОСОВ
    for i, q in enumerate(st.session_state['quiz'].questions):
        st.subheader(f"{i+1}. {q.scenario}")
        st.radio("Варианты:", q.options, key=f"q{i}")
        with st.expander("Показать ответ"):
            st.write(f"Правильно: {q.options[q.correct_option_id]}")
            st.info(q.explanation)

    st.divider()
    
    # 2. СЕКЦИЯ СЕРТИФИКАТА (НОВАЯ)
    st.subheader("🏆 Генерация сертификата")
    col1, col2 = st.columns(2)
    with col1:
        student_name = st.text_input("Имя студента (на латинице):", "Ivan Ivanov")
    with col2:
        # Берем название курса из имени файла или ставим дефолтное
        course_default = st.session_state.get('file_name', 'Corporate Training')
        course_title = st.text_input("Название курса:", course_default)
    
    if st.button("📄 Сгенерировать Сертификат"):
        pdf_data = create_certificate(student_name, course_title, company_logo)
        st.download_button(
            label="📥 Скачать PDF Сертификат",
            data=pdf_data,
            file_name=f"Certificate_{student_name}.pdf",
            mime="application/pdf"
        )

    st.divider()
    st.subheader("📦 Экспорт курса (HTML)")
    
    # ЛОГИКА ЭКСПОРТА В HTML
    logo_html = ""
    if company_logo:
        company_logo.seek(0)
        b64_data = base64.b64encode(company_logo.read()).decode()
        mime_type = company_logo.type
        logo_html = f'<img src="data:{mime_type};base64,{b64_data}" style="max-width: 150px; margin-bottom: 20px;">'

    quiz_json = st.session_state['quiz'].model_dump_json()
    
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Course Export</title>
        <style>
            body {{ font-family: sans-serif; max_width: 800px; margin: 0 auto; padding: 20px; background: #f4f4f9; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .card {{ background: white; padding: 20px; margin-bottom: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            .btn {{ display: inline-block; padding: 10px 20px; background: #007bff; color: white; cursor: pointer; border-radius: 5px; }}
            .btn:hover {{ background: #0056b3; }}
            .feedback {{ margin-top: 10px; font-weight: bold; display: none; }}
            .correct {{ color: green; }}
            .wrong {{ color: red; }}
        </style>
    </head>
    <body>
        <div class="header">
            {logo_html}
            <h1>🎓 Экзамен / Test</h1>
        </div>
        <div id="quiz-container"></div>
        <script>
            const quizData = {quiz_json};
            const container = document.getElementById('quiz-container');
            quizData.questions.forEach((q, index) => {{
                const card = document.createElement('div');
                card.className = 'card';
                let optionsHtml = '';
                q.options.forEach(opt => {{
                    optionsHtml += `<label style="display:block; margin: 5px 0; cursor: pointer;">
                        <input type="radio" name="q${{index}}" value="${{opt}}"> ${{opt}}
                    </label>`;
                }});
                card.innerHTML = `<h3>${{index + 1}}. ${{q.scenario}}</h3><form>${{optionsHtml}}</form><div class="btn" onclick="checkAnswer(${{index}})">Проверить</div><div class="feedback" id="feedback-${{index}}"></div>`;
                container.appendChild(card);
            }});
            function checkAnswer(index) {{
                const q = quizData.questions[index];
                const selected = document.querySelector(`input[name="q${{index}}"]:checked`);
                const fb = document.getElementById(`feedback-${{index}}`);
                if (!selected) return alert("Выберите ответ!");
                fb.style.display = 'block';
                const correct = q.options[q.correct_option_id];
                if (selected.value === correct) {{
                    fb.className = 'feedback correct';
                    fb.innerHTML = "✅ " + q.explanation;
                }} else {{
                    fb.className = 'feedback wrong';
                    fb.innerHTML = "❌ Правильный ответ: " + correct;
                }}
            }}
        </script>
    </body>
    </html>
    """

    st.download_button(
        label="📥 Скачать брендированный HTML",
        data=html_template,
        file_name="branded_course.html",
        mime="text/html"
    )