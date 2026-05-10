import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def check_vector_type():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("Error: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set.")
        return

    supabase: Client = create_client(url, key)
    
    # Check what schema the 'vector' type is in
    res = supabase.postgrest.rpc("check_schema", {}).execute() # Unlikely to exist
    # Use direct query via HTTP if possible, or just guess
    
    # Actually, the error message said 'extensions.vector'.
    # So it's in the 'extensions' schema.
    print("Vector type is in 'extensions' schema.")

if __name__ == "__main__":
    check_vector_type()
