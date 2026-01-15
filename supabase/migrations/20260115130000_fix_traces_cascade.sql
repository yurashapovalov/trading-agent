-- Fix: Add CASCADE delete to request_traces
-- When chat_logs are deleted, traces should be deleted too

-- Drop existing constraint and recreate with CASCADE
ALTER TABLE request_traces
DROP CONSTRAINT IF EXISTS request_traces_request_id_fkey;

ALTER TABLE request_traces
ADD CONSTRAINT request_traces_request_id_fkey
FOREIGN KEY (request_id)
REFERENCES chat_logs(request_id)
ON DELETE CASCADE;
