# VYUD AI Bot — Архитектура

## Структура файлов
```
/var/www/vyud_app/
├── bot.py              # Telegram бот (aiogram 3.x)
├── app.py              # Streamlit веб-приложение
├── auth.py             # Авторизация и работа с кредитами
├── logic.py            # Генерация квизов, модели данных
├── admin_stats.py      # Админ-панель (порт 8503)
├── .streamlit/
│   └── secrets.toml    # ⛔ Секреты (не в Git!)
└── venv/               # Виртуальное окружение
```

## Ключевые модели данных

### QuizQuestion (logic.py, строка 22)
```python
class QuizQuestion:
    scenario: str          # Текст вопроса (НЕ 'question'!)
    options: list          # Варианты ответов
    correct_option_id: int # Индекс правильного ответа
    explanation: str       # Объяснение
```

### Quiz (logic.py)
```python
class Quiz:
    questions: list[QuizQuestion]
```

## Async/Sync функции

### auth.py — ВСЕ СИНХРОННЫЕ
Вызывать через `await asyncio.to_thread(func, args)`:
- `get_user_credits(email)` → int
- `deduct_credit(email, amount)` → bool
- `save_quiz(email, title, questions, hints)` → str
- `get_user_quizzes(email)` → list

### bot.py — ВСЕ АСИНХРОННЫЕ
- `update_user_profile(user, generation_type)` — async
- `ensure_user_credits(telegram_id, username)` — async

## Критичные точки в bot.py

| Строки | Функционал | Что проверять |
|--------|-----------|---------------|
| 140-160 | Обработка аудио/видео | send_poll после генерации |
| 250-280 | Обработка документов | send_poll после генерации |
| 93-110 | update_user_profile | Premium статус |

## База данных (Supabase)

### Таблица users_credits
- `telegram_id` (PK)
- `email`
- `credits`
- `total_generations`
- `tariff`
- `telegram_premium` (bool)

### Таблица quizzes
- `id` (uuid)
- `owner_email`
- `title`
- `questions` (jsonb)
- `created_at`

## Деплой
```bash
# Безопасный деплой
./safe_deploy.sh

# Ручной рестарт бота
pkill -f bot.py && sleep 2 && cd /var/www/vyud_app && source venv/bin/activate && nohup python3 bot.py > bot.log 2>&1 &

# Проверка
ps aux | grep bot.py | grep -v grep
tail -20 bot.log
```

## Частые ошибки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `'QuizQuestion' has no attribute 'question'` | Поле называется `scenario` | Заменить на `q.scenario` |
| `object bool can't be used in 'await'` | await для sync функции | Использовать `asyncio.to_thread()` |
| `ModuleNotFoundError: aiogram` | Не активирован venv | `source venv/bin/activate` |
