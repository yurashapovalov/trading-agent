-- AskBar Database Schema
-- Complete schema for multi-agent trading analytics system
-- Generated: 2026-01-11

--------------------------------------------------------------------------------
-- CHAT_LOGS: Final results of each user request
--------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS chat_logs (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID UNIQUE DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id VARCHAR(100),              -- thread_id from LangGraph

    -- Request/Response
    question TEXT NOT NULL,
    response TEXT,

    -- Routing & agents
    route TEXT,                           -- 'data', 'concept', 'hypothetical'
    agents_used TEXT[] DEFAULT '{}',      -- ['understander', 'data_fetcher', 'analyst', 'validator']

    -- Validation
    validation_attempts INTEGER DEFAULT 1,
    validation_passed BOOLEAN,

    -- Token usage (totals across all agents)
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    thinking_tokens INTEGER DEFAULT 0,
    cost_usd DECIMAL(10, 6) DEFAULT 0,

    -- Metadata
    model VARCHAR(50),
    provider VARCHAR(20) DEFAULT 'gemini',
    duration_ms INTEGER,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chat_logs_user_id ON chat_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_logs_created_at ON chat_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_logs_session ON chat_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_logs_request_id ON chat_logs(request_id);
CREATE INDEX IF NOT EXISTS idx_chat_logs_route ON chat_logs(route);
CREATE INDEX IF NOT EXISTS idx_chat_logs_validation ON chat_logs(validation_passed)
    WHERE validation_passed IS NOT NULL;

-- Row Level Security
ALTER TABLE chat_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own chat logs" ON chat_logs
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own chat logs" ON chat_logs
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Service role full access" ON chat_logs
    FOR ALL USING (auth.role() = 'service_role');


--------------------------------------------------------------------------------
-- REQUEST_TRACES: Full trace of every agent step
--------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS request_traces (
    id BIGSERIAL PRIMARY KEY,

    -- Links to parent request
    request_id UUID REFERENCES chat_logs(request_id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Step identification
    step_number INTEGER NOT NULL,
    agent_name TEXT NOT NULL,             -- 'router', 'data_agent', 'analyst', 'educator', 'validator'
    agent_type TEXT NOT NULL,             -- 'routing', 'data', 'output'

    -- Agent I/O
    input_data JSONB,
    output_data JSONB,

    -- SQL execution (for DATA agents)
    sql_query TEXT,
    sql_result JSONB,
    sql_rows_returned INTEGER,
    sql_error TEXT,

    -- Validation (for Validator agent)
    validation_status TEXT,               -- 'ok', 'rewrite', 'need_more_data'
    validation_issues TEXT[],
    validation_feedback TEXT,

    -- LLM details
    prompt_template TEXT,
    model_used TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    thinking_tokens INTEGER DEFAULT 0,
    cost_usd DECIMAL(10, 6) DEFAULT 0,

    -- Timing
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_traces_request_id ON request_traces(request_id);
CREATE INDEX IF NOT EXISTS idx_traces_user_id ON request_traces(user_id);
CREATE INDEX IF NOT EXISTS idx_traces_created_at ON request_traces(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_traces_agent_name ON request_traces(agent_name);
CREATE INDEX IF NOT EXISTS idx_traces_agent_type ON request_traces(agent_type);
CREATE INDEX IF NOT EXISTS idx_traces_validation_status ON request_traces(validation_status)
    WHERE validation_status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_traces_sql_error ON request_traces(sql_error)
    WHERE sql_error IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_traces_request_step ON request_traces(request_id, step_number);

-- Row Level Security
ALTER TABLE request_traces ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own traces" ON request_traces
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Service role full access on traces" ON request_traces
    FOR ALL USING (auth.role() = 'service_role');
