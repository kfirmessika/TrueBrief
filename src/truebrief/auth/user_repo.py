from uuid import uuid4
from truebrief.ledger.database import get_supabase
from truebrief.auth.models import User

def get_or_create_user(clerk_id: str, email: str) -> User:
    db = get_supabase()
    res = db.table("users").select("*").eq("clerk_id", clerk_id).execute()
    if res.data:
        row = res.data[0]
        db.table("users").update({"last_seen_at": "now()"}).eq("id", row["id"]).execute()
        return User(**row)

    # First login — create paired rows
    new_id = str(uuid4())
    db.table("users").insert({
        "id": new_id,
        "clerk_id": clerk_id,
        "email": email,
    }).execute()
    db.table("user_subscriptions").insert({
        "user_id": new_id,
        "tier": "free",
        "status": "active",
    }).execute()
    return User(id=new_id, clerk_id=clerk_id, email=email)
