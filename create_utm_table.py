"""
Creates utm_events table in Supabase.
Run: python3 create_utm_table.py
"""
import toml
from supabase import create_client
import sys

try:
    # Load secrets
    secrets = toml.load('/var/www/vyud_app/.streamlit/secrets.toml')
    supabase = create_client(secrets['SUPABASE_URL'], secrets['SUPABASE_KEY'])
    
    # Read SQL file
    with open('/var/www/vyud_app/migrations/001_utm_events.sql', 'r') as f:
        sql = f.read()
    
    print("📊 Creating utm_events table in Supabase...")
    print("=" * 60)
    
    # Note: Supabase Python client doesn't support direct SQL execution
    # We need to use Supabase Dashboard SQL Editor or PostgREST RPC
    
    print("\n⚠️  MANUAL STEP REQUIRED:")
    print("Supabase Python client doesn't support direct SQL execution.")
    print("\nPlease execute the SQL manually:")
    print("1. Go to: https://vdduyndldbetdhwtilks.supabase.co/project/_/sql")
    print("2. Open SQL Editor")
    print("3. Copy and paste this SQL:\n")
    print("-" * 60)
    print(sql)
    print("-" * 60)
    print("\n4. Click 'Run'")
    print("\n✅ After execution, verify with:")
    print("   python3 -c \"from supabase import create_client; import toml; s=toml.load('.streamlit/secrets.toml'); sb=create_client(s['SUPABASE_URL'], s['SUPABASE_KEY']); print('✅ Table exists:', len(sb.table('utm_events').select('id').limit(1).execute().data) >= 0)\"")
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
