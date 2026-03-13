-- SQL Миграция: Механика удержания (Ударный режим / Streaks)
-- Добавляем поля current_streak и last_activity в таблицу users_credits

DO $$ 
BEGIN
    -- Добавляем поле current_streak (по умолчанию 0)
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'users_credits' 
        AND column_name = 'current_streak'
    ) THEN
        ALTER TABLE users_credits 
        ADD COLUMN current_streak INTEGER DEFAULT 0;
    END IF;

    -- Добавляем поле last_activity (для хранения даты последней успешной генерации)
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'users_credits' 
        AND column_name = 'last_activity'
    ) THEN
        ALTER TABLE users_credits 
        ADD COLUMN last_activity TIMESTAMP WITH TIME ZONE;
    END IF;
END $$;

-- Создаем индекс для быстрого поиска активных пользователей
CREATE INDEX IF NOT EXISTS idx_users_credits_last_activity 
ON users_credits(last_activity);
