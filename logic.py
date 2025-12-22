import os
import tempfile
import io
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

# --- МОДЕЛИ ДАННЫХ ---
class QuizQuestion(BaseModel):
    scenario: str = Field(..., description="Question text")
    options: List[str] = Field(..., description="4 options")
    correct_option_id: int = Field(..., description="Index 0-3")
    explanation: str = Field(..., description="Explanation")

class Quiz(BaseModel):
    questions: List[QuizQuestion]

# --- ФУНКЦИИ ОБРАБОТКИ ---

def compress_audio(input_path):
    """
    Превращает видео/аудио в MP3 и сжимает, если файл > 25MB.
    Возвращает путь к новому файлу.
    """
    file_size = os.path.getsize(input_path) / (1024 * 1024) # Размер в МБ
    output_path = input_path + "_compressed.mp3"
    
    # Если файл уже маленький и это MP3/M4A/WAV, можно не трогать, 
    # но для надежности лучше всегда конвертировать в MP3, если это видео.
    
    try:
        # Если это видео, достаем звук
        if input_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
            video = VideoFileClip(input_path)
            video.audio.write_audiofile(output_path, bitrate="32k", logger=None) # Сильное сжатие 32k
            video.close()
            return output_path
            
        # Если это аудио, но тяжелое
        elif file_size > 24:
            audio = AudioSegment.from_file(input_path)
            # Экспорт с низким битрейтом
            audio.export(output_path, format="mp3", bitrate="32k")
            return output_path
            
        else:
            return input_path # Возвращаем как есть
            
    except Exception as e:
        print(f"Ошибка сжатия: {e}")
        return input_path # Если не вышло сжать, пробуем оригинал

def process_file_to_text(uploaded_file, openai_key, llama_key):
    """Определяет тип файла и извлекает текст"""
    
    text = ""
    file_ext = os.path.splitext(uploaded_file.name)[1].lower()
    
    # Создаем временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    try:
        # 1. ВИДЕО И АУДИО (Whisper)
        if file_ext in [".mp4", ".mov", ".avi", ".mp3", ".mpeg", ".m4a", ".wav"]:
            
            # --- СЖАТИЕ ФАЙЛА (FIX 25MB LIMIT) ---
            processed_path = compress_audio(tmp_path)
            
            client = OpenAIClient(api_key=openai_key)
            with open(processed_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file,
                    response_format="json"
                )
            
            # Удаляем сжатую копию, если создавали
            if processed_path != tmp_path and os.path.exists(processed_path):
                os.remove(processed_path)
            
            if hasattr(transcription, 'text'):
                text = transcription.text
            elif isinstance(transcription, dict):
                text = transcription['text']
            else:
                text = str(transcription)

        # 2. ДОКУМЕНТЫ (LlamaParse)
        else:
            parser = LlamaParse(result_type="markdown", api_key=llama_key)
            file_extractor = {".pdf": parser, ".pptx": parser, ".docx": parser, ".xlsx": parser, ".txt": parser}
            docs = SimpleDirectoryReader(input_files=[tmp_path], file_extractor=file_extractor).load_data()
            if docs:
                text = docs[0].text
            else:
                raise Exception("Не удалось прочитать документ")
                
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
    return text

def generate_quiz_ai(text, count, difficulty, lang):
    """Генерирует JSON с тестом через GPT-4o"""
    Settings.llm = OpenAI(model="gpt-4o", temperature=0.1)
    
    prompt = (
        f"You are an expert instructional designer. "
        f"1. Analyze content. 2. Create quiz in '{lang}'. "
        f"3. Questions: {count}. 4. Diff: {difficulty}. "
        "Return STRICTLY JSON format matching the Quiz schema."
    )
    
    program = LLMTextCompletionProgram.from_defaults(
        output_cls=Quiz,
        prompt_template_str=prompt + " Content: {text}",
        llm=Settings.llm
    )
    
    # Ограничиваем текст для экономии токенов
    return program(text=text[:50000])

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
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    c.setFont("Helvetica", 12)
    c.drawString(50, 50, f"Date: {date_str}")
    c.drawRightString(width-50, 50, "Authorized by Vyud AI")
    
    c.save()
    buffer.seek(0)
    return buffer
    def create_html_quiz(quiz, course_title):
    """Генерирует интерактивный HTML файл с тестом"""
    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Тест: {course_title}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; background-color: #f4f4f9; }}
            .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; text-align: center; }}
            .question {{ margin-bottom: 25px; border-bottom: 1px solid #eee; padding-bottom: 20px; }}
            .options label {{ display: block; margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; cursor: pointer; transition: 0.2s; }}
            .options label:hover {{ background-color: #f0f8ff; }}
            .btn {{ display: block; width: 100%; padding: 15px; background: #007bff; color: white; border: none; border-radius: 5px; font-size: 18px; cursor: pointer; margin-top: 20px; }}
            .btn:hover {{ background: #0056b3; }}
            .feedback {{ margin-top: 10px; padding: 10px; border-radius: 5px; display: none; }}
            .correct-answer {{ background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
            .wrong-answer {{ background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎓 {course_title}</h1>
            <form id="quizForm">
    """

    # Безопасно собираем правильные ответы для JS
    correct_indices = []
    
    for i, q in enumerate(quiz.questions):
        # Защита индекса (как в app.py)
        safe_id = q.correct_option_id
        if not q.options: continue
        if safe_id >= len(q.options) or safe_id < 0: safe_id = 0
        correct_indices.append(safe_id)

        html += f"""
        <div class="question" id="q{i}">
            <h3>{i+1}. {q.scenario}</h3>
            <div class="options">
        """
        for j, opt in enumerate(q.options):
            html += f"""
                <label>
                    <input type="radio" name="q{i}" value="{j}"> {opt}
                </label>
            """
        
        html += f"""
            </div>
            <div id="feedback-{i}" class="feedback">
                <strong>Правильный ответ:</strong> {q.options[safe_id]}<br>
                <em>{q.explanation}</em>
            </div>
        </div>
        """

    # JavaScript для проверки
    html += f"""
            <button type="button" class="btn" onclick="checkAnswers()">Проверить результаты</button>
        </form>
    </div>

    <script>
        const correctAnswers = {correct_indices};
        
        function checkAnswers() {{
            let score = 0;
            correctAnswers.forEach((correct, index) => {{
                const feedback = document.getElementById('feedback-' + index);
                const options = document.getElementsByName('q' + index);
                let selected = -1;
                
                options.forEach(opt => {{
                    if (opt.checked) selected = parseInt(opt.value);
                    opt.disabled = true; // Блокируем выбор
                }});

                feedback.style.display = 'block';
                
                if (selected === correct) {{
                    score++;
                    feedback.className = 'feedback correct-answer';
                    feedback.innerHTML = '✅ Верно! ' + feedback.innerHTML;
                }} else {{
                    feedback.className = 'feedback wrong-answer';
                    feedback.innerHTML = '❌ Ошибка. ' + feedback.innerHTML;
                }}
            }});
            
            alert(`Ваш результат: ${{score}} из ${{correctAnswers.length}}`);
        }}
    </script>
    </body>
    </html>
    """
    
    return html.encode('utf-8')
