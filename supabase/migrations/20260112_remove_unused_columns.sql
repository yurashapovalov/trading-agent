-- Migration: Remove unused columns from chat_logs
-- These fields are from legacy tool-based architecture

-- Drop unused columns from chat_logs
ALTER TABLE chat_logs DROP COLUMN IF EXISTS tools_used;
ALTER TABLE chat_logs DROP COLUMN IF EXISTS total_sql_queries;
ALTER TABLE chat_logs DROP COLUMN IF EXISTS total_rows_returned;
ALTER TABLE chat_logs DROP COLUMN IF EXISTS was_interrupted;
ALTER TABLE chat_logs DROP COLUMN IF EXISTS interrupt_reason;
