# 🎓 CourseFlow AI

**Turn boring PDFs into interactive quizzes in seconds.**

CourseFlow is an AI-powered engine designed to automate the work of Instructional Designers. It uses advanced RAG (Retrieval-Augmented Generation) to understand complex technical documentation and generate scenario-based assessments.

## 🚀 Live Demo
Try it here: [https://lms.vyud.online/](https://lms.vyud.online/)

## 🛠 Tech Stack
- **Core:** Python 3.11
- **Orchestration:** LlamaIndex
- **Parsing:** LlamaParse (SOTA PDF parsing)
- **LLM:** OpenAI GPT-4o

## ✨ Key Features
- **Smart Parsing:** Handles tables, charts, and complex layouts via LlamaParse.
- **Scenario Generation:** Creates "Bloom's Taxonomy Level 3" questions (application), not just memorization.
- **Export Ready:** Generates a standalone `.html` file that works offline or can be uploaded to any LMS.
- **REST API:** FastAPI endpoints for external integrations.
- **Multi-format Support:** PDF, DOCX, MP4, MP3, M4A files.

## 🔧 Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/Retyreg/vyud-ai.git
cd vyud-ai
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure secrets
Copy the example file and add your API keys:
```bash
cp .env.example .env
```

Edit `.env` and add your keys:
- **OPENAI_API_KEY** - Get from [OpenAI Platform](https://platform.openai.com/api-keys)
- **LLAMA_CLOUD_API_KEY** - Get from [Llama Cloud](https://cloud.llamaindex.ai/api-key)
- **SUPABASE_URL & SUPABASE_KEY** - Get from [Supabase Dashboard](https://supabase.com/dashboard)
- **API_KEYS** - Generate with: `python -c "import secrets; print('vyud_' + secrets.token_urlsafe(32))"`

### 4. Run the application

****
```bash
```

**REST API Server:**
```bash
python api.py
# API docs: http://localhost:8000/api/docs
```

**Telegram Bot:**
```bash
python bot.py
```

## 📚 API Documentation
See [API_EXAMPLES.md](API_EXAMPLES.md) for detailed API usage examples.