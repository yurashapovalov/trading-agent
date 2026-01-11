-- Migration: Create request_traces table for full trace logging
-- Stores every step of every agent for debugging, analytics, and future ML

CREATE TABLE IF NOT EXISTS request_traces (
    id BIGSERIAL PRIMARY KEY,

    -- Links to parent request
    request_id UUID REFERENCES chat_logs(request_id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Step identification
    step_number INTEGER NOT NULL,
    agent_name TEXT NOT NULL,         -- 'router', 'data_agent', 'analyst', 'educator', 'validator'
    agent_type TEXT NOT NULL,         -- 'routing', 'data', 'output'

    -- Agent I/O (full data for replay/debugging)
    input_data JSONB,                 -- What the agent received
    output_data JSONB,                -- What the agent returned

    -- SQL execution (for DATA agents)
    sql_query TEXT,
    sql_result JSONB,
    sql_rows_returned INTEGER,
    sql_error TEXT,

    -- Validation details (for Validator agent)
    validation_status TEXT,           -- 'ok', 'rewrite', 'need_more_data'
    validation_issues TEXT[],         -- List of found issues
    validation_feedback TEXT,         -- Feedback sent back to Analyst

    -- LLM details (for cost tracking and debugging)
    prompt_template TEXT,             -- Which prompt was used
    model_used TEXT,                  -- 'gemini-2.0-flash', 'claude-sonnet', etc.
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    thinking_tokens INTEGER DEFAULT 0,
    cost_usd DECIMAL(10, 6) DEFAULT 0,

    -- Timing
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Core indexes for common queries
CREATE INDEX IF NOT EXISTS idx_traces_request_id ON request_traces(request_id);
CREATE INDEX IF NOT EXISTS idx_traces_user_id ON request_traces(user_id);
CREATE INDEX IF NOT EXISTS idx_traces_created_at ON request_traces(created_at DESC);

-- Analytics indexes
CREATE INDEX IF NOT EXISTS idx_traces_agent_name ON request_traces(agent_name);
CREATE INDEX IF NOT EXISTS idx_traces_agent_type ON request_traces(agent_type);
CREATE INDEX IF NOT EXISTS idx_traces_validation_status ON request_traces(validation_status)
    WHERE validation_status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_traces_sql_error ON request_traces(sql_error)
    WHERE sql_error IS NOT NULL;

-- Composite index for step ordering
CREATE INDEX IF NOT EXISTS idx_traces_request_step ON request_traces(request_id, step_number);

-- Enable Row Level Security
ALTER TABLE request_traces ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own traces
CREATE POLICY "Users can view own traces" ON request_traces
    FOR SELECT
    USING (auth.uid() = user_id);

-- Policy: Service role can do anything (for backend logging)
CREATE POLICY "Service role full access on traces" ON request_traces
    FOR ALL
    USING (auth.role() = 'service_role');

-- Comments for documentation
COMMENT ON TABLE request_traces IS 'Full trace of every agent step for debugging, analytics, and future ML training';
COMMENT ON COLUMN request_traces.step_number IS 'Sequential step number within the request (1, 2, 3...)';
COMMENT ON COLUMN request_traces.agent_type IS 'Category: routing (no validation), data (code validation), output (LLM validation)';
COMMENT ON COLUMN request_traces.input_data IS 'Full input received by the agent (for replay)';
COMMENT ON COLUMN request_traces.output_data IS 'Full output returned by the agent (for replay)';
COMMENT ON COLUMN request_traces.validation_status IS 'ok=pass, rewrite=send back to Analyst, need_more_data=send back to Data Agent';
