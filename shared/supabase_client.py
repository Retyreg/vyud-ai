"""
Единый Supabase клиент (service_role) для бота и API.
Используется только на сервере — никогда не передаётся в браузер.
"""
from supabase import create_client, Client
from shared.config import SUPABASE_URL, SUPABASE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ---------------------------------------------------------------------------
# Пользователи / кредиты
# ---------------------------------------------------------------------------

def get_or_create_user(telegram_id: int, username: str | None = None) -> dict:
    """
    Возвращает запись пользователя из users_credits.
    Если записи нет — создаёт её с приветственным бонусом (5 кредитов).
    """
    resp = (
        supabase.table("users_credits")
        .select("*")
        .eq("telegram_id", telegram_id)
        .maybe_single()
        .execute()
    )
    if resp.data:
        # Обновляем username если изменился
        if username and resp.data.get("username") != username:
            supabase.table("users_credits").update({"username": username}).eq("telegram_id", telegram_id).execute()
            resp.data["username"] = username
        return resp.data

    # Создаём нового пользователя
    new_user = {
        "telegram_id": telegram_id,
        "username": username,
        "credits": 5,
        "current_streak": 0,
        "total_generations": 0,
    }
    insert = supabase.table("users_credits").insert(new_user).execute()
    return insert.data[0]


def get_credits(telegram_id: int) -> int:
    resp = (
        supabase.table("users_credits")
        .select("credits")
        .eq("telegram_id", telegram_id)
        .maybe_single()
        .execute()
    )
    return resp.data["credits"] if resp.data else 0


def deduct_credit(telegram_id: int, amount: int = 1) -> bool:
    """Списывает кредиты. Возвращает True при успехе."""
    current = get_credits(telegram_id)
    if current < amount:
        return False
    supabase.table("users_credits").update(
        {"credits": current - amount}
    ).eq("telegram_id", telegram_id).execute()
    return True


def add_credits(telegram_id: int, amount: int) -> int:
    """Зачисляет кредиты. Возвращает новый баланс."""
    current = get_credits(telegram_id)
    new_balance = current + amount
    supabase.table("users_credits").update(
        {"credits": new_balance}
    ).eq("telegram_id", telegram_id).execute()
    return new_balance


def increment_generations(telegram_id: int) -> None:
    """Увеличивает счётчик генераций и обновляет стрик."""
    from datetime import date, timedelta

    resp = (
        supabase.table("users_credits")
        .select("total_generations, current_streak, last_active")
        .eq("telegram_id", telegram_id)
        .maybe_single()
        .execute()
    )
    if not resp.data:
        return

    data = resp.data
    today = date.today()
    last_active = data.get("last_active")

    # Логика стрика
    new_streak = data.get("current_streak", 0)
    if last_active:
        last_date = date.fromisoformat(str(last_active)[:10])
        if last_date == today - timedelta(days=1):
            new_streak += 1
        elif last_date < today - timedelta(days=1):
            new_streak = 1
        # last_date == today → стрик не меняем
    else:
        new_streak = 1

    # Бонус каждые 5 дней стрика
    bonus = 0
    if new_streak > 0 and new_streak % 5 == 0:
        bonus = 1

    update_payload: dict = {
        "total_generations": data.get("total_generations", 0) + 1,
        "current_streak": new_streak,
        "last_active": today.isoformat(),
    }
    supabase.table("users_credits").update(update_payload).eq("telegram_id", telegram_id).execute()

    if bonus:
        add_credits(telegram_id, bonus)


# ---------------------------------------------------------------------------
# Прогресс
# ---------------------------------------------------------------------------

def save_progress(telegram_id: int, quiz_id: str, score: int, total: int,
                  mastery_pct: int, wrong_question_ids: list[int]) -> None:
    supabase.table("user_progress").insert({
        "telegram_id": telegram_id,
        "quiz_id": quiz_id,
        "score": score,
        "total": total,
        "mastery_pct": mastery_pct,
        "wrong_question_ids": wrong_question_ids,
    }).execute()
