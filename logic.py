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

# --- МОДЕЛИ ДАННЫХ (Pydantic) ---
class QuizQuestion(BaseModel):
    scenario: str = Field(..., description="Текст вопроса")
    options: List[str] = Field(..., description="Варианты ответов (максимум 4)")
    correct_option_id: int = Field(..., description="Индекс правильного ответа (0, 1, 2 или 3)")
    explanation: str = Field(..., description="Короткое объяснение (почему ответ верен)")

class Quiz(BaseModel):
    questions: List[QuizQuestion]

# --- ФУНКЦИИ ОБРАБОТКИ ---

def compress_audio(input_path):
    """Сжимает аудио, если нужно."""
    try:
        if not os.path.exists(input_path): return input_path
        file_size = os.path.getsize(input_path) / (1024 * 1024)
        output_path = input_path + "_compressed.mp3"
        
        if input_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
            try:
                video = VideoFileClip(input_path)
                video.audio.write_audiofile(output_path, bitrate="32k", logger=None)
                video.close()
                return output_path
            except: return input_path
        elif file_size > 24:
            audio = AudioSegment.from_file(input_path)
            audio.export(output_path, format="mp3", bitrate="32k")
            return output_path
        return input_path
    except: return input_path

def process_file_to_text(uploaded_file, openai_key, llama_key):
    """Универсальный парсер (Сайт + Бот)."""
    text = ""
    tmp_path = ""
    is_temp = False

    try:
        if isinstance(uploaded_file, str):
            tmp_path = uploaded_file # Путь от бота
        else:
            file_ext = os.path.splitext(uploaded_file.name)[1].lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            is_temp = True

        # Определяем тип (Видео/Аудио или Док)
        ext = os.path.splitext(tmp_path)[1].lower()
        if ext in [".mp4", ".mov", ".avi", ".mp3", ".mpeg", ".m4a", ".wav", ".ogg"]:
            processed_path = compress_audio(tmp_path)
            client = OpenAIClient(api_key=openai_key)
            with open(processed_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1", file=audio_file, response_format="json"
                )
            # Удаляем сжатый файл
            if processed_path != tmp_path and "_compressed" in processed_path:
                os.remove(processed_path)
            
            text = transcription.text if hasattr(transcription, 'text') else str(transcription)
        else:
            # Документы (LlamaParse)
            if not llama_key: llama_key = os.environ.get("LLAMA_CLOUD_API_KEY", "")
            parser = LlamaParse(result_type="markdown", api_key=llama_key)
            file_extractor = {".pdf": parser, ".pptx": parser, ".docx": parser, ".txt": parser}
            docs = SimpleDirectoryReader(input_files=[tmp_path], file_extractor=file_extractor).load_data()
            text = "\n\n".join([doc.text for doc in docs]) if docs else ""
            
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        if is_temp and os.path.exists(tmp_path): os.remove(tmp_path)
            
    return text

def generate_quiz_ai(text, count=3, difficulty="Medium", lang="Russian"):
    """Базовая функция генерации через Pydantic."""
    if not text or len(text) < 50: return None

    Settings.llm = OpenAI(model="gpt-4o", temperature=0.2)
    
    system_prompt = (
        f"Create a quiz based on the text. Language: {lang}. "
        f"Difficulty: {difficulty}. Questions: {count}. "
        f"IMPORTANT: 'scenario' is the question text. 'options' is a list of 2-4 strings. "
        f"'correct_option_id' is the integer index (0-based) of the correct answer. "
        f"Keep questions short (<300 chars) and options short (<100 chars) for Telegram."
    )
    
    program = LLMTextCompletionProgram.from_defaults(
        output_cls=Quiz,
        prompt_template_str=system_prompt + "\n\nText:\n{text}",
        llm=Settings.llm
    )
    
    try:
        return program(text=text[:50000])
    except Exception as e:
        logging.error(f"GPT Error: {e}")
        return None

# --- АДАПТЕРЫ ДЛЯ БОТА ---

def transcribe_audio(file_path):
    """Для бота: просто транскрибируем."""
    return process_file_to_text(file_path, os.environ.get("OPENAI_API_KEY"), None)

def generate_quiz_struct(text):
    """Для бота: возвращаем ОБЪЕКТ, а не текст."""
    return generate_quiz_ai(text, count=3, difficulty="Medium", lang="Russian")

# Заглушка для PDF (чтобы не сломать импорты сайта)
def create_certificate(name, course, logo=None): return io.BytesIO()