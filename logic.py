import os
import tempfile
import io
import logging
from datetime import datetime

# Библиотеки AI
from openai import OpenAI as OpenAIClient
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader, Settings
from llama_index.llms.openai import OpenAI
from llama_index.core.program import LLMTextCompletionProgram
from pydantic import BaseModel, Field
from typing import List

# Библиотеки для работы с видео/аудио
from moviepy.editor import VideoFileClip
from pydub import AudioSegment

# Библиотеки PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import textwrap

# --- МОДЕЛИ ДАННЫХ ---
class QuizQuestion(BaseModel):
    scenario: str = Field(..., description="Текст вопроса")
    options: List[str] = Field(..., description="Варианты ответов (максимум 4)")
    correct_option_id: int = Field(..., description="Индекс правильного ответа (0, 1, 2 или 3)")
    explanation: str = Field(..., description="Короткое объяснение (почему ответ верен)")

class Quiz(BaseModel):
    questions: List[QuizQuestion]

# --- 0. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (ШРИФТЫ) ---
def register_fonts():
    """Регистрирует кириллический шрифт, чтобы PDF не ломался на Linux."""
    font_path = "assets/DejaVuSans.ttf" # Убедись, что файл есть в папке assets!
    try:
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('DejaVu', font_path))
            return 'DejaVu'
        else:
            return 'Helvetica'
    except:
        return 'Helvetica'

# --- 1. ОБРАБОТКА ФАЙЛОВ ---
def compress_audio(input_path):
    """Сжимает аудио/видео для Whisper (лимит 25мб)."""
    try:
        if not os.path.exists(input_path): return input_path
        file_size = os.path.getsize(input_path) / (1024 * 1024)
        
        if file_size < 24 and not input_path.endswith(('.mp4', '.mov')):
            return input_path

        output_path = os.path.splitext(input_path)[0] + "_compressed.mp3"
        
        if input_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
            video = VideoFileClip(input_path)
            video.audio.write_audiofile(output_path, bitrate="32k", logger=None)
            video.close()
            return output_path
        elif file_size > 24:
            audio = AudioSegment.from_file(input_path)
            audio.export(output_path, format="mp3", bitrate="32k")
            return output_path
            
        return input_path
    except Exception as e:
        print(f"Ошибка сжатия: {e}")
        return input_path

def process_file_to_text(uploaded_file, openai_key, llama_key):
    """Парсит PDF, DOCX, Video, Audio в текст."""
    text = ""
    tmp_path = ""
    is_temp = False

    try:
        if isinstance(uploaded_file, str):
            tmp_path = uploaded_file 
        else:
            file_ext = os.path.splitext(uploaded_file.name)[1].lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            is_temp = True

        ext = os.path.splitext(tmp_path)[1].lower()
        
        # --- AUDIO / VIDEO ---
        if ext in [".mp4", ".mov", ".avi", ".mp3", ".mpeg", ".m4a", ".wav", ".ogg"]:
            processed_path = compress_audio(tmp_path)
            client = OpenAIClient(api_key=openai_key)
            with open(processed_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1", file=audio_file, response_format="json"
                )
            if processed_path != tmp_path and "_compressed" in processed_path:
                try: os.remove(processed_path)
                except: pass
            
            text = transcription.text if hasattr(transcription, 'text') else str(transcription)
        
        # --- DOCUMENTS ---
        else:
            if not llama_key: llama_key = os.environ.get("LLAMA_CLOUD_API_KEY", "")
            parser = LlamaParse(result_type="markdown", api_key=llama_key)
            file_extractor = {".pdf": parser, ".pptx": parser, ".docx": parser, ".txt": parser}
            docs = SimpleDirectoryReader(input_files=[tmp_path], file_extractor=file_extractor).load_data()
            text = "\n\n".join([doc.text for doc in docs]) if docs else ""
            
    except Exception as e:
        return f"Error processing file: {str(e)}"
    finally:
        if is_temp and os.path.exists(tmp_path): 
            try: os.remove(tmp_path)
            except: pass
            
    return text

# --- 2. ГЕНЕРАЦИЯ КОНТЕНТА (AI) ---

def generate_quiz_ai(text, count=5, difficulty="Medium", lang="Russian"):
    """Генерирует JSON структуру теста."""
    if not text or len(text) < 50: return None

    Settings.llm = OpenAI(model="gpt-4o", temperature=0.3)
    
    system_prompt = (
        f"You are a professional teacher. Create a quiz based on the provided text. "
        f"Language: {lang}. Difficulty: {difficulty}. Number of questions: {count}. "
        f"Generate a valid JSON object matching the Quiz schema. "
        f"Keep questions concise."
    )
    
    program = LLMTextCompletionProgram.from_defaults(
        output_cls=Quiz,
        prompt_template_str=system_prompt + "\n\nTEXT:\n{text}",
        llm=Settings.llm
    )
    
    try:
        return program(text=text[:50000])
    except Exception as e:
        logging.error(f"GPT Error: {e}")
        return None

# [ВОТ ОНА! Та самая функция, которой не хватало]
def generate_methodologist_hints(text, lang="Russian"):
    """Генерирует советы для улучшения материала."""
    try:
        client = OpenAIClient(api_key=os.environ.get("OPENAI_API_KEY"))
        prompt = (
            f"Analyze this educational text and give 3 short, actionable tips for a methodologist "
            f"on how to improve it (e.g. structure, clarity, examples). "
            f"Language: {lang}. Text snippet: {text[:2000]}"
        )
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except:
        return "Не удалось сгенерировать подсказки."

def generate_marketing_post(topic, platform, tone, context=""):
    """Генерирует текст поста (для админки)."""
    try:
        client = OpenAIClient(api_key=os.environ.get("OPENAI_API_KEY"))
        prompt = (
            f"Write a marketing post. Topic: {topic}. Platform: {platform}. Tone: {tone}. "
            f"Context: {context}. Language: Russian. Use emojis."
        )
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"

# --- 3. ГЕНЕРАЦИЯ ДОКУМЕНТОВ (PDF/HTML) ---

def create_certificate(user_name, course_name):
    """Генерирует PDF сертификат."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)
    
    font_name = register_fonts()
    
    c.setStrokeColorRGB(0.2, 0.4, 0.8)
    c.setLineWidth(5)
    c.rect(30, 30, width-60, height-60)
    
    c.setFont(font_name, 36)
    c.drawCentredString(width/2, height - 100, "СЕРТИФИКАТ")
    
    c.setFont(font_name, 18)
    c.drawCentredString(width/2, height - 140, "Подтверждает, что")
    
    c.setFont(font_name, 30)
    c.drawCentredString(width/2, height - 200, user_name)
    
    c.setFont(font_name, 16)
    c.drawCentredString(width/2, height - 250, "Успешно прошел(ла) тестирование по теме:")
    
    c.setFont(font_name, 22)
    c.drawCentredString(width/2, height - 290, course_name)
    
    date_str = datetime.now().strftime("%d.%m.%Y")
    c.setFont(font_name, 12)
    c.drawString(50, 50, f"Дата: {date_str}")
    c.drawRightString(width-50, 50, "VYUD AI Platform")
    
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

def create_html_quiz(quiz_obj, title):
    """Генерирует HTML файл."""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>{title}</title>
        <style>
            body {{ font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .question {{ margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 8px; }}
            .correct {{ color: green; font-weight: bold; }}
            .wrong {{ color: red; }}
            .hidden {{ display: none; }}
            button {{ padding: 10px 20px; background: #007bff; color: white; border: none; cursor: pointer; }}
        </style>
    </head>
    <body>
        <h1>Тест: {title}</h1>
    """
    
    for i, q in enumerate(quiz_obj.questions):
        html_content += f"""
        <div class="question" id="q{i}">
            <h3>{i+1}. {q.scenario}</h3>
            <div class="options">
        """
        for j, opt in enumerate(q.options):
            html_content += f"""
                <label>
                    <input type="radio" name="q{i}" value="{j}" onclick="check({i}, {j}, {q.correct_option_id})"> 
                    {opt}
                </label><br>
            """
        html_content += f"""
            </div>
            <p id="res{i}" class="result"></p>
            <p id="expl{i}" class="hidden">💡 {q.explanation}</p>
        </div>
        """

    html_content += """
        <script>
            function check(qId, selected, correct) {
                const res = document.getElementById('res' + qId);
                const expl = document.getElementById('expl' + qId);
                if (selected === correct) {
                    res.innerHTML = "✅ Верно!";
                    res.className = "correct";
                } else {
                    res.innerHTML = "❌ Ошибка";
                    res.className = "wrong";
                }
                expl.classList.remove('hidden');
            }
        </script>
    </body>
    </html>
    """
    return html_content

# --- 4. АДАПТЕРЫ ДЛЯ БОТА ---
def transcribe_audio(file_path):
    return process_file_to_text(file_path, os.environ.get("OPENAI_API_KEY"), None)

def generate_quiz_struct(text):
    return generate_quiz_ai(text)
