import asyncio
import logging
import os
import json
from fastapi import FastAPI, Header, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Импортируем вашу существующую логику
from logic import generate_quiz_ai as generate_quiz_struct
from auth import get_user_credits, deduct_credit, save_quiz, get_supabase

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="VYUD AI API for Mini App")

# Настройка CORS (разрешаем запросы от ваших доменов)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://vyud-tma.vercel.app", 
        "https://tma.vyud.online",
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ваш API ключ для безопасности
API_SECRET_KEY = "vyud_api_key_vNbMtkZxhwmNeeZkALxCzb-Xy6JbJiMnxSY4jk2_aWY"

class GenerationRequest(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    text: str
    num_questions: int = 5
    difficulty: str = "medium"
    language: str = "ru"

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

@app.post("/api/generate")
async def generate_test(request: GenerationRequest, x_api_key: str = Header(None)):
    # 1. Проверка API ключа
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    # 2. Формируем email (как в боте)
    user_email = f"{request.username or f'user{request.telegram_id}'}@telegram.io"

    # 3. Проверка баланса
    credits = await asyncio.to_thread(get_user_credits, user_email)
    if credits < 1:
        raise HTTPException(status_code=402, detail="Not enough credits")

    try:
        # 4. Запускаем генерацию
        lang_full = "Russian" if request.language == "ru" else "English"
        
        logger.info(f"Starting generation for user {request.telegram_id}")
        
        quiz_data = await asyncio.to_thread(
            generate_quiz_struct, request.text, request.num_questions, request.difficulty, lang_full
        )
        
        if not quiz_data:
            raise HTTPException(status_code=500, detail="AI failed to generate quiz")

        # 5. Преобразуем в JSON (логика из build_questions_json в bot.py)
        questions_json = []
        for q in quiz_data.questions:
            q_type = getattr(q, 'question_type', 'single_choice')
            q_dict = {
                "scenario": q.scenario,
                "options": q.options,
                "correct_option_id": q.correct_option_id,
                "explanation": q.explanation,
                "question_type": q_type,
                "correct_option_ids": getattr(q, 'correct_option_ids', [q.correct_option_id])
            }
            questions_json.append(q_dict)

        # 6. Сохраняем в базу
        title = request.text[:30] + "..." if len(request.text) > 30 else request.text
        test_id = await asyncio.to_thread(
            save_quiz, user_email, title, questions_json, getattr(quiz_data, "hints", [])
        )

        # 7. Списываем кредит
        await asyncio.to_thread(deduct_credit, user_email, 1)
        
        # 8. Логируем генерацию в Supabase (опционально)
        supabase = get_supabase()
        if supabase:
            try:
                supabase.table("generation_logs").insert({
                    "telegram_id": request.telegram_id,
                    "email": user_email,
                    "generation_type": "mini_app"
                }).execute()
                
                # Обновляем профиль (total_generations)
                res = supabase.table("users_credits").select("total_generations").eq("telegram_id", request.telegram_id).execute()
                if res.data:
                    total = res.data[0].get("total_generations", 0) + 1
                    supabase.table("users_credits").update({"total_generations": total, "last_seen": datetime.utcnow().isoformat()}).eq("telegram_id", request.telegram_id).execute()
            except Exception as e:
                logger.warning(f"Logging failed: {e}")

        return {
            "success": True,
            "test_id": test_id,
            "title": title,
            "num_questions": len(questions_json)
        }

    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
