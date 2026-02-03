from supabase import create_client
import streamlit as st
import hashlib
import sqlite3
import os

# Import the new Database class with retry logic
try:
    from utils.db import Database, supabase as db_supabase
    USE_RETRY_DB = True
except ImportError:
    USE_RETRY_DB = False
    db_supabase = None

DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users_credits 
                 (email TEXT PRIMARY KEY, password TEXT, credits INTEGER)""")
    conn.commit()
    conn.close()

def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_user(email, password):
    init_db()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM users_credits WHERE email=? AND password=?", (email, hash_pass(password)))
    res = c.fetchone()
    conn.close()
    return res is not None

def register_user(email, password):
    init_db()
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO users_credits VALUES (?, ?, ?)", (email, hash_pass(password), 5))
        conn.commit()
        conn.close()
        try:
            supabase = get_supabase()
            if supabase:
                supabase.table("users_credits").insert({"email": email, "credits": 5}).execute()
        except:
            pass
        return True
    except:
        return False

def get_supabase():
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
    except:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)

# ==================== ФУНКЦИИ ДЛЯ КВИЗОВ ====================

def save_quiz(user_email, title, questions, hints=""):
    """Сохраняет тест в БД"""
    # Use retry-enabled database if available
    if USE_RETRY_DB:
        try:
            return Database.save_quiz(user_email, title, questions, hints)
        except Exception as e:
            print(f"Error saving quiz with retry DB: {e}")
    
    # Fallback to original implementation
    try:
        import uuid
        import json
        from datetime import datetime
        
        test_id = str(uuid.uuid4())[:8]
        
        supabase_client = get_supabase()
        if supabase_client:
            data = {
                "id": test_id,
                "owner_email": user_email,
                "title": title,
                "questions": json.dumps(questions) if isinstance(questions, list) else questions,
                "hints": hints or "",
                "created_at": datetime.utcnow().isoformat(),
                "is_public": False
            }
            supabase_client.table("quizzes").insert(data).execute()
            return test_id
        return f"local_{int(datetime.now().timestamp())}"
    except Exception as e:
        print(f"Error saving quiz: {e}")
        return f"error_{int(datetime.now().timestamp())}"

def get_user_quizzes(user_email, limit=50):
    """Получает все тесты пользователя"""
    # Use retry-enabled database if available
    if USE_RETRY_DB:
        try:
            return Database.get_user_quizzes(user_email, limit)
        except Exception as e:
            print(f"Error getting quizzes with retry DB: {e}")
    
    # Fallback to original implementation
    try:
        supabase_client = get_supabase()
        if supabase_client:
            result = supabase_client.table("quizzes")\
                .select("*")\
                .eq("owner_email", user_email)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            return result.data if result.data else []
        return []
    except Exception as e:
        print(f"Error getting quizzes: {e}")
        return []

def get_quiz_by_id(quiz_id):
    """Получает тест по ID"""
    # Use retry-enabled database if available
    if USE_RETRY_DB:
        try:
            return Database.get_quiz_by_id(quiz_id)
        except Exception as e:
            print(f"Error getting quiz with retry DB: {e}")
    
    # Fallback to original implementation
    try:
        import json
        supabase_client = get_supabase()
        if supabase_client:
            result = supabase_client.table("quizzes")\
                .select("*")\
                .eq("id", quiz_id)\
                .single()\
                .execute()
            
            if result.data and result.data.get("questions"):
                if isinstance(result.data["questions"], str):
                    result.data["questions"] = json.loads(result.data["questions"])
            
            return result.data if result.data else None
        return None
    except Exception as e:
        print(f"Error getting quiz: {e}")
        return None

def get_public_test(slug):
    """Получает публичный тест по slug"""
    # Use retry-enabled database if available
    if USE_RETRY_DB:
        try:
            return Database.get_public_test(slug)
        except Exception as e:
            print(f"Error getting public test with retry DB: {e}")
    
    # Fallback to original implementation
    try:
        import json
        supabase_client = get_supabase()
        if supabase_client:
            result = supabase_client.table("quizzes")\
                .select("*")\
                .eq("id", slug)\
                .eq("is_public", True)\
                .single()\
                .execute()
            
            if result.data and result.data.get("questions"):
                if isinstance(result.data["questions"], str):
                    result.data["questions"] = json.loads(result.data["questions"])
            
            return result.data if result.data else None
        return None
    except Exception as e:
        print(f"Error getting public test: {e}")
        return None

def get_user_credits(email):
    # Use retry-enabled database if available
    if USE_RETRY_DB:
        try:
            return Database.get_user_credits(email)
        except Exception as e:
            print(f"Error getting credits with retry DB: {e}")
    
    # Fallback to Supabase without retry
    try:
        supabase = get_supabase()
        if supabase:
            result = supabase.table("users_credits").select("credits").eq("email", email).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]["credits"]
    except:
        pass
    
    # Fallback to SQLite
    try:
        init_db()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT credits FROM users_credits WHERE email=?", (email,))
        res = c.fetchone()
        conn.close()
        return res[0] if res else 0
    except:
        return 0

def deduct_credit(email, amount=1):
    # Use retry-enabled database if available
    if USE_RETRY_DB:
        try:
            return Database.deduct_credit(email, amount)
        except Exception as e:
            print(f"Error deducting credits with retry DB: {e}")
    
    # Fallback to Supabase without retry
    try:
        supabase = get_supabase()
        if supabase:
            current = get_user_credits(email)
            if current >= amount:
                supabase.table("users_credits").update({"credits": current - amount}).eq("email", email).execute()
                return True
    except:
        pass
    
    # Fallback to SQLite
    try:
        init_db()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE users_credits SET credits = credits - ? WHERE email=?", (amount, email))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def add_credits(email, amount):
    # Use retry-enabled database if available
    if USE_RETRY_DB:
        try:
            return Database.add_credits(email, amount)
        except Exception as e:
            print(f"Error adding credits with retry DB: {e}")
    
    # Fallback to Supabase without retry
    try:
        supabase = get_supabase()
        if supabase:
            result = supabase.table("users_credits").select("credits").eq("email", email).execute()
            if result.data and len(result.data) > 0:
                new_balance = result.data[0]["credits"] + amount
                supabase.table("users_credits").update({"credits": new_balance}).eq("email", email).execute()
            else:
                supabase.table("users_credits").insert({"email": email, "credits": amount}).execute()
        return True
    except:
        return False

class MockSupabaseClient:
    def table(self, name): return self
    def select(self, *args): return self
    def eq(self, col, val): return self
    def update(self, data): return self
    def execute(self): return type('obj', (object,), {'data': []})()

supabase = get_supabase() if os.environ.get("SUPABASE_URL") else MockSupabaseClient()
