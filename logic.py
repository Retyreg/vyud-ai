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
    """
    try:
        file_size = os.path.getsize(input_path) / (1024 * 1024) # Размер в МБ
        output_path = input_path + "_compressed.mp3"
        
        # Если это видео, достаем звук
        if input_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
            video = VideoFileClip(input_path)
            # Извлекаем аудио, глушим вывод логов (logger=None)
            video.audio.write_audiofile(output_path, bitrate="32k", logger=None)
            video.close()
            return output_path
            
        # Если это аудио, но тяжелое (>24MB)
        elif file_size > 24:
            audio = AudioSegment.from_file(input_path)
            audio.export(output_path, format="mp3", bitrate="32k")
            return output_path
            
        else:
            return input_path # Возвращаем как есть
            
    except Exception as e:
        print(f"Warning: Audio compression failed: {e}")
        return input_path

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
            
            # Сжимаем/конвертируем перед отправкой
            processed_path = compress_audio(tmp_path)
            
            client = OpenAIClient(api_key=openai_key)
            with open(processed_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file,
                    response_format="json"
                )
            
            # Удаляем сжатую копию
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
    """Генерирует JSON с тестом через GPT-4o (PRO Промпт)"""
    Settings.llm = OpenAI(model="gpt-4o", temperature=0.2) # Чуть повысим креативность для сценариев
    
    # Продвинутый промпт для корпоративного обучения
    system_prompt = (
        f"Role: You are a Senior Instructional Designer for a Fortune 500 company. "
        f"Task: Create a high-quality assessment quiz based on the provided text. "
        f"Target Audience: Corporate employees. "
        f"Language: All questions, options, and explanations must be in '{lang}'.\n\n"
        
        f"Configuration:\n"
        f"- Number of questions: {count}\n"
        f"- Difficulty Level: {difficulty}\n\n"
        
        f"Difficulty Guidelines:\n"
        f"- If 'Easy': Focus on recalling facts, definitions, and key terms from the text.\n"
        f"- If 'Medium': Focus on understanding and applying concepts. Use simple 'What would you do?' scenarios.\n"
        f"- If 'Hard': Focus on analysis and evaluation. Use COMPLEX SCENARIOS/CASE STUDIES where the user must diagnose a problem or choose the BEST solution among several good ones.\n\n"
        
        f"Rules for Quality:\n"
        f"1. NO 'all of the above' or 'none of the above' options.\n"
        f"2. Distractors (wrong answers) must be PLAUSIBLE common misconceptions, not obvious jokes.\n"
        f"3. The 'scenario' field should be the question text. For Hard/Medium, make it a mini-story.\n"
        f"4. The 'explanation' must explain WHY the correct answer is right AND why the distraction was wrong. It should be educational.\n"
        f"5. Strictly follow the JSON schema provided."
    )
    
    program = LLMTextCompletionProgram.from_defaults(
        output_cls=Quiz,
        prompt_template_str=system_prompt + "\n\nContent to analyze:\n{text}",
        llm=Settings.llm
    )
    
    # Ограничиваем текст (видео бывает длинным, берем самое важное)
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
    # Собираем индексы правильных ответов
    correct_indices = []
    for q in quiz.questions:
        safe_id = q.correct_option_id
        if not q.options: 
            correct_indices.append(0)
            continue
        if safe_id >= len(q.options) or safe_id < 0: safe_id = 0
        correct_indices.append(safe_id)

    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Тест: {course_title}</title>
        <style>
            body {{ font-family: sans-serif; max-width: 800px; margin: 20px auto; padding: 20px; background: #f4f4f9; }}
            .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            h1 {{ text-align: center; color: #333; }}
            .question {{ margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 20px; }}
            .options label {{ display: block; margin: 5px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; cursor: pointer; }}
            .options label:hover {{ background: #f0f8ff; }}
            .btn {{ display: block; width: 100%; padding: 15px; background: #28a745; color: white; border: none; border-radius: 5px; font-size: 18px; cursor: pointer; margin-top: 20px; }}
            .btn:hover {{ background: #218838; }}
            .feedback {{ margin-top: 10px; padding: 10px; border-radius: 5px; display: none; }}
            .correct {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
            .wrong {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎓 {course_title}</h1>
            <form id="quizForm">
    """
    
    for i, q in enumerate(quiz.questions):
        html += f"""
        <div class="question" id="q{i}">
            <h3>{i+1}. {q.scenario}</h3>
            <div class="options">
        """
        for j, opt in enumerate(q.options):
            html += f"""<label><input type="radio" name="q{i}" value="{j}"> {opt}</label>"""
        
        html += f"""
            </div>
            <div id="feedback-{i}" class="feedback">
                <strong>Правильный ответ:</strong> {q.options[correct_indices[i]]}<br>
                <em>{q.explanation}</em>
            </div>
        </div>
        """

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
                    opt.disabled = true;
                }});
                feedback.style.display = 'block';
                if (selected === correct) {{
                    score++;
                    feedback.className = 'feedback correct';
                    feedback.innerHTML = '✅ Верно! ' + feedback.innerHTML;
                }} else {{
                    feedback.className = 'feedback wrong';
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

    def generate_marketing_post(topic, platform, tone, extra_context=""):
    """Генерирует маркетинговый пост для Vyud AI"""
    Settings.llm = OpenAI(model="gpt-4o", temperature=0.7) # Креативность повыше
    
    # Промпт знает о продукте ВСЁ
    product_info = (
        "Product: Vyud AI.\n"
        "What it does: Instantly converts PDF documents, Video (mp4/mov), and Audio into interactive quizzes with certificates.\n"
        "Target Audience: HR Directors, L&D Managers, Business Trainers, Online Schools.\n"
        "Key Benefits: Saves hours of manual work, creates situational scenarios (Bloom's taxonomy), generates HTML & PDF certificates.\n"
        "Tone: Friendly, professional, expert."
    )
    
    system_prompt = (
        f"You are a Senior SMM Manager for an EdTech SaaS. \n"
        f"{product_info}\n\n"
        f"Task: Write a social media post.\n"
        f"Platform: {platform} (Adjust style: emojis/structure accordingly).\n"
        f"Tone: {Tone}.\n"
        f"Topic/Hook: {topic}\n"
        f"Context/Details: {extra_context}\n\n"
        f"Rules:\n"
        f"1. Catchy headline.\n"
        f"2. Focus on value and pain points.\n"
        f"3. Call to action at the end (Link: https://vyud.tech).\n"
        f"4. Language: RUSSIAN.\n"
        f"5. Short paragraphs."
    )
    
    program = LLMTextCompletionProgram.from_defaults(
        output_cls=Quiz, # Используем тот же класс просто для текстового вывода, или проще вызвать напрямую
        prompt_template_str=system_prompt, # Здесь мы упростим вызов
        llm=Settings.llm
    )
    
    # Для простоты текста вызовем чат напрямую, без Pydantic, чтобы получить просто текст
    response = Settings.llm.complete(system_prompt)
    return response.text