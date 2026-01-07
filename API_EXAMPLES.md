# Vyud AI REST API - Примеры использования

## Настройка

### 1. Установите зависимости
```bash
pip install -r requirements.txt
```

### 2. Настройте API ключи

Создайте файл `.streamlit/secrets.toml` или установите переменные окружения:

```toml
# .streamlit/secrets.toml
OPENAI_API_KEY = "sk-..."
LLAMA_CLOUD_API_KEY = "llx_..."

# API ключи для доступа к REST API (можно несколько через запятую)
API_KEYS = "your-secret-key-1,your-secret-key-2"
```

Или через переменные окружения:
```bash
export OPENAI_API_KEY="sk-..."
export LLAMA_CLOUD_API_KEY="llx_..."
export API_KEYS="your-secret-key-1,your-secret-key-2"
```

### 3. Запустите API сервер

```bash
python api.py
```

Или с помощью uvicorn:
```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

API будет доступен по адресу: `http://localhost:8000`

### 4. Документация

- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

---

## Примеры запросов

### 1. Проверка работы API

```bash
curl http://localhost:8000/
```

Ответ:
```json
{
  "message": "Vyud AI API is running",
  "version": "1.0.0",
  "docs": "/api/docs"
}
```

### 2. Health Check

```bash
curl http://localhost:8000/api/health
```

Ответ:
```json
{
  "status": "healthy",
  "openai_configured": true,
  "llama_configured": true,
  "api_keys_configured": true
}
```

---

## Основные endpoints

### POST /api/generate-quiz - Генерация квиза из файла

**Параметры:**
- `file` - файл (PDF, DOCX, TXT, MP4, MP3, M4A)
- `count` - количество вопросов (3-10), по умолчанию 5
- `difficulty` - сложность (Easy/Medium/Hard), по умолчанию Medium
- `lang` - язык (Russian/English/Kazakh), по умолчанию Russian
- `user_email` - email для списания кредитов (опционально)

**Заголовки:**
- `X-API-Key` - ваш API ключ (обязательно)

**Пример с curl:**

```bash
curl -X POST "http://localhost:8000/api/generate-quiz" \
  -H "X-API-Key: your-secret-key-1" \
  -F "file=@document.pdf" \
  -F "count=5" \
  -F "difficulty=Medium" \
  -F "lang=Russian" \
  -F "user_email=user@example.com"
```

**Пример с Python (requests):**

```python
import requests

url = "http://localhost:8000/api/generate-quiz"
headers = {
    "X-API-Key": "your-secret-key-1"
}

files = {
    "file": open("document.pdf", "rb")
}

data = {
    "count": 5,
    "difficulty": "Medium",
    "lang": "Russian",
    "user_email": "user@example.com"
}

response = requests.post(url, headers=headers, files=files, data=data)
print(response.json())
```

**Пример ответа:**

```json
{
  "success": true,
  "questions": [
    {
      "scenario": "Компания внедряет новую CRM систему...",
      "options": [
        "Немедленно начать обучение сотрудников",
        "Провести пилотное тестирование с небольшой группой",
        "Отложить внедрение до следующего квартала",
        "Заменить всю IT инфраструктуру"
      ],
      "correct_option_id": 1,
      "explanation": "Пилотное тестирование позволяет выявить проблемы..."
    }
  ],
  "message": "Квиз успешно сгенерирован из файла document.pdf"
}
```

---

### POST /api/generate-quiz-text - Генерация квиза из текста

**Body (JSON):**

```json
{
  "text": "Ваш длинный текст для создания квиза...",
  "count": 5,
  "difficulty": "Medium",
  "lang": "Russian",
  "user_email": "user@example.com"
}
```

**Пример с curl:**

```bash
curl -X POST "http://localhost:8000/api/generate-quiz-text" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key-1" \
  -d '{
    "text": "Искусственный интеллект (ИИ) - это область компьютерных наук...",
    "count": 5,
    "difficulty": "Medium",
    "lang": "Russian",
    "user_email": "user@example.com"
  }'
```

**Пример с Python:**

```python
import requests

url = "http://localhost:8000/api/generate-quiz-text"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "your-secret-key-1"
}

payload = {
    "text": "Искусственный интеллект (ИИ) - это область компьютерных наук...",
    "count": 5,
    "difficulty": "Medium",
    "lang": "Russian",
    "user_email": "user@example.com"
}

response = requests.post(url, headers=headers, json=payload)
print(response.json())
```

**Пример с JavaScript (fetch):**

```javascript
const url = "http://localhost:8000/api/generate-quiz-text";

const payload = {
  text: "Искусственный интеллект (ИИ) - это область компьютерных наук...",
  count: 5,
  difficulty: "Medium",
  lang: "Russian",
  user_email: "user@example.com"
};

fetch(url, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": "your-secret-key-1"
  },
  body: JSON.stringify(payload)
})
  .then(response => response.json())
  .then(data => console.log(data))
  .catch(error => console.error("Error:", error));
```

---

## Обработка ошибок

### 401 - Неверный API ключ

```json
{
  "detail": "Invalid API key"
}
```

### 400 - Неверные параметры

```json
{
  "detail": "count должен быть от 3 до 10"
}
```

### 402 - Недостаточно кредитов

```json
{
  "detail": "Недостаточно кредитов для пользователя user@example.com"
}
```

### 500 - Ошибка сервера

```json
{
  "detail": "Ошибка при обработке файла: ..."
}
```

---

## Интеграция с другими сервисами

### Пример webhook для автоматической генерации квизов

```python
from flask import Flask, request
import requests

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    # Получаем файл из webhook
    file = request.files['file']

    # Отправляем в Vyud AI API
    url = "http://localhost:8000/api/generate-quiz"
    headers = {"X-API-Key": "your-secret-key-1"}

    files = {"file": file}
    data = {"count": 5, "difficulty": "Medium", "lang": "Russian"}

    response = requests.post(url, headers=headers, files=files, data=data)

    return response.json()

if __name__ == '__main__':
    app.run(port=5000)
```

---

## Развертывание в production

### Docker

Создайте `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV OPENAI_API_KEY=""
ENV LLAMA_CLOUD_API_KEY=""
ENV API_KEYS=""

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Запуск:

```bash
docker build -t vyud-ai-api .
docker run -p 8000:8000 \
  -e OPENAI_API_KEY="sk-..." \
  -e LLAMA_CLOUD_API_KEY="llx_..." \
  -e API_KEYS="your-secret-key" \
  vyud-ai-api
```

---

## Безопасность

1. **Храните API ключи в secrets** - никогда не коммитьте их в git
2. **Используйте HTTPS** в production
3. **Ограничьте CORS** - измените `allow_origins` в api.py на конкретные домены
4. **Ротация ключей** - регулярно меняйте API ключи
5. **Rate limiting** - добавьте ограничение частоты запросов

---

## Поддержка

Для вопросов и поддержки: https://vyud.online
