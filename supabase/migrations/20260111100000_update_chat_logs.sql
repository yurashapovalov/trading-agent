-- Migration: Add multi-agent architecture fields to chat_logs
-- This prepares the table for LangGraph-based multi-agent system

-- Add unique request_id for linking with request_traces
ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS request_id UUID UNIQUE DEFAULT gen_random_uuid();

-- Routing information
ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS route TEXT;  -- 'data', 'concept', 'hypothetical'
ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS agents_used TEXT[] DEFAULT '{}';

-- Aggregated SQL metrics
ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS total_sql_queries INTEGER DEFAULT 0;
ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS total_rows_returned INTEGER DEFAULT 0;

-- Validation tracking
ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS validation_attempts INTEGER DEFAULT 1;
ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS validation_passed BOOLEAN;

-- Human-in-the-loop (interrupt)
ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS was_interrupted BOOLEAN DEFAULT FALSE;
ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS interrupt_reason TEXT;

-- Rename token columns for clarity (total_ prefix indicates aggregated across all agents)
-- Note: These renames are optional - only if you want clearer naming
-- ALTER TABLE chat_logs RENAME COLUMN input_tokens TO total_input_tokens;
-- ALTER TABLE chat_logs RENAME COLUMN output_tokens TO total_output_tokens;
-- ALTER TABLE chat_logs RENAME COLUMN cost_usd TO total_cost_usd;
-- ALTER TABLE chat_logs RENAME COLUMN duration_ms TO total_duration_ms;

-- Add index on request_id for fast lookups from request_traces
CREATE INDEX IF NOT EXISTS idx_chat_logs_request_id ON chat_logs(request_id);

-- Add index on route for analytics
CREATE INDEX IF NOT EXISTS idx_chat_logs_route ON chat_logs(route);

-- Add index for validation analysis
CREATE INDEX IF NOT EXISTS idx_chat_logs_validation ON chat_logs(validation_passed) WHERE validation_passed IS NOT NULL;

COMMENT ON COLUMN chat_logs.request_id IS 'Unique ID linking to request_traces table';
COMMENT ON COLUMN chat_logs.route IS 'Router decision: data, concept, hypothetical';
COMMENT ON COLUMN chat_logs.agents_used IS 'List of agents that processed this request';
COMMENT ON COLUMN chat_logs.validation_attempts IS 'How many validation loops before passing';
COMMENT ON COLUMN chat_logs.was_interrupted IS 'Whether human-in-the-loop was triggered';
