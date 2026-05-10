import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def apply_schema():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") # Need service role for DDL
    
    if not url or not key:
        print("Error: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set.")
        return

    supabase: Client = create_client(url, key)
    
    with open("src/truebrief/ledger/schema.sql", "r") as f:
        sql = f.read()

    # Split by semicolons for a rough multi-statement execution
    # Note: This is fragile for complex SQL with nested blocks, but good for simple DDL.
    # Actually, Supabase Python client doesn't have a direct 'execute_sql' method.
    # It usually goes through RPC or Postgrest.
    # However, we can use the 'postgres' connection if we had the password.
    
    # Alternatively, we can use a small RPC if it exists.
    # Since we can't easily run raw SQL DDL through the Postgrest client, 
    # we'll tell the user to run it in the Supabase Dashboard.
    
    print("--- SCHEMA TO APPLY ---")
    print("Please run the content of 'src/truebrief/ledger/schema.sql' in your Supabase SQL Editor.")
    print("Specifically, ensure 'match_facts' has the correct search_path.")

if __name__ == "__main__":
    apply_schema()
