# VYUD AI Platform (CourseFlow)

**Turn any document or video into an interactive, scenario-based learning experience in seconds.**

VYUD AI is an AI-powered engine designed to automate the work of Instructional Designers and HR teams. It uses advanced RAG (Retrieval-Augmented Generation) to understand complex technical documentation and generate high-quality assessments, bridging the gap between passive reading and active comprehension.

## 🚀 Key Features

*   **Smart Multi-format Parsing:** Supports PDF, DOCX, TXT, MP4, MP3, and M4A. Handles tables, charts, and complex layouts effortlessly.
*   **Scenario-Based Assessment:** Generates application-level questions (Bloom's Taxonomy Level 3+), not just simple recall.
*   **Enterprise Security:** Built with strict data isolation for corporate knowledge.
*   **Ready-to-use API:** FastAPI-based backend for easy integration into existing LMS or custom workflows.
*   **Telegram Integration:** AI-assistant bot for on-the-go quiz generation from voice notes or documents.

## 🛠 Tech Stack

| Layer | Technology |
|-------|------------|
| **Core** | Python 3.11 |
| **AI Orchestration** | LlamaIndex, LiteLLM |
| **LLM Engine** | OpenAI GPT-4o, Anthropic, Google Gemini |
| **Backend API** | FastAPI |
| **Parsing** | LlamaParse |
| **Database/Auth** | Supabase (PostgreSQL) |

## 🏗️ Quick Start

### 1. Setup Environment
```bash
# Clone the repository
git clone https://github.com/Retyreg/vyud-ai.git
cd vyud-ai

# Create .env from example and add your keys
cp .env.example .env
# Set: OPENAI_API_KEY, LLAMA_CLOUD_API_KEY, SUPABASE_URL, SUPABASE_KEY
```

### 2. Run Locally

**REST API Server:**
```bash
python api.py
# API docs available at: http://localhost:8000/api/docs
```

**Telegram AI Bot:**
```bash
python bot.py
```

## 📚 API Integration
VYUD AI provides a clean REST API for external integrations. See `API_EXAMPLES.md` for details on how to generate quizzes programmatically for your users.

---
Built with ❤️ by [VYUD AI](https://vyud.tech)
