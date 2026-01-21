"""
Модуль для работы с тестами и статистикой в Supabase
"""
import streamlit as st
import os
import json
from datetime import datetime

def get_supabase():
    """Получить клиент Supabase"""
    from supabase import create_client
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
    except:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


# ==================== ТЕСТЫ ====================

def save_test(owner_email: str, title: str, questions: list, 
              source_filename: str = None, difficulty: str = None, language: str = None) -> str:
    """
    Сохранить новый тест в БД
    
    Args:
        owner_email: email создателя
        title: название теста
        questions: список вопросов в формате [{"scenario": ..., "options": [...], "correct_option_id": int, "explanation": ...}]
        source_filename: имя исходного файла
        difficulty: сложность (Easy/Medium/Hard)
        language: язык теста
    
    Returns:
        test_id (UUID) или None при ошибке
    """
    supabase = get_supabase()
    if not supabase:
        return None
    
    try:
        result = supabase.table("tests").insert({
            "owner_email": owner_email,
            "title": title,
            "questions": questions,
            "source_filename": source_filename,
            "difficulty": difficulty,
            "language": language
        }).execute()
        
        if result.data:
            return result.data[0]["id"]
        return None
    except Exception as e:
        st.error(f"Ошибка сохранения теста: {e}")
        return None


def get_user_tests(email: str) -> list:
    """
    Получить все тесты пользователя
    
    Returns:
        Список тестов с полями: id, title, created_at, questions_count
    """
    supabase = get_supabase()
    if not supabase:
        return []
    
    try:
        result = supabase.table("tests")\
            .select("id, title, source_filename, difficulty, language, created_at, questions")\
            .eq("owner_email", email)\
            .order("created_at", desc=True)\
            .execute()
        
        tests = []
        for t in result.data:
            tests.append({
                "id": t["id"],
                "title": t["title"],
                "source_filename": t.get("source_filename"),
                "difficulty": t.get("difficulty"),
                "language": t.get("language"),
                "created_at": t["created_at"],
                "questions_count": len(t["questions"]) if t["questions"] else 0
            })
        return tests
    except Exception as e:
        st.error(f"Ошибка загрузки тестов: {e}")
        return []


def get_test(test_id: str) -> dict:
    """
    Получить тест по ID
    
    Returns:
        {"id": ..., "title": ..., "questions": [...], "owner_email": ..., ...} или None
    """
    supabase = get_supabase()
    if not supabase:
        return None
    
    try:
        result = supabase.table("tests")\
            .select("*")\
            .eq("id", test_id)\
            .execute()
        
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        st.error(f"Ошибка загрузки теста: {e}")
        return None


def update_test(test_id: str, questions: list = None, title: str = None) -> bool:
    """
    Обновить тест (вопросы и/или название)
    
    Returns:
        True если успешно
    """
    supabase = get_supabase()
    if not supabase:
        return False
    
    try:
        update_data = {}
        if questions is not None:
            update_data["questions"] = questions
        if title is not None:
            update_data["title"] = title
        
        if not update_data:
            return True
        
        supabase.table("tests")\
            .update(update_data)\
            .eq("id", test_id)\
            .execute()
        return True
    except Exception as e:
        st.error(f"Ошибка обновления теста: {e}")
        return False


def delete_test(test_id: str) -> bool:
    """Удалить тест (каскадно удалит и все попытки)"""
    supabase = get_supabase()
    if not supabase:
        return False
    
    try:
        supabase.table("tests").delete().eq("id", test_id).execute()
        return True
    except Exception as e:
        st.error(f"Ошибка удаления теста: {e}")
        return False


# ==================== СТАТИСТИКА ====================

def save_attempt(test_id: str, user_email: str, score: int, total_questions: int,
                 passed: bool, answers: list = None, time_spent_seconds: int = None) -> str:
    """
    Сохранить результат прохождения теста
    
    Args:
        test_id: ID теста
        user_email: email прошедшего
        score: количество правильных ответов
        total_questions: всего вопросов
        passed: сдал или нет
        answers: список ответов пользователя [{"question_id": 0, "selected": 1, "correct": True}, ...]
        time_spent_seconds: время прохождения в секундах
    
    Returns:
        attempt_id или None
    """
    supabase = get_supabase()
    if not supabase:
        return None
    
    try:
        result = supabase.table("test_attempts").insert({
            "test_id": test_id,
            "user_email": user_email,
            "score": score,
            "total_questions": total_questions,
            "passed": passed,
            "answers": answers,
            "time_spent_seconds": time_spent_seconds
        }).execute()
        
        if result.data:
            return result.data[0]["id"]
        return None
    except Exception as e:
        st.error(f"Ошибка сохранения результата: {e}")
        return None


def get_test_stats(test_id: str) -> dict:
    """
    Получить статистику по тесту
    
    Returns:
        {
            "total_attempts": int,
            "passed_count": int,
            "failed_count": int,
            "avg_score": float,
            "avg_percentage": float,
            "attempts": [...]  # последние 50 попыток
        }
    """
    supabase = get_supabase()
    if not supabase:
        return None
    
    try:
        result = supabase.table("test_attempts")\
            .select("*")\
            .eq("test_id", test_id)\
            .order("passed_at", desc=True)\
            .limit(50)\
            .execute()
        
        attempts = result.data
        if not attempts:
            return {
                "total_attempts": 0,
                "passed_count": 0,
                "failed_count": 0,
                "avg_score": 0,
                "avg_percentage": 0,
                "attempts": []
            }
        
        total = len(attempts)
        passed = sum(1 for a in attempts if a["passed"])
        avg_score = sum(a["score"] for a in attempts) / total
        avg_pct = sum(float(a["percentage"]) for a in attempts) / total
        
        return {
            "total_attempts": total,
            "passed_count": passed,
            "failed_count": total - passed,
            "avg_score": round(avg_score, 1),
            "avg_percentage": round(avg_pct, 1),
            "attempts": attempts
        }
    except Exception as e:
        st.error(f"Ошибка загрузки статистики: {e}")
        return None


def get_user_stats(email: str) -> dict:
    """
    Получить общую статистику пользователя по всем тестам
    
    Returns:
        {
            "total_attempts": int,
            "tests_passed": int,
            "tests_failed": int,
            "avg_percentage": float,
            "recent_attempts": [...]  # последние 20 попыток с названиями тестов
        }
    """
    supabase = get_supabase()
    if not supabase:
        return None
    
    try:
        # Получаем попытки пользователя
        result = supabase.table("test_attempts")\
            .select("*, tests(title)")\
            .eq("user_email", email)\
            .order("passed_at", desc=True)\
            .limit(50)\
            .execute()
        
        attempts = result.data
        if not attempts:
            return {
                "total_attempts": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "avg_percentage": 0,
                "recent_attempts": []
            }
        
        total = len(attempts)
        passed = sum(1 for a in attempts if a["passed"])
        avg_pct = sum(float(a["percentage"]) for a in attempts) / total
        
        # Форматируем для отображения
        recent = []
        for a in attempts[:20]:
            recent.append({
                "test_title": a["tests"]["title"] if a.get("tests") else "Неизвестный тест",
                "score": a["score"],
                "total": a["total_questions"],
                "percentage": float(a["percentage"]),
                "passed": a["passed"],
                "date": a["passed_at"]
            })
        
        return {
            "total_attempts": total,
            "tests_passed": passed,
            "tests_failed": total - passed,
            "avg_percentage": round(avg_pct, 1),
            "recent_attempts": recent
        }
    except Exception as e:
        st.error(f"Ошибка загрузки статистики: {e}")
        return None


# ==================== АДМИН ФУНКЦИИ ====================

def get_all_tests() -> list:
    """
    Получить ВСЕ тесты (для админа)
    
    Returns:
        Список всех тестов с информацией о владельце
    """
    supabase = get_supabase()
    if not supabase:
        return []
    
    try:
        result = supabase.table("tests")\
            .select("id, title, owner_email, source_filename, difficulty, language, created_at, questions")\
            .order("created_at", desc=True)\
            .execute()
        
        tests = []
        for t in result.data:
            tests.append({
                "id": t["id"],
                "title": t["title"],
                "owner_email": t["owner_email"],
                "source_filename": t.get("source_filename"),
                "difficulty": t.get("difficulty"),
                "language": t.get("language"),
                "created_at": t["created_at"],
                "questions_count": len(t["questions"]) if t["questions"] else 0
            })
        return tests
    except Exception as e:
        st.error(f"Ошибка загрузки тестов: {e}")
        return []


def get_all_attempts(limit: int = 100) -> list:
    """
    Получить ВСЕ попытки прохождения (для админа)
    
    Returns:
        Список всех попыток с названиями тестов
    """
    supabase = get_supabase()
    if not supabase:
        return []
    
    try:
        result = supabase.table("test_attempts")\
            .select("*, tests(title, owner_email)")\
            .order("passed_at", desc=True)\
            .limit(limit)\
            .execute()
        
        attempts = []
        for a in result.data:
            attempts.append({
                "id": a["id"],
                "test_title": a["tests"]["title"] if a.get("tests") else "Удалённый тест",
                "test_owner": a["tests"]["owner_email"] if a.get("tests") else "N/A",
                "user_email": a["user_email"],
                "score": a["score"],
                "total_questions": a["total_questions"],
                "percentage": float(a["percentage"]) if a.get("percentage") else 0,
                "passed": a["passed"],
                "passed_at": a["passed_at"],
                "time_spent_seconds": a.get("time_spent_seconds")
            })
        return attempts
    except Exception as e:
        st.error(f"Ошибка загрузки попыток: {e}")
        return []


def get_global_stats() -> dict:
    """
    Получить глобальную статистику по платформе (для админа)
    
    Returns:
        {
            "total_tests": int,
            "total_attempts": int,
            "total_users_with_tests": int,
            "avg_pass_rate": float,
            "tests_today": int,
            "attempts_today": int
        }
    """
    supabase = get_supabase()
    if not supabase:
        return None
    
    try:
        # Общее количество тестов
        tests_result = supabase.table("tests").select("id, owner_email, created_at").execute()
        tests = tests_result.data if tests_result.data else []
        
        # Общее количество попыток
        attempts_result = supabase.table("test_attempts").select("id, passed, passed_at").execute()
        attempts = attempts_result.data if attempts_result.data else []
        
        # Уникальные создатели тестов
        unique_owners = set(t["owner_email"] for t in tests)
        
        # Процент сдачи
        passed_count = sum(1 for a in attempts if a.get("passed"))
        pass_rate = (passed_count / len(attempts) * 100) if attempts else 0
        
        # Статистика за сегодня
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        tests_today = sum(1 for t in tests if t["created_at"] and t["created_at"].startswith(today))
        attempts_today = sum(1 for a in attempts if a["passed_at"] and a["passed_at"].startswith(today))
        
        return {
            "total_tests": len(tests),
            "total_attempts": len(attempts),
            "total_users_with_tests": len(unique_owners),
            "avg_pass_rate": round(pass_rate, 1),
            "tests_today": tests_today,
            "attempts_today": attempts_today
        }
    except Exception as e:
        st.error(f"Ошибка загрузки глобальной статистики: {e}")
        return None


# ==================== ШАРИНГ ТЕСТОВ ====================

def generate_slug() -> str:
    """Генерирует уникальный короткий slug для публичной ссылки"""
    import random
    import string
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))


def make_test_public(test_id: str, require_name: bool = True) -> str:
    """
    Сделать тест публичным и получить ссылку
    
    Returns:
        public_slug или None при ошибке
    """
    supabase = get_supabase()
    if not supabase:
        return None
    
    try:
        # Проверяем, есть ли уже slug
        result = supabase.table("tests").select("public_slug").eq("id", test_id).execute()
        if result.data and result.data[0].get("public_slug"):
            # Уже есть slug — просто включаем публичность
            supabase.table("tests").update({
                "is_public": True,
                "require_name": require_name
            }).eq("id", test_id).execute()
            return result.data[0]["public_slug"]
        
        # Генерируем новый slug
        slug = generate_slug()
        supabase.table("tests").update({
            "is_public": True,
            "require_name": require_name,
            "public_slug": slug
        }).eq("id", test_id).execute()
        return slug
    except Exception as e:
        st.error(f"Ошибка создания публичной ссылки: {e}")
        return None


def make_test_private(test_id: str) -> bool:
    """Сделать тест приватным (отключить публичный доступ)"""
    supabase = get_supabase()
    if not supabase:
        return False
    
    try:
        supabase.table("tests").update({"is_public": False}).eq("id", test_id).execute()
        return True
    except Exception as e:
        st.error(f"Ошибка: {e}")
        return False


def get_public_test(slug: str) -> dict:
    """
    Получить публичный тест по slug
    
    Returns:
        {"id": ..., "title": ..., "questions": [...], "require_name": bool, "owner_email": ...} или None
    """
    supabase = get_supabase()
    if not supabase:
        return None
    
    try:
        result = supabase.table("tests")\
            .select("id, title, questions, require_name, owner_email")\
            .eq("public_slug", slug)\
            .eq("is_public", True)\
            .execute()
        
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        return None


def get_test_sharing_info(test_id: str) -> dict:
    """
    Получить информацию о шаринге теста
    
    Returns:
        {"is_public": bool, "public_slug": str or None, "require_name": bool}
    """
    supabase = get_supabase()
    if not supabase:
        return None
    
    try:
        result = supabase.table("tests")\
            .select("is_public, public_slug, require_name")\
            .eq("id", test_id)\
            .execute()
        
        if result.data:
            return result.data[0]
        return None
    except:
        return None


def get_question_stats(test_id: str) -> list:
    """
    Получить статистику по каждому вопросу теста (на каких чаще ошибаются)
    
    Returns:
        [{"question_id": 0, "correct_count": 10, "wrong_count": 5, "success_rate": 66.7}, ...]
    """
    supabase = get_supabase()
    if not supabase:
        return []
    
    try:
        result = supabase.table("test_attempts")\
            .select("answers")\
            .eq("test_id", test_id)\
            .execute()
        
        if not result.data:
            return []
        
        # Агрегируем по вопросам
        question_stats = {}
        for attempt in result.data:
            if not attempt.get("answers"):
                continue
            for ans in attempt["answers"]:
                qid = ans.get("question_id", 0)
                if qid not in question_stats:
                    question_stats[qid] = {"correct": 0, "wrong": 0}
                if ans.get("correct"):
                    question_stats[qid]["correct"] += 1
                else:
                    question_stats[qid]["wrong"] += 1
        
        # Форматируем результат
        stats = []
        for qid, data in sorted(question_stats.items()):
            total = data["correct"] + data["wrong"]
            rate = (data["correct"] / total * 100) if total > 0 else 0
            stats.append({
                "question_id": qid,
                "correct_count": data["correct"],
                "wrong_count": data["wrong"],
                "success_rate": round(rate, 1)
            })
        
        return stats
    except Exception as e:
        st.error(f"Ошибка загрузки статистики вопросов: {e}")
        return []
