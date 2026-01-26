-- Add separate usage column to request_traces
-- Separates token usage from agent-specific output_data for easier aggregation
-- Generated: 2026-01-25

-- Add usage column
ALTER TABLE public.request_traces
ADD COLUMN IF NOT EXISTS usage jsonb;

-- Comment
COMMENT ON COLUMN public.request_traces.usage IS 'Token usage: {input_tokens, output_tokens, thinking_tokens, cached_tokens}';

-- Index for usage queries (optional, for cost analysis)
CREATE INDEX IF NOT EXISTS idx_traces_usage ON public.request_traces USING gin (usage);
