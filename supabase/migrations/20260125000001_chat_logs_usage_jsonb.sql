-- Convert separate token fields to single JSONB usage field
-- Generated: 2026-01-25

-- Add new usage JSONB field with structure for all LLM agents
ALTER TABLE public.chat_logs ADD COLUMN IF NOT EXISTS usage jsonb DEFAULT '{
  "intent": null,
  "understander": null,
  "clarifier": null,
  "parser": null,
  "presenter": null,
  "responder": null,
  "total": {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cached_tokens": 0, "cost_usd": 0}
}'::jsonb;

-- Migrate existing data to new structure (put old values in total)
UPDATE public.chat_logs
SET usage = jsonb_build_object(
  'intent', null,
  'understander', null,
  'clarifier', null,
  'parser', null,
  'presenter', null,
  'responder', null,
  'total', jsonb_build_object(
    'input_tokens', COALESCE(input_tokens, 0),
    'output_tokens', COALESCE(output_tokens, 0),
    'thinking_tokens', COALESCE(thinking_tokens, 0),
    'cached_tokens', 0,
    'cost_usd', COALESCE(cost_usd, 0)
  )
)
WHERE usage IS NULL OR usage = '{}'::jsonb;

-- Drop old columns
ALTER TABLE public.chat_logs DROP COLUMN IF EXISTS input_tokens;
ALTER TABLE public.chat_logs DROP COLUMN IF EXISTS output_tokens;
ALTER TABLE public.chat_logs DROP COLUMN IF EXISTS thinking_tokens;
ALTER TABLE public.chat_logs DROP COLUMN IF EXISTS cost_usd;

-- Add comment
COMMENT ON COLUMN public.chat_logs.usage IS 'Token usage per LLM agent: {intent, understander, clarifier, parser, presenter, responder, total}. Each agent has {input_tokens, output_tokens, thinking_tokens, cached_tokens, cost_usd}.';
