# Деплой VYUD AI

## Архитектура

```
vyud-tma (React)  →  Vercel        (frontend, авто-деплой из Retyreg/vyud-tma)
vyud-api (FastAPI) →  Render web    (REST API для Mini App)
vyud-bot (aiogram) →  Render worker (Telegram-бот, polling)
```

Бот и API разделены — падение одного не затрагивает другой.
Общаются только через Supabase (не по HTTP друг с другом).

---

## Render — первый деплой

1. Открой https://dashboard.render.com → **New → Blueprint**
2. Подключи репо `Retyreg/vyud-ai`
3. Render автоматически найдёт `render.yaml` и создаст оба сервиса:
   - `vyud-api` — web service (FastAPI)
   - `vyud-bot` — background worker (aiogram)
4. Для каждого сервиса добавь переменные окружения (см. `.env.example`):

| Переменная | Где взять |
|---|---|
| `TELEGRAM_BOT_TOKEN` | @BotFather |
| `OPENAI_API_KEY` | platform.openai.com |
| `LLAMA_CLOUD_API_KEY` | cloud.llamaindex.ai (опционально) |
| `SUPABASE_URL` | Supabase → Settings → API |
| `SUPABASE_KEY` | Supabase → Settings → API → **service_role** |
| `API_KEYS` | Придумать случайную строку, добавить в VITE_API_KEY на Vercel |

> ⚠️ Используй `service_role` ключ Supabase — он позволяет обходить RLS на сервере.

5. После деплоя скопируй URL `vyud-api` (вида `https://vyud-api.onrender.com`)
6. Обнови в `vyud-tma` → Vercel → Environment Variables:
   ```
   VITE_API_URL=https://vyud-api.onrender.com/api
   ```

---

## Vercel — Mini App (vyud-tma)

Автоматически деплоится при пуше в `main` ветку `Retyreg/vyud-tma`.

Переменные окружения в Vercel Dashboard → Settings → Environment Variables:

| Переменная | Значение |
|---|---|
| `VITE_API_URL` | `https://vyud-api.onrender.com/api` |
| `VITE_API_KEY` | Тот же ключ что в `API_KEYS` бэкенда |
| `VITE_SUPABASE_URL` | Supabase URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase **anon** key (публичный) |

---

## Обновление кода

```bash
git push origin main   # → Render автоматически пересобирает оба сервиса
```

---

## Free tier ограничения Render

- Web service засыпает после 15 мин бездействия (cold start ~30 сек)
- Worker не засыпает — бот всегда онлайн
- 750 часов/месяц бесплатно на все сервисы

Для продакшна рекомендуется `starter` план ($7/мес) — нет cold start.
