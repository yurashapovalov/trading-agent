-- Add cached_tokens to chat_sessions.stats
-- Generated: 2026-01-25

-- Add cached_tokens to existing stats JSONB
UPDATE public.chat_sessions
SET stats = stats || '{"cached_tokens": 0}'::jsonb
WHERE stats->>'cached_tokens' IS NULL;

-- Update default value for new sessions
ALTER TABLE public.chat_sessions
ALTER COLUMN stats SET DEFAULT '{"cost_usd": 0, "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cached_tokens": 0, "message_count": 0}'::jsonb;

-- Add comment
COMMENT ON COLUMN public.chat_sessions.stats IS 'Aggregated token usage: {input_tokens, output_tokens, thinking_tokens, cached_tokens, cost_usd, message_count}';
