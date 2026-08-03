from uuid import uuid4
from truebrief.ledger.database import get_supabase
from truebrief.auth.models import User

def get_or_create_user(auth_uid: str, email: str) -> User:
    db = get_supabase()

    # (a) Normal path — user already linked to this Supabase auth identity.
    res = db.table("users").select("*").eq("auth_uid", auth_uid).execute()
    if res.data:
        row = res.data[0]
        db.table("users").update({"last_seen_at": "now()"}).eq("id", row["id"]).execute()
        return User(**row)

    # (b) Adoption path — ONE-TIME Clerk→Supabase migration affordance. The pre-existing
    # account (created under Clerk auth) has a NULL auth_uid; if a row with a matching
    # email exists, adopt it by stamping in the new Supabase auth_uid instead of creating
    # a duplicate account and orphaning that user's topics. Safe to remove once every row
    # in `users` has a non-null auth_uid.
    adopt_res = (
        db.table("users")
        .select("*")
        .eq("email", email)
        .is_("auth_uid", "null")
        .execute()
    )
    if adopt_res.data:
        row = adopt_res.data[0]
        db.table("users").update({
            "auth_uid": auth_uid,
            "last_seen_at": "now()",
        }).eq("id", row["id"]).execute()
        row["auth_uid"] = auth_uid
        return User(**row)

    # (c) First login — create paired rows
    new_id = str(uuid4())
    db.table("users").insert({
        "id": new_id,
        "auth_uid": auth_uid,
        "email": email,
    }).execute()
    db.table("user_subscriptions").insert({
        "user_id": new_id,
        "tier": "free",
        "status": "active",
    }).execute()
    return User(id=new_id, auth_uid=auth_uid, email=email)
