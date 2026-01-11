-- Clear all test data (run manually in Supabase SQL Editor)

-- Clear chat logs
TRUNCATE TABLE chat_logs;

-- To delete users, go to Supabase Dashboard → Authentication → Users
-- and delete them manually (auth.users is managed by Supabase)
