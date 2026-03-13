-- UTM Events Table for VYUD AI Marketing Analytics
-- Stores UTM parameters and conversion funnel events

CREATE TABLE IF NOT EXISTS utm_events (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- User Identification
    telegram_id BIGINT,
    email TEXT,
    session_id TEXT,
    
    -- UTM Parameters
    utm_source TEXT,        -- telegram, vk, youtube, google, direct
    utm_medium TEXT,        -- cpc, social, video, organic, bot
    utm_campaign TEXT,      -- campaign name
    utm_content TEXT,       -- ad variant (A/B test)
    utm_term TEXT,          -- keyword
    
    -- Conversion Funnel
    funnel_step TEXT,       -- visit, signup, first_generation, payment, repeat, scorm_export
    
    -- Context
    source_platform TEXT,   -- web, telegram_bot, landing
    page_url TEXT,
    user_agent TEXT,
    referrer TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_utm_source ON utm_events(utm_source);
CREATE INDEX IF NOT EXISTS idx_utm_campaign ON utm_events(utm_campaign);
CREATE INDEX IF NOT EXISTS idx_funnel_step ON utm_events(funnel_step);
CREATE INDEX IF NOT EXISTS idx_created_at ON utm_events(created_at);
CREATE INDEX IF NOT EXISTS idx_telegram_id ON utm_events(telegram_id);
CREATE INDEX IF NOT EXISTS idx_email ON utm_events(email);

-- Comment
COMMENT ON TABLE utm_events IS 'Marketing analytics: UTM tracking and conversion funnel events';
