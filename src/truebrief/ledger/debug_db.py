from truebrief.ledger.database import get_supabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug():
    db = get_supabase()
    tables = ["users", "topics", "known_facts", "briefs"]
    
    for table in tables:
        try:
            res = db.table(table).select("count", count="exact").execute()
            print(f"Table '{table}': EXISTS (count: {res.count})")
        except Exception as e:
            print(f"Table '{table}': ERROR - {e}")

    # Check RPC
    try:
        # Dummy call to match_facts
        db.rpc("match_facts", {"query_embedding": [0.1]*768, "match_threshold": 0.5, "match_count": 1}).execute()
        print("RPC 'match_facts': EXISTS")
    except Exception as e:
        print(f"RPC 'match_facts': ERROR - {e}")

if __name__ == "__main__":
    debug()
