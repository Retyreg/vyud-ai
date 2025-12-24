import os
import tempfile
import io
import logging
from datetime import datetime

# Библиотеки AI
from openai import OpenAI as OpenAIClient
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader, Settings, Document
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

# --- МОДЕЛИ ДАННЫХ (Pydantic) ---
class QuizQuestion(BaseModel):
    scenario: str = Field(..., description="Question text or scenario")
    options: List[str] = Field(..., description="List of options")
    correct_option_id: int = Field(..., description="Index of correct option (0-3)")
    explanation: str = Field(..., description="Educational explanation")

class Quiz(BaseModel):
    questions: List[QuizQuestion]

# --- ФУНКЦИИ ОБРАБОТКИ ---

def compress_audio(input_path):
    """
    Превращает видео/аудио в MP3 и сжимает, если файл > 25MB.
    """
    try:
        if not os.path.exists(input_path):
            return input_path
            
        file_size = os.path.getsize(input_path) / (1024 * 1024) # Размер в МБ
        output_path = input_path + "_compressed.mp3"
        
        # Если это видео, достаем звук
        if input_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
            try:
                video = VideoFileClip(input_path)
                # Извлекаем аудио, глушим вывод логов
                video.audio.write_audiofile(output_path, bitrate="32k", logger=None)
                video.close()
                return output_path
            except Exception as e:
                logging.error(f"Video compression error: {e}")
                return input_path # Возвращаем оригинал, если не вышло
            
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
    """
    Универсальная функция.
    Принимает либо объект файла (Streamlit), либо путь к файлу (Telegram Bot).
    """
    text = ""
    tmp_path = ""
    is_temp = False

    try:
        # ЛОГИКА ОПРЕДЕЛЕНИЯ ИСТОЧНИКА
        if isinstance(uploaded_file, str):
            # Это путь к файлу (от Telegram Бота)
            file_ext = os.path.splitext(uploaded_file)[1].lower()
            tmp_path = uploaded_file
            is_temp = False # Мы не удаляем файл здесь, это сделает бот
        else:
            # Это объект файла (от Streamlit)
            file_ext = os.path.splitext(uploaded_file.name)[1].lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            is_temp = True # Мы создали этот файл, надо удалить

        # --- ОБРАБОТКА (WHISPER или LLAMAPARSE) ---
        
        # 1. ВИДЕО И АУДИО (Whisper)
        if file_ext in [".mp4", ".mov", ".avi", ".mp3", ".mpeg", ".m4a", ".wav", ".ogg"]:
            
            # Сжимаем/конвертируем перед отправкой
            processed_path = compress_audio(tmp_path)
            
            client = OpenAIClient(api_key=openai_key)
            with open(processed_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file,
                    response_format="json"
                )
            
            # Если создавали сжатую копию - удаляем
            if processed_path != tmp_path and "_compressed" in processed_path and os.path.exists(processed_path):
                os.remove(processed_path)
            
            if hasattr(transcription, 'text'):
                text = transcription.text
            elif isinstance(transcription, dict):
                text = transcription.get('text', '')
            else:
                text = str(transcription)

        # 2. ДОКУМЕНТЫ (LlamaParse)
        else:
            parser = LlamaParse(result_type="markdown", api_key=llama_key)
            file_extractor = {".pdf": parser, ".pptx": parser, ".docx": parser, ".xlsx": parser, ".txt": parser}
            
            docs = SimpleDirectoryReader(input_files=[tmp_path], file_extractor=file_extractor).load_data()
            if docs:
                text = "\n\n".join([doc.text for doc in docs])
            else:
                raise Exception("Не удалось прочитать документ")
                
    except Exception as e:
        logging.error(f"Error processing file: {e}")
        return f"Error: {str(e)}"
        
    finally:
        # Удаляем временный файл ТОЛЬКО если мы его создали (Streamlit случай)
        if is_temp and os.path.exists(tmp_path):
            os.remove(tmp_path)
            
    return text

def generate_quiz_ai(text, count=5, difficulty="Medium", lang="Russian"):
    """Генерирует JSON с тестом через GPT-4o (PRO Промпт)"""
    # Если текст слишком короткий или содержит ошибку
    if not text or "Error:" in text or len(text) < 50:
        return Quiz(questions=[])

    Settings.llm = OpenAI(model="gpt-4o", temperature=0.2)
    
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
    
    # Обрезаем текст, чтобы не вылететь за лимиты токенов
    return program(text=text[:50000])

# Функция-обертка для БОТА (возвращает строку, а не объект Pydantic)
def generate_quiz_from_text(text):
    """
    Адаптер для Telegram-бота. 
    Бот ждет строку, а generate_quiz_ai возвращает объект Quiz.
    """
    try:
        quiz_obj = generate_quiz_ai(text, count=3, difficulty="Medium", lang="Russian")
        
        if not quiz_obj or not quiz_obj.questions:
            return "Не удалось сгенерировать тест. Текст слишком короткий или неинформативный."

        # Форматируем объект Quiz в красивый текст для Телеграма
        output = ""
        for i, q in enumerate(quiz_obj.questions, 1):
            output += f"<b>{i}. {q.scenario}</b>\n"
            for j, opt in enumerate(q.options):
                # Добавляем буквы (A, B, C...)
                letter = chr(65 + j)
                output += f"({letter}) {opt}\n"
            output += f"<i>Правильный: ({chr(65 + q.correct_option_id)})</i>\n"
            output += f"💡 <i>{q.explanation}</i>\n\n"
            
        return output
    except Exception as e:
        return f"Ошибка генерации: {e}"

# Функция-обертка для БОТА (transcribe_audio -> process_file_to_text)
def transcribe_audio(file_path):
    """Адаптер имени функции для бота, чтобы не переписывать bot.py"""
    openai_key = os.environ.get("OPENAI_API_KEY")
    # Ключ LlamaCloud нам для аудио не нужен, но функция требует аргумент
    return process_file_to_text(file_path, openai_key, None)

def create_certificate(student_name, course_name, logo_file=None):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)
    
    c.setStrokeColorRGB(0.2, 0.2, 0.2)
    c.setLineWidth(5)
    c.rect(30, 30, width-60, height-60)
    
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(width/2, height-100, "CERTIFICATE OF COMPLETION")
    
    c.setFont("Helvetica", 20)
    c.drawCentredString(width/2, height-160, "This is to certify that")
    
    c.setFont("Helvetica-Bold", 40)
    c.drawCentredString(width/2, height-220, student_name)
    
    c.setFont("Helvetica", 20)
    c.drawCentredString(width/2, height-280, "Has successfully completed the course")
    
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(width/2, height-340, course_name)
    
    c.setFont("Helvetica", 15)
    c.drawCentredString(width/2, height-450, f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    
    if logo_file:
        try:
            logo_file.seek(0)
            logo = ImageReader(logo_file)
            c.drawImage(logo, 50, height-150, width=100, preserveAspectRatio=True, mask='auto')
        except Exception as e:
            print(f"Logo error: {e}")
            
    c.save()
    buffer.seek(0)
    return buffer