# 🎓 VYUD AI

**Turn boring PDFs into interactive quizzes in seconds.**

VYUD AI is an AI-powered engine that automates the work of Instructional Designers. It uses advanced RAG (Retrieval-Augmented Generation) to understand complex technical documentation and generate scenario-based assessments.

## 🚀 Live Demo

Try it here: [https://app.vyud.online/](https://app.vyud.online/)

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11 |
| Orchestration | LlamaIndex |
| PDF Parsing | LlamaParse (SOTA PDF parsing) |
| LLM | OpenAI GPT-4o |
| Transcription | OpenAI Whisper |
| UI | Streamlit |
| Database | Supabase (PostgreSQL) + SQLite (local fallback) |
| Payments | Telegram Stars / Prodamus |
| Deployment | Streamlit Community Cloud + Linux VPS |

---

## ✨ Key Features

- **Smart Parsing** — handles tables, charts, and complex layouts via LlamaParse.
- **Scenario Generation** — creates Bloom's Taxonomy Level 3 questions (application-level), not just recall.
- **Multiple Input Formats** — PDF, DOCX, PPTX, XLSX, CSV, MP3, MP4, and more.
- **Certificate Generation** — produces branded PDF certificates in English and Russian.
- **SCORM 1.2 Export** — export quizzes as SCORM packages for any LMS.
- **Telegram Bot** — full-featured bot with quiz delivery, credit system, and Telegram Stars payments.
- **Export Ready** — generates a standalone `.html` file that works offline or can be uploaded to any LMS.

---

## 📁 Project Structure

```
vyud-ai/
├── app.py                  # Streamlit web application (main entry point)
├── logic.py                # Quiz generation, AI logic, certificate rendering
├── auth.py                 # Authentication and credit management (SQLite + Supabase)
├── bot.py                  # Telegram bot (aiogram 3.x)
├── scorm_export.py         # SCORM 1.2 package export
├── admin_stats.py          # Admin analytics panel (port 8503)
├── webhook_prodamus.py     # Prodamus payment webhook handler
├── test_bot.py             # Tests for critical bot functionality
├── safe_deploy.sh          # Safe deployment script (runs tests before deploy)
├── payments_log_schema.sql # Supabase SQL schema for payment logs
├── requirements.txt        # Python dependencies
├── style.css               # Custom CSS styles
├── assets/
│   └── DejaVuSans.ttf      # Font for Cyrillic PDF certificate rendering
└── .streamlit/
    └── config.toml         # Streamlit theme and server configuration
```

---

## ⚙️ Configuration

All secrets are stored in `.streamlit/secrets.toml` (not committed to Git):

```toml
OPENAI_API_KEY = "sk-..."
LLAMA_CLOUD_API_KEY = "llx-..."
SUPABASE_URL = "https://..."
SUPABASE_KEY = "eyJ..."
BOT_TOKEN = "..."
ADMIN_CHAT_ID = "..."
```

---

## 🚀 Running Locally

```bash
# Clone the repository
git clone https://github.com/Retyreg/vyud-ai.git
cd vyud-ai

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure secrets
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets.toml with your API keys

# Run the web app
streamlit run app.py

# Run the Telegram bot (separate terminal)
python3 bot.py
```

---

## 🧪 Testing

```bash
cd /var/www/vyud_app
source venv/bin/activate
python3 -m pytest test_bot.py -v
```

Tests cover:
- `QuizQuestion` data model integrity
- Sync/async correctness of `auth.py` functions
- Proper usage of `q.scenario` (not `q.question`) in `bot.py`
- Telegram poll sending logic
- Credit deduction via `asyncio.to_thread`

---

## 🌐 Deployment

The project runs on a Linux VPS. Use the provided deploy script for safe zero-downtime deploys:

```bash
# Safe deploy (runs tests, commits, restarts bot)
./safe_deploy.sh "Your commit message"
```

The script:
1. Creates a temporary bot backup in `/tmp/`
2. Runs the test suite — aborts if any test fails
3. Commits and pushes changes to Git
4. Restarts the Telegram bot process

---

## 💳 Credit System

Users receive **5 free credits** on registration. Additional credits can be purchased via:
- **Telegram Stars** (in-bot payments)
- **Prodamus** (web checkout)

| Package | Price |
|---------|-------|
| 10 credits | 50 ⭐ (~$1) |
| 50 credits | 200 ⭐ (~$4) |
| 100 credits | 350 ⭐ (~$7) |
| Monthly subscription | 300 ⭐ (~$6) — 100 credits |
| Annual subscription | 3000 ⭐ (~$60) — 1200 credits |

---

## 🗃 Database

### Supabase tables

| Table | Purpose |
|-------|---------|
| `users_credits` | User accounts, credit balance, subscription status |
| `quizzes` | Saved quizzes (JSONB questions) |
| `payments_log` | Full payment transaction history |

See `payments_log_schema.sql` for the complete Supabase schema.

---

## 📄 License

Proprietary. All rights reserved.

