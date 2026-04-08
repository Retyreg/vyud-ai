"""
REST API для Vyud AI Platform
Предоставляет endpoints для генерации квизов через HTTP запросы
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Header, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, List
import io
import os
from pydantic import BaseModel

import logic
import auth

# Инициализация FastAPI приложения
app = FastAPI(
    title="Vyud AI API",
    description="REST API для генерации интерактивных квизов из файлов и текста",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS настройки (разрешаем запросы с любых доменов)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Загружаем API ключи
from dotenv import load_dotenv
load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
LLAMA_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
VALID_API_KEYS = os.getenv("API_KEYS", "").split(",")

# Очищаем пустые ключи
VALID_API_KEYS = [k.strip() for k in VALID_API_KEYS if k.strip()]

# --- МОДЕЛИ ДАННЫХ ДЛЯ API ---

class QuizQuestionResponse(BaseModel):
    scenario: str
    options: List[str]
    correct_option_id: int
    explanation: str

class QuizResponse(BaseModel):
    success: bool
    questions: List[QuizQuestionResponse]
    message: Optional[str] = None

class TextQuizRequest(BaseModel):
    text: str
    count: int = 5
    difficulty: str = "Medium"
    lang: str = "Russian"
    user_email: Optional[str] = None

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None

# --- АУТЕНТИФИКАЦИЯ ---

async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """
    Проверяет API ключ из заголовка X-API-Key
    """
    if not VALID_API_KEYS or len(VALID_API_KEYS) == 0:
        # Если API ключи не настроены, выдаем предупреждение
        raise HTTPException(
            status_code=500,
            detail="API keys not configured. Please set API_KEYS in secrets.toml or environment variables"
        )

    if x_api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return x_api_key

# --- ENDPOINTS ---

@app.get("/")
async def root():
    """Базовый endpoint для проверки работы API"""
    return {
        "message": "Vyud AI API is running",
        "version": "1.0.0",
        "docs": "/api/docs",
        "endpoints": {
            "generate_quiz_file": "POST /api/generate-quiz",
            "generate_quiz_text": "POST /api/generate-quiz-text",
            "health": "GET /api/health"
        }
    }

@app.get("/api/health")
async def health_check():
    """Проверка здоровья API"""
    return {
        "status": "healthy",
        "openai_configured": bool(OPENAI_KEY),
        "llama_configured": bool(LLAMA_KEY),
        "api_keys_configured": bool(VALID_API_KEYS)
    }

@app.post("/api/generate-quiz", response_model=QuizResponse)
async def generate_quiz_from_file(
    file: UploadFile = File(..., description="Файл (PDF, DOCX, MP4, MP3, M4A)"),
    count: int = Form(5, description="Количество вопросов (3-10)"),
    difficulty: str = Form("Medium", description="Сложность: Easy, Medium, Hard"),
    lang: str = Form("Russian", description="Язык: Russian, English, Kazakh"),
    user_email: Optional[str] = Form(None, description="Email пользователя для списания кредитов"),
    api_key: str = Depends(verify_api_key)
):
    """
    Генерирует квиз из загруженного файла

    - **file**: PDF, DOCX, TXT, MP4, MP3, M4A файл
    - **count**: Количество вопросов (3-10)
    - **difficulty**: Сложность - Easy/Medium/Hard
    - **lang**: Язык квиза - Russian/English/Kazakh
    - **user_email**: Email пользователя (опционально, для списания кредитов)

    **Требования:**
    - Заголовок `X-API-Key` с валидным API ключом
    """

    # Валидация параметров
    if count < 3 or count > 10:
        raise HTTPException(status_code=400, detail="count должен быть от 3 до 10")

    if difficulty not in ["Easy", "Medium", "Hard"]:
        raise HTTPException(status_code=400, detail="difficulty должен быть Easy, Medium или Hard")

    if lang not in ["Russian", "English", "Kazakh"]:
        raise HTTPException(status_code=400, detail="lang должен быть Russian, English или Kazakh")

    # Проверка кредитов, если указан email
    if user_email:
        credits = auth.get_credits(user_email)
        if credits <= 0:
            raise HTTPException(
                status_code=402,
                detail=f"Недостаточно кредитов для пользователя {user_email}"
            )

    try:
        # Оборачиваем UploadFile в объект с методом getvalue()
    class FileWrapper:
        def __init__(self, upload_file):
            """
            Оборачивает UploadFile для совместимости с SimpleDirectoryReader.
            """
            self.name = upload_file.filename
            self._file = upload_file.file

        def getvalue(self):
            """Возвращает содержимое файла."""
            self._file.seek(0)
            return self._file.read()

    wrapped_file = FileWrapper(file)

    # 1. Извлекаем текст из файла
    text_content = logic.process_file_to_text(wrapped_file, OPENAI_KEY, LLAMA_KEY)

        if not text_content or len(text_content.strip()) < 50:
            raise HTTPException(
                status_code=400,
                detail="Не удалось извлечь достаточно текста из файла"
            )

        # 2. Генерируем квиз
        quiz_data = logic.generate_quiz_ai(text_content, count, difficulty, lang)

        # 3. Списываем кредит, если указан email
        if user_email:
            auth.deduct_credit(user_email, 1)

        # 4. Формируем ответ
        questions = [
            QuizQuestionResponse(
                scenario=q.scenario,
                options=q.options,
                correct_option_id=q.correct_option_id,
                explanation=q.explanation
            )
            for q in quiz_data.questions
        ]

        return QuizResponse(
            success=True,
            questions=questions,
            message=f"Квиз успешно сгенерирован из файла {file.filename}"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обработке файла: {str(e)}"
        )

@app.post("/api/generate-quiz-text", response_model=QuizResponse)
async def generate_quiz_from_text(
    request: TextQuizRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Генерирует квиз из текста

    - **text**: Исходный текст для создания квиза
    - **count**: Количество вопросов (3-10)
    - **difficulty**: Сложность - Easy/Medium/Hard
    - **lang**: Язык квиза - Russian/English/Kazakh
    - **user_email**: Email пользователя (опционально)

    **Требования:**
    - Заголовок `X-API-Key` с валидным API ключом
    """

    # Валидация
    if not request.text or len(request.text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="Текст должен содержать минимум 50 символов"
        )

    if request.count < 3 or request.count > 10:
        raise HTTPException(status_code=400, detail="count должен быть от 3 до 10")

    if request.difficulty not in ["Easy", "Medium", "Hard"]:
        raise HTTPException(status_code=400, detail="difficulty должен быть Easy, Medium или Hard")

    if request.lang not in ["Russian", "English", "Kazakh"]:
        raise HTTPException(status_code=400, detail="lang должен быть Russian, English или Kazakh")

    # Проверка кредитов
    if request.user_email:
        credits = auth.get_credits(request.user_email)
        if credits <= 0:
            raise HTTPException(
                status_code=402,
                detail=f"Недостаточно кредитов для пользователя {request.user_email}"
            )

    try:
        # Генерируем квиз
        quiz_data = logic.generate_quiz_ai(
            request.text,
            request.count,
            request.difficulty,
            request.lang
        )

        # Списываем кредит
        if request.user_email:
            auth.deduct_credit(request.user_email, 1)

        # Формируем ответ
        questions = [
            QuizQuestionResponse(
                scenario=q.scenario,
                options=q.options,
                correct_option_id=q.correct_option_id,
                explanation=q.explanation
            )
            for q in quiz_data.questions
        ]

        return QuizResponse(
            success=True,
            questions=questions,
            message="Квиз успешно сгенерирован из текста"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при генерации квиза: {str(e)}"
        )

# --- ЗАПУСК ---
if __name__ == "__main__":
    import uvicorn
    # Используем PORT из environment для Railway/Heroku совместимости
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
