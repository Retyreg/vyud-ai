import asyncio
import logging
import os
import json
from fastapi import FastAPI, Header, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from aiogram import Bot

# Импортируем вашу существующую логику
from logic import generate_quiz_ai as generate_quiz_struct
from auth import get_user_credits, deduct_credit, save_quiz, get_supabase, add_credits

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализируем бота для уведомлений
TELEGRAM_BOT_TOKEN = "8335389203:AAEnlOGha8yx8yu5ds9JtH3OTHtqfjFRBOs"
bot = Bot(token=TELEGRAM_BOT_TOKEN)

app = FastAPI(title="VYUD AI API for Mini App")

# Настройка CORS
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

# Ваш API ключ
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
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    user_email = f"{request.username or f'user{request.telegram_id}'}@telegram.io"
    is_admin = (request.telegram_id == 5701645456)
    
    if not is_admin:
        credits = await asyncio.to_thread(get_user_credits, user_email)
        if credits < 1:
            raise HTTPException(status_code=402, detail="Not enough credits")

    try:
        lang_full = "Russian" if request.language == "ru" else "English"
        logger.info(f"Starting generation for user {request.telegram_id}")
        
        quiz_data = await asyncio.to_thread(
            generate_quiz_struct, request.text, request.num_questions, request.difficulty, lang_full
        )
        
        if not quiz_data:
            raise HTTPException(status_code=500, detail="AI failed to generate quiz")

        questions_json = []
        for q in quiz_data.questions:
            q_type = getattr(q, 'question_type', 'single_choice')
            questions_json.append({
                "scenario": q.scenario,
                "options": q.options,
                "correct_option_id": q.correct_option_id,
                "explanation": q.explanation,
                "question_type": q_type,
                "correct_option_ids": getattr(q, 'correct_option_ids', [q.correct_option_id])
            })

        title = request.text[:30] + "..." if len(request.text) > 30 else request.text
        test_id = await asyncio.to_thread(
            save_quiz, user_email, title, questions_json, getattr(quiz_data, "hints", [])
        )

        if not is_admin:
            await asyncio.to_thread(deduct_credit, user_email, 1)
        
        # --- ЛОГИКА ОБНОВЛЕНИЯ ПРОФИЛЯ И СТРИКОВ ---
        supabase = get_supabase()
        if supabase:
            try:
                # Получаем текущие данные
                res = supabase.table("users_credits").select("*").eq("telegram_id", request.telegram_id).execute()
                
                if res.data:
                    user_record = res.data[0]
                    current_streak = user_record.get("current_streak") or 0
                    total_gens = (user_record.get("total_generations") or 0) + 1
                    last_activity_str = user_record.get("last_activity")
                    
                    now = datetime.utcnow()
                    streak_updated = False
                    bonus_awarded = False
                    last_activity = None

                    if last_activity_str:
                        # Чистим строку даты
                        last_activity_str = last_activity_str.split('+')[0].split('.')[0]
                        last_activity = datetime.fromisoformat(last_activity_str)

                    # Расчет стрика
                    if last_activity:
                        time_diff = now - last_activity
                        if time_diff.days == 1 or (time_diff.days == 0 and now.date() > last_activity.date()):
                            current_streak += 1
                            streak_updated = True
                        elif time_diff.days > 1:
                            current_streak = 1
                            streak_updated = True
                    else:
                        current_streak = 1
                        streak_updated = True

                    if streak_updated and current_streak > 0 and current_streak % 5 == 0:
                        bonus_awarded = True

                    # Обновляем в БД
                    update_data = {
                        "total_generations": total_gens,
                        "current_streak": current_streak,
                        "last_activity": now.isoformat(),
                        "last_seen": now.isoformat()
                    }
                    supabase.table("users_credits").update(update_data).eq("telegram_id", request.telegram_id).execute()
                    
                    # Логируем
                    supabase.table("generation_logs").insert({
                        "telegram_id": request.telegram_id,
                        "email": user_email,
                        "generation_type": "mini_app"
                    }).execute()

                    # Начисляем бонус и уведомляем
                    if bonus_awarded:
                        await asyncio.to_thread(add_credits, user_email, 1)
                        try:
                            await bot.send_message(
                                request.telegram_id,
                                f"🔥 <b>Ударный режим в Mini App: {current_streak} дней!</b>\n\n"
                                f"Вы создаете тесты через приложение {current_streak} дней подряд. Вам начислен <b>1 бонусный кредит</b>! 🎁",
                                parse_mode="HTML"
                            )
                        except: pass

            except Exception as e:
                logger.warning(f"Profile/Streak update failed: {e}")

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
