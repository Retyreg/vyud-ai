# Деплой Vyud AI API на Railway

## 🚀 Быстрый старт

### 1. Подготовка проекта

Убедитесь, что все файлы для деплоя созданы:
- ✅ `Dockerfile` - конфигурация Docker образа
- ✅ `railway.toml` - конфигурация Railway
- ✅ `.dockerignore` - исключения для Docker

### 2. Создание проекта на Railway

#### Вариант A: Через GitHub (Рекомендуется)

1. Запушьте код в GitHub (уже сделано)
2. Откройте [Railway](https://railway.app)
3. Нажмите **"New Project"**
4. Выберите **"Deploy from GitHub repo"**
5. Выберите репозиторий `Retyreg/vyud-ai`
6. Railway автоматически обнаружит `Dockerfile` и начнет деплой

#### Вариант B: Через Railway CLI

```bash
# Установите Railway CLI
npm i -g @railway/cli

# Войдите в аккаунт
railway login

# Инициализируйте проект
railway init

# Задеплойте
railway up
```

### 3. Настройка Environment Variables

В Railway Dashboard перейдите в **Variables** и добавьте:

```bash
# OpenAI API Key
OPENAI_API_KEY=sk-proj-your-key-here

# Llama Cloud API Key
LLAMA_CLOUD_API_KEY=llx-your-key-here

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-key-here

# API Keys для аутентификации (через запятую)
API_KEYS=vyud_api_key_xxx,vyud_api_key_yyy

# Port (Railway автоматически устанавливает)
PORT=8000
```

### 4. Проверка деплоя

После успешного деплоя Railway предоставит вам URL типа:
```
https://vyud-ai-production.up.railway.app
```

Проверьте работу API:

```bash
# Health check
curl https://your-app.up.railway.app/api/health

# Тест генерации квиза
curl -X POST "https://your-app.up.railway.app/api/generate-quiz-text" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "text": "Test content",
    "count": 3,
    "difficulty": "Easy",
    "lang": "Russian"
  }'
```

### 5. Документация API

После деплоя документация будет доступна по адресу:
- Swagger UI: `https://your-app.up.railway.app/api/docs`
- ReDoc: `https://your-app.up.railway.app/api/redoc`

## 🔧 Настройки Railway

### Автоматический деплой

Railway автоматически деплоит при каждом push в `main` branch.

Чтобы отключить:
```bash
railway service settings --no-auto-deploy
```

### Масштабирование

Railway автоматически масштабирует приложение. Можно настроить:
- Минимум/максимум реплик
- Ресурсы (CPU/RAM)
- Автоскейлинг по нагрузке

### Мониторинг

В Railway Dashboard доступны:
- 📊 Логи приложения
- 📈 Метрики (CPU, RAM, Network)
- 🔔 Алерты

### Домен

Можно привязать свой домен:
1. Railway Dashboard → Settings → Domains
2. Добавьте свой домен
3. Настройте DNS записи

## 🐛 Troubleshooting

### Проблема: Build fails

**Решение:**
```bash
# Проверьте логи билда в Railway Dashboard
# Обычно помогает очистка кэша:
railway service settings --clear-cache
```

### Проблема: API не отвечает

**Решение:**
1. Проверьте environment variables
2. Проверьте логи: `railway logs`
3. Убедитесь, что PORT переменная установлена

### Проблема: Out of memory

**Решение:**
- Увеличьте лимит памяти в Railway settings
- Оптимизируйте загрузку библиотек (lazy imports уже настроены)

## 💰 Стоимость

Railway предоставляет:
- **$5 бесплатно каждый месяц**
- Далее ~$0.000463/GB-hour для памяти
- ~$0.000231/vCPU-hour для процессора

Примерная стоимость для легкой нагрузки: **$5-10/месяц**

## 📚 Дополнительные ресурсы

- [Railway Documentation](https://docs.railway.app)
- [Railway Discord](https://discord.gg/railway)
- [Railway Status](https://status.railway.app)

## 🔄 Обновление деплоя

Просто пушьте изменения в GitHub:

```bash
git add .
git commit -m "Update API"
git push origin main
```

Railway автоматически задеплоит новую версию!
