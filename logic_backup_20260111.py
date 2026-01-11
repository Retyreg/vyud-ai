import streamlit as st
from openai import OpenAI
import json
import os
import PyPDF2
from docx import Document
import moviepy.editor as mp
from tempfile import NamedTemporaryFile
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- КОНФИГУРАЦИЯ ---
MODEL_GPT = "gpt-4o"
MODEL_WHISPER = "whisper-1"

class QuizQuestion:
    def __init__(self, scenario, options, correct_option_id, explanation=""):
        self.scenario = scenario
        self.options = options
        self.correct_option_id = correct_option_id
        self.explanation = explanation

class Quiz:
    def __init__(self, questions):
        self.questions = questions

def get_client(api_key):
    return OpenAI(api_key=api_key)

# --- 1. ОБРАБОТКА ФАЙЛОВ ---
def process_file_to_text(uploaded_file, api_key):
    client = get_client(api_key)
    file_ext = uploaded_file.name.split('.')[-1].lower()
    text_content = ""

    try:
        # PDF
        if file_ext == 'pdf':
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            for page in pdf_reader.pages: text_content += page.extract_text() + "\n"
        
        # DOCX
        elif file_ext in ['docx', 'doc']:
            doc = Document(uploaded_file)
            text_content = "\n".join([para.text for para in doc.paragraphs])
        
        # TEXT
        elif file_ext == 'txt':
            text_content = uploaded_file.getvalue().decode("utf-8")
        
        # ВИДЕО И АУДИО (ГЛАВНАЯ ЧАСТЬ)
        elif file_ext in ['mp4', 'mov', 'avi', 'mkv', 'mp3', 'wav', 'm4a', 'mpeg4', 'webm', 'wmv']:
            with st.status("🎬 Обработка видео/аудио...", expanded=True) as status:
                status.write("1. Извлекаем аудиодорожку...")
                text_content = transcribe_audio_video(uploaded_file, client, status)
                status.update(label="✅ Готово!", state="complete", expanded=False)

    except Exception as e:
        st.error(f"❌ Ошибка обработки файла: {e}")
        return ""

    if not text_content:
        st.warning("⚠️ Текст не извлечен. Возможно, файл пустой или видео без звука.")
    
    return text_content

def transcribe_audio_video(uploaded_file, client, status_container):
    try:
        # Сохраняем во временный файл
        suffix = f".{uploaded_file.name.split('.')[-1]}"
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp_video:
            tmp_video.write(uploaded_file.getvalue())
            tmp_video_path = tmp_video.name

        audio_path = tmp_video_path + "_converted.mp3"
        
        # Конвертация через MoviePy (требует FFMPEG)
        status_container.write("2. Конвертация в формат MP3 (32kbps)...")
        
        if suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.wmv', '.mpeg4']:
            video = mp.VideoFileClip(tmp_video_path)
            # Если видео длиннее 20 минут - режем
            if video.duration > 1200: 
                status_container.warning(f"Видео длинное ({int(video.duration)}с). Берем первые 20 мин.")
                video = video.subclip(0, 1200)
            
            video.audio.write_audiofile(audio_path, bitrate="32k", logger=None)
            video.close()
        else:
            # Аудио тоже прогоняем через конвертер для сжатия
            audio_clip = mp.AudioFileClip(tmp_video_path)
            audio_clip.write_audiofile(audio_path, bitrate="32k", logger=None)
            audio_clip.close()

        # Проверка размера
        size_mb = os.path.getsize(audio_path) / (1024*1024)
        status_container.write(f"3. Отправка в Whisper AI ({size_mb:.1f} MB)...")

        if size_mb > 24:
            st.error("Файл слишком большой (>25MB) даже после сжатия.")
            return ""

        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model=MODEL_WHISPER, file=audio_file, response_format="text"
            )
        
        # Чистка
        try: os.remove(tmp_video_path); os.remove(audio_path)
        except: pass
        
        return transcript

    except Exception as e:
        st.error(f"Ошибка транскрибации (FFMPEG/Whisper): {str(e)}")
        if "ffmpeg" in str(e).lower():
            st.error("🚨 На сервере не найден FFMPEG. Установите: sudo apt install ffmpeg")
        return ""

# --- 2. ГЕНЕРАЦИЯ ТЕСТА ---
def generate_quiz_ai(text, num_questions, difficulty, language):
    client = get_client(st.secrets["OPENAI_API_KEY"])
    if not text: return Quiz([])
    
    prompt = f"""
You are an expert quiz creator. Create an engaging quiz based on the following text.

TEXT:
{text[:25000]}

REQUIREMENTS:
- Language: {language}
- Difficulty: {difficulty}
- Number of questions: {num_questions}
- Each question must have exactly 4 options
- Include a brief explanation (1-2 sentences) for why the correct answer is right

OUTPUT FORMAT (strict JSON):
{{
  "questions": [
    {{
      "scenario": "Question text here?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_option_id": 0,
      "explanation": "Brief explanation why this answer is correct."
    }}
  ]
}}
"""
    try:
        response = client.chat.completions.create(
            model=MODEL_GPT,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return Quiz([QuizQuestion(q['scenario'], q['options'], q['correct_option_id'], q.get('explanation', '')) for q in data['questions']])
    except Exception as e: return Quiz([QuizQuestion(f"Error: {e}", ["OK"], 0)])

def generate_methodologist_hints(text, language):
    if not text: return "Нет текста."
    client = get_client(st.secrets["OPENAI_API_KEY"])
    try:
        res = client.chat.completions.create(
            model=MODEL_GPT, messages=[{"role": "user", "content": f"3 learning tips for: {text[:5000]}. Lang: {language}"}]
        )
        return res.choices[0].message.content
    except: return "Советы недоступны."

# --- 3. ЭКСПОРТ ---
def create_html_quiz(quiz_obj, filename):
    js_data = []
    for q in quiz_obj.questions:
        js_data.append({"question": q.scenario, "options": q.options, "correct": q.correct_option_id})
    json_str = json.dumps(js_data)
    
    html = f"""
    <!DOCTYPE html>
    <html><head><meta charset='UTF-8'><style>body{{font-family:sans-serif;padding:20px;max-width:800px;margin:0 auto}} .card{{border:1px solid #ccc;padding:15px;margin-bottom:15px;border-radius:8px}} .btn{{background:#007bff;color:white;padding:10px 20px;border:none;cursor:pointer}} .correct{{color:green;font-weight:bold}} .wrong{{color:red;font-weight:bold}}</style></head>
    <body><h1>Test: {filename}</h1><div id="q"></div><button class="btn" onclick="check()">Check</button><h2 id="sc"></h2>
    <script>const d={json_str}; function r(){{let h='';d.forEach((q,i)=>{{h+=`<div class='card'><h3>${{i+1}}. ${{q.question}}</h3>`;q.options.forEach((o,j)=>{{h+=`<label style='display:block'><input type='radio' name='q${{i}}' value='${{j}}'> ${{o}}</label>`}});h+=`<div id='r${{i}}'></div></div>`}});document.getElementById('q').innerHTML=h}} r();
    function check(){{let s=0;d.forEach((q,i)=>{{let el=document.querySelector(`input[name='q${{i}}']:checked`);let r=document.getElementById(`r${{i}}`);if(el&&parseInt(el.value)===q.correct){{s++;r.innerHTML="<span class='correct'>OK</span>"}}else{{r.innerHTML=`<span class='wrong'>Wrong. Answer: ${{q.options[q.correct]}}</span>`}}}});document.getElementById('sc').innerText=`Score: ${{s}}/${{d.length}}`}}</script></body></html>
    """
    return html.encode('utf-8')

def create_certificate(student_name, course_name, logo_file=None):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    c.setLineWidth(5); c.rect(30,30,width-60,height-60)
    c.setFont("Helvetica-Bold", 40); c.drawCentredString(width/2, height-150, "CERTIFICATE")
    c.setFont("Helvetica", 20); c.drawCentredString(width/2, height-220, "OF COMPLETION")
    c.setFont("Helvetica-Bold", 30); c.drawCentredString(width/2, height-300, student_name)
    c.setFont("Helvetica-Oblique", 20); c.drawCentredString(width/2, height-380, course_name)
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

# --- ТРАНСКРИПЦИЯ ДЛЯ БОТА (принимает путь к файлу) ---
def transcribe_for_bot(file_path):
    """Транскрибация для Telegram бота - принимает путь к файлу"""
    try:
        import os
        from openai import OpenAI
        
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Конвертация в mp3 (если это видео)
        audio_path = file_path + "_converted.mp3"
        
        if file_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
            video = mp.VideoFileClip(file_path)
            if video.duration > 1200:
                video = video.subclip(0, 1200)
            video.audio.write_audiofile(audio_path, bitrate="32k", logger=None)
            video.close()
        else:
            # Аудио - тоже конвертируем для сжатия
            audio_clip = mp.AudioFileClip(file_path)
            audio_clip.write_audiofile(audio_path, bitrate="32k", logger=None)
            audio_clip.close()
        
        # Проверка размера
        size_mb = os.path.getsize(audio_path) / (1024*1024)
        if size_mb > 24:
            return "Error: File too large"
        
        # Whisper
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", file=audio_file, response_format="text"
            )
        
        # Чистка
        try: 
            os.remove(file_path)
            os.remove(audio_path)
        except: pass
        
        return transcript
        
    except Exception as e:
        return f"Error: {str(e)}"
