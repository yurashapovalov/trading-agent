-- Update increment_chat_stats RPC to include cached_tokens
-- Generated: 2026-01-25

CREATE OR REPLACE FUNCTION increment_chat_stats(
    p_chat_id UUID,
    p_input_tokens INTEGER DEFAULT 0,
    p_output_tokens INTEGER DEFAULT 0,
    p_thinking_tokens INTEGER DEFAULT 0,
    p_cached_tokens INTEGER DEFAULT 0,
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
                            jsonb_set(
                                stats,
                                '{message_count}',
                                to_jsonb(COALESCE((stats->>'message_count')::integer, 0) + 1)
                            ),
                            '{input_tokens}',
                            to_jsonb(COALESCE((stats->>'input_tokens')::integer, 0) + p_input_tokens)
                        ),
                        '{output_tokens}',
                        to_jsonb(COALESCE((stats->>'output_tokens')::integer, 0) + p_output_tokens)
                    ),
                    '{thinking_tokens}',
                    to_jsonb(COALESCE((stats->>'thinking_tokens')::integer, 0) + p_thinking_tokens)
                ),
                '{cached_tokens}',
                to_jsonb(COALESCE((stats->>'cached_tokens')::integer, 0) + p_cached_tokens)
            ),
            '{cost_usd}',
            to_jsonb(COALESCE((stats->>'cost_usd')::numeric, 0) + p_cost_usd)
        ),
        updated_at = now()
    WHERE id = p_chat_id;
END;
$$;

COMMENT ON FUNCTION increment_chat_stats(UUID, INTEGER, INTEGER, INTEGER, INTEGER, NUMERIC) IS 'Atomically increment chat session stats including cached_tokens';
