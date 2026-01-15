-- Add feedback JSONB column to chat_logs
-- Structure: {"rating": "like"|"dislike", "comment": "optional text"}
ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS feedback JSONB;

-- Index for analytics
CREATE INDEX IF NOT EXISTS idx_chat_logs_feedback ON chat_logs(feedback)
    WHERE feedback IS NOT NULL;
