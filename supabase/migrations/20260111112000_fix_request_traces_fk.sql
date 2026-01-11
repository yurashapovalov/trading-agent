-- Remove foreign key constraint from request_traces
-- Traces are logged DURING processing, but chat_logs entry is created at the END
-- So we can't enforce FK constraint

ALTER TABLE request_traces
DROP CONSTRAINT IF EXISTS request_traces_request_id_fkey;

-- Add index for performance (queries by request_id)
CREATE INDEX IF NOT EXISTS idx_request_traces_request_id ON request_traces(request_id);
