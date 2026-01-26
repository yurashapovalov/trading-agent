-- Cleanup chat_logs: remove unused fields
-- Generated: 2026-01-25

-- Remove deprecated/unused columns
ALTER TABLE public.chat_logs DROP COLUMN IF EXISTS model;
ALTER TABLE public.chat_logs DROP COLUMN IF EXISTS provider;
ALTER TABLE public.chat_logs DROP COLUMN IF EXISTS session_id;
ALTER TABLE public.chat_logs DROP COLUMN IF EXISTS validation_attempts;
ALTER TABLE public.chat_logs DROP COLUMN IF EXISTS validation_passed;

-- Remove indexes for dropped columns
DROP INDEX IF EXISTS idx_chat_logs_session;
DROP INDEX IF EXISTS idx_chat_logs_validation;

-- Add comment
COMMENT ON TABLE public.chat_logs IS 'Individual request/response pairs. Token usage is summed from request_traces.';
