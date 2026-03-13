#!/bin/bash
# Execute SQL migration for utm_events table

SUPABASE_URL="https://vdduyndldbetdhwtilks.supabase.co"
SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkZHV5bmRsZGJldGRod3RpbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjU5NzgwMTIsImV4cCI6MjA4MTU1NDAxMn0.t-4OESW1AtI9GRJEbxGAV8SYIoOrIyZs6NVghwwU4UE"

# Try to execute SQL via Supabase REST API (typically requires service_role key, not anon)
# This will likely fail, but we'll try

echo "Attempting to create utm_events table..."
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/exec_sql" \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$(cat migrations/001_utm_events.sql | tr '\n' ' ' | sed 's/"/\\"/g')\"}" 2>&1

echo ""
echo "If the above failed (expected with anon key), execute SQL manually:"
echo "https://vdduyndldbetdhwtilks.supabase.co/project/_/sql"
