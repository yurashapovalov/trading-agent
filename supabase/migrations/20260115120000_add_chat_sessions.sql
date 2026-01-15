-- Migration: Add chat_sessions table
-- Run this in Supabase SQL Editor
-- Version: 001

--------------------------------------------------------------------------------
-- 1. Create chat_sessions table
--------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT,
    status TEXT DEFAULT 'active',  -- 'active' or 'deleted' (soft delete for analytics)
    stats JSONB DEFAULT '{"message_count": 0, "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cost_usd": 0}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON chat_sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_status ON chat_sessions(status) WHERE status = 'active';

ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own chat sessions" ON chat_sessions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own chat sessions" ON chat_sessions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own chat sessions" ON chat_sessions
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own chat sessions" ON chat_sessions
    FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Service role full access on sessions" ON chat_sessions
    FOR ALL USING (auth.role() = 'service_role');


--------------------------------------------------------------------------------
-- 2. Add chat_id column to chat_logs
--------------------------------------------------------------------------------

ALTER TABLE chat_logs
ADD COLUMN IF NOT EXISTS chat_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_chat_logs_chat_id ON chat_logs(chat_id);


--------------------------------------------------------------------------------
-- 3. Migrate existing data: create sessions from existing session_ids
--------------------------------------------------------------------------------

-- Create chat sessions for each unique user_id + session_id combination
INSERT INTO chat_sessions (id, user_id, title, created_at)
SELECT DISTINCT ON (user_id, session_id)
    gen_random_uuid(),
    user_id,
    'Chat ' || ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY MIN(created_at)),
    MIN(created_at)
FROM chat_logs
WHERE user_id IS NOT NULL
GROUP BY user_id, session_id
ON CONFLICT DO NOTHING;

-- Link chat_logs to their chat_sessions
-- This creates a temp mapping and updates chat_logs
WITH session_mapping AS (
    SELECT DISTINCT ON (cl.user_id, cl.session_id)
        cl.user_id,
        cl.session_id,
        cs.id as chat_id
    FROM chat_logs cl
    JOIN chat_sessions cs ON cs.user_id = cl.user_id
    WHERE cl.chat_id IS NULL
)
UPDATE chat_logs cl
SET chat_id = sm.chat_id
FROM session_mapping sm
WHERE cl.user_id = sm.user_id
  AND cl.session_id = sm.session_id
  AND cl.chat_id IS NULL;


--------------------------------------------------------------------------------
-- 4. RPC function for atomic stats increment
--------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION increment_chat_stats(
    p_chat_id UUID,
    p_input_tokens INTEGER DEFAULT 0,
    p_output_tokens INTEGER DEFAULT 0,
    p_thinking_tokens INTEGER DEFAULT 0,
    p_cost_usd NUMERIC DEFAULT 0
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE chat_sessions
    SET
        stats = jsonb_set(
            jsonb_set(
                jsonb_set(
                    jsonb_set(
                        jsonb_set(
                            stats,
                            '{message_count}',
                            to_jsonb(COALESCE((stats->>'message_count')::int, 0) + 1)
                        ),
                        '{input_tokens}',
                        to_jsonb(COALESCE((stats->>'input_tokens')::int, 0) + p_input_tokens)
                    ),
                    '{output_tokens}',
                    to_jsonb(COALESCE((stats->>'output_tokens')::int, 0) + p_output_tokens)
                ),
                '{thinking_tokens}',
                to_jsonb(COALESCE((stats->>'thinking_tokens')::int, 0) + p_thinking_tokens)
            ),
            '{cost_usd}',
            to_jsonb(COALESCE((stats->>'cost_usd')::numeric, 0) + p_cost_usd)
        ),
        updated_at = NOW()
    WHERE id = p_chat_id;
END;
$$;
