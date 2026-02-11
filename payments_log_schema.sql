-- ============================================
-- ТАБЛИЦА ЛОГОВ ПЛАТЕЖЕЙ
-- ============================================

-- Создаем таблицу payments_log для логирования всех платежей
CREATE TABLE IF NOT EXISTS payments_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    email TEXT NOT NULL,
    username TEXT,
    plan_id TEXT NOT NULL,
    plan_title TEXT NOT NULL,
    amount_stars INTEGER NOT NULL,
    credits_purchased INTEGER NOT NULL,
    payment_type TEXT NOT NULL CHECK (payment_type IN ('credits', 'subscription')),
    telegram_payment_charge_id TEXT NOT NULL,
    provider_payment_charge_id TEXT NOT NULL,
    status TEXT DEFAULT 'completed' CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_payments_log_telegram_id ON payments_log(telegram_id);
CREATE INDEX IF NOT EXISTS idx_payments_log_created_at ON payments_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payments_log_plan_id ON payments_log(plan_id);
CREATE INDEX IF NOT EXISTS idx_payments_log_status ON payments_log(status);

-- Триггер для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_payments_log_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER payments_log_updated_at
    BEFORE UPDATE ON payments_log
    FOR EACH ROW
    EXECUTE FUNCTION update_payments_log_updated_at();

-- ============================================
-- ОБНОВЛЕНИЕ ТАБЛИЦЫ users_credits
-- ============================================

-- Добавляем поле subscription_expires_at в таблицу users_credits (если не существует)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users_credits'
        AND column_name = 'subscription_expires_at'
    ) THEN
        ALTER TABLE users_credits
        ADD COLUMN subscription_expires_at TIMESTAMP WITH TIME ZONE;
    END IF;
END $$;

-- Создаем индекс для поиска активных подписок
CREATE INDEX IF NOT EXISTS idx_users_credits_subscription ON users_credits(subscription_expires_at)
WHERE subscription_expires_at IS NOT NULL;

-- ============================================
-- ПРАВА ДОСТУПА (RLS - Row Level Security)
-- ============================================

-- Включаем RLS для таблицы payments_log
ALTER TABLE payments_log ENABLE ROW LEVEL SECURITY;

-- Политика: пользователи могут видеть только свои платежи
CREATE POLICY "Users can view own payments" ON payments_log
    FOR SELECT
    USING (telegram_id = current_setting('app.current_user_telegram_id', TRUE)::BIGINT);

-- Политика: сервис (бот) может вставлять логи платежей
CREATE POLICY "Service can insert payments" ON payments_log
    FOR INSERT
    WITH CHECK (true);

-- ============================================
-- ПРЕДСТАВЛЕНИЯ (VIEWS) ДЛЯ АНАЛИТИКИ
-- ============================================

-- Представление: статистика по тарифам
CREATE OR REPLACE VIEW payments_stats AS
SELECT
    plan_id,
    plan_title,
    payment_type,
    COUNT(*) as total_purchases,
    SUM(amount_stars) as total_stars,
    SUM(credits_purchased) as total_credits_sold,
    AVG(amount_stars) as avg_price,
    MIN(created_at) as first_purchase,
    MAX(created_at) as last_purchase
FROM payments_log
WHERE status = 'completed'
GROUP BY plan_id, plan_title, payment_type
ORDER BY total_purchases DESC;

-- Представление: топ покупателей
CREATE OR REPLACE VIEW top_buyers AS
SELECT
    telegram_id,
    username,
    COUNT(*) as total_purchases,
    SUM(amount_stars) as total_spent_stars,
    SUM(credits_purchased) as total_credits_purchased,
    MAX(created_at) as last_purchase_date
FROM payments_log
WHERE status = 'completed'
GROUP BY telegram_id, username
ORDER BY total_spent_stars DESC
LIMIT 100;

-- Представление: дневная статистика продаж
CREATE OR REPLACE VIEW daily_revenue AS
SELECT
    DATE(created_at) as date,
    COUNT(*) as purchases,
    SUM(amount_stars) as revenue_stars,
    COUNT(DISTINCT telegram_id) as unique_buyers,
    COUNT(CASE WHEN payment_type = 'credits' THEN 1 END) as credit_packages,
    COUNT(CASE WHEN payment_type = 'subscription' THEN 1 END) as subscriptions
FROM payments_log
WHERE status = 'completed'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- ============================================
-- КОММЕНТАРИИ К ТАБЛИЦАМ
-- ============================================

COMMENT ON TABLE payments_log IS 'Лог всех платежей через Telegram Stars';
COMMENT ON COLUMN payments_log.telegram_id IS 'Telegram ID пользователя';
COMMENT ON COLUMN payments_log.plan_id IS 'ID тарифа (credits_10, sub_month и т.д.)';
COMMENT ON COLUMN payments_log.amount_stars IS 'Сумма платежа в Telegram Stars';
COMMENT ON COLUMN payments_log.telegram_payment_charge_id IS 'ID платежа от Telegram';
COMMENT ON COLUMN payments_log.provider_payment_charge_id IS 'ID платежа от провайдера';
