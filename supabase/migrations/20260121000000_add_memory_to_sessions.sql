-- Add memory field to chat_sessions for conversation persistence
-- Stores summaries and key_facts as JSONB
-- Generated: 2026-01-21

-- Add memory column
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS
  memory JSONB DEFAULT '{"summaries": [], "key_facts": []}'::jsonb;

-- Composite index for fast recent messages lookup
CREATE INDEX IF NOT EXISTS idx_chat_logs_chat_created
ON chat_logs(chat_id, created_at DESC);

-- Comment
COMMENT ON COLUMN chat_sessions.memory IS 'Conversation memory: {summaries: [{content, up_to_id}], key_facts: [string]}';
