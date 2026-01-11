from supabase import create_client
import streamlit as st
import hashlib
import sqlite3
import os

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

def get_user_credits(email):
    try:
        supabase = get_supabase()
        if supabase:
            result = supabase.table("users_credits").select("credits").eq("email", email).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]["credits"]
    except:
        pass
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
    try:
        supabase = get_supabase()
        if supabase:
            current = get_user_credits(email)
            if current >= amount:
                supabase.table("users_credits").update({"credits": current - amount}).eq("email", email).execute()
                return True
    except:
        pass
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
