"""
Tests — test_user_repo_cache.py

auth/user_repo caches the resolved User and throttles last_seen_at writes so a
single page load (6-8 API calls) no longer hits `users` 8 reads + 8 writes.
"""

from unittest.mock import MagicMock, patch

import pytest

from truebrief.auth import user_repo


class _FakeRedis:
    def __init__(self):
        self.kv: dict[str, str] = {}

    def get(self, k):
        return self.kv.get(k)

    def setex(self, k, ttl, v):
        self.kv[k] = v

    def set(self, k, v, nx=False, ex=None):
        if nx and k in self.kv:
            return False
        self.kv[k] = v
        return True

    def delete(self, *ks):
        for k in ks:
            self.kv.pop(k, None)


@pytest.fixture
def fake_redis(monkeypatch):
    r = _FakeRedis()
    monkeypatch.setattr(user_repo, "_redis", lambda: r)
    return r


def _db_existing_user():
    db = MagicMock()
    row = {"id": "u1", "auth_uid": "auth_1", "email": "a@b.com"}
    db.table().select().eq().execute.return_value = MagicMock(data=[row])
    return db


def test_second_call_served_from_cache_no_select(fake_redis):
    db = _db_existing_user()
    with patch.object(user_repo, "get_supabase", return_value=db):
        u1 = user_repo.get_or_create_user("auth_1", "a@b.com")
        select_calls_after_first = db.table().select.call_count
        u2 = user_repo.get_or_create_user("auth_1", "a@b.com")

    assert u1.id == u2.id == "u1"
    # no new .select() chain built on the cached call
    assert db.table().select.call_count == select_calls_after_first


def test_last_seen_stamped_once_per_window(fake_redis):
    db = _db_existing_user()
    with patch.object(user_repo, "get_supabase", return_value=db):
        for _ in range(5):
            user_repo.get_or_create_user("auth_1", "a@b.com")

    update_calls = [c for c in db.table().update.call_args_list
                    if c.args and "last_seen_at" in c.args[0]]
    assert len(update_calls) == 1


def test_invalidate_clears_cache(fake_redis):
    db = _db_existing_user()
    with patch.object(user_repo, "get_supabase", return_value=db):
        user_repo.get_or_create_user("auth_1", "a@b.com")
        user_repo.invalidate_user_cache("auth_1")
        n_before = db.table().select.call_count
        user_repo.get_or_create_user("auth_1", "a@b.com")

    assert db.table().select.call_count > n_before  # hit the DB again


def test_no_redis_keeps_old_behaviour(monkeypatch):
    monkeypatch.setattr(user_repo, "_redis", lambda: None)
    db = _db_existing_user()
    with patch.object(user_repo, "get_supabase", return_value=db):
        user_repo.get_or_create_user("auth_1", "a@b.com")
        user_repo.get_or_create_user("auth_1", "a@b.com")

    # every call stamps last_seen_at when there's no Redis to throttle
    update_calls = [c for c in db.table().update.call_args_list
                    if c.args and "last_seen_at" in c.args[0]]
    assert len(update_calls) == 2
