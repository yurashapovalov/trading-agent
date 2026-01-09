-- Chat logs table for tracking usage
CREATE TABLE IF NOT EXISTS chat_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Request/Response
    question TEXT NOT NULL,
    response TEXT,

    -- Tools used (full log with inputs and results)
    tools_used JSONB DEFAULT '[]',

    -- Token usage
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    thinking_tokens INTEGER DEFAULT 0,
    cost_usd DECIMAL(10, 6) DEFAULT 0,

    -- Metadata
    model VARCHAR(50),
    provider VARCHAR(20) DEFAULT 'gemini',
    duration_ms INTEGER,
    session_id VARCHAR(100),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_chat_logs_user_id ON chat_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_logs_created_at ON chat_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_logs_session ON chat_logs(session_id);

-- Enable Row Level Security
ALTER TABLE chat_logs ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own logs
CREATE POLICY "Users can view own chat logs" ON chat_logs
    FOR SELECT
    USING (auth.uid() = user_id);

-- Policy: Users can insert their own logs
CREATE POLICY "Users can insert own chat logs" ON chat_logs
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Policy: Service role can do anything (for backend)
CREATE POLICY "Service role full access" ON chat_logs
    FOR ALL
    USING (auth.role() = 'service_role');
