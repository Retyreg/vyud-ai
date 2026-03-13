# UTM Integration Guide для VYUD AI

## ✅ Выполнено

1. **Создана таблица SQL**: `/var/www/vyud_app/migrations/001_utm_events.sql`
2. **Создан модуль**: `/var/www/vyud_app/utm_tracker.py`
3. **Импорт добавлен** в bot.py: `import utm_tracker` (строка 21)
4. **Бэкапы созданы**: app.py.bak_utm_20260305, bot.py.bak_utm_20260305, admin_stats.py.bak_utm_20260305

## 🔧 Требует ручного выполнения

### 1. Создать таблицу utm_events в Supabase
Открыть: https://vdduyndldbetdhwtilks.supabase.co/project/_/sql
Выполнить SQL из: `/var/www/vyud_app/migrations/001_utm_events.sql`

### 2. Интеграция в bot.py

#### A) В функции `cmd_start` (после строки 1222):
После `start_info = parse_start_param(command.args)` добавить:

```python
    # === UTM TRACKING ===
    utm_data = utm_tracker.parse_utm_from_start_param(command.args) if command.args else {}
    if any(utm_data.values()):
        utm_tracker.track_event(
            funnel_step="visit",
            telegram_id=telegram_id,
            source_platform="telegram_bot",
            **utm_data
        )
```

#### B) В функции `ensure_user_credits` (после создания нового юзера, строка ~530):
После `supabase.table('users_credits').insert({...}).execute()` добавить:

```python
            # Track signup
            utm_tracker.track_event(
                funnel_step="signup",
                telegram_id=telegram_id,
                source_platform="telegram_bot"
            )
```

#### C) В функции генерации (где вызывается deduct_credit):
Добавить после успешной генерации:

```python
        # Track generation funnel
        total_gens = user_data.get("total_generations", 0)
        if total_gens == 1:
            utm_tracker.track_event(funnel_step="first_generation", telegram_id=telegram_id, source_platform="telegram_bot")
        elif total_gens == 2:
            utm_tracker.track_event(funnel_step="second_generation", telegram_id=telegram_id, source_platform="telegram_bot")
```

### 3. Интеграция в app.py

#### A) В начале файла (после импортов):
```python
import utm_tracker
```

#### B) После инициализации Streamlit (строка ~10):
```python
# UTM tracking from URL
query_params = st.query_params
utm_data = utm_tracker.parse_utm_from_url_params(query_params)

if any(utm_data.values()) and "utm_tracked" not in st.session_state:
    st.session_state["utm_tracked"] = True
    st.session_state["utm_data"] = utm_data
    utm_tracker.track_event(
        funnel_step="visit",
        source_platform="web",
        page_url="app.vyud.online",
        **utm_data
    )
```

#### C) При регистрации нового пользователя:
```python
utm_tracker.track_event(funnel_step="signup", email=user_email, source_platform="web")
```

#### D) При SCORM экспорте (после успешного скачивания):
```python
utm_tracker.track_event(funnel_step="scorm_export", email=user_email, source_platform="web")
```

### 4. Расширение admin_stats.py

Добавить новый таб "📊 UTM & Воронка" с:
- Воронка конверсии (plotly funnel chart)
- Эффективность источников (таблица)
- Генератор UTM-ссылок
- Динамика по дням

См. код в промпте.

## 🧪 Тестирование

```bash
# 1. Проверка модуля
python3 -c "from utm_tracker import track_event; print('✅ Import OK')"

# 2. Проверка таблицы
python3 -c "
import toml
from supabase import create_client
s = toml.load('.streamlit/secrets.toml')
sb = create_client(s['SUPABASE_URL'], s['SUPABASE_KEY'])
r = sb.table('utm_events').select('id').limit(1).execute()
print(f'✅ Table exists: {len(r.data)} rows')
"

# 3. Тест записи
python3 -c "
from utm_tracker import track_event
track_event('visit', telegram_id=999, utm_source='test', utm_campaign='integration_test', source_platform='test')
print('✅ Event tracked')
"

# 4. Перезапуск
pkill -f bot.py && pkill -f "streamlit run app.py" && pkill -f admin_stats
sleep 2
cd /var/www/vyud_app
nohup venv/bin/python3 bot.py > bot.log 2>&1 &
nohup venv/bin/streamlit run app.py --server.port 8501 > streamlit.log 2>&1 &
nohup venv/bin/streamlit run admin_stats.py --server.port 8503 > admin_stats.log 2>&1 &
```

## 📊 UTM Links Examples

Telegram Bot:
- `https://t.me/VyudAiBot?start=utm_telegram_cpc_spring26_A`
- `https://t.me/VyudAiBot?start=utm_vk_social_hrtest_B`

Web App:
- `https://app.vyud.online/?utm_source=youtube&utm_medium=video&utm_campaign=review1`
- `https://app.vyud.online/?utm_source=google&utm_medium=cpc&utm_campaign=hr_edu`

## 📈 Воронка

visit → signup → first_generation → payment → repeat → scorm_export

CAC = Рекламные расходы / Signups
Conversion visit→signup = Signups / Visits * 100%
Conversion signup→first_gen = First_gen / Signups * 100%

## ⚠️ Важно

- UTM работает ПАРАЛЛЕЛЬНО с реферальной системой
- Один пользователь может иметь и ref_code и UTM
- Graceful degradation: если таблицы нет, трекинг не ломает приложение
