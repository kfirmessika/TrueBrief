"""
Tests — test_retention_task.py

tasks/retention_task.prune_telemetry_task: calls the two prune RPCs with the
configured retention windows, reports the counts, and never raises even when an
RPC is missing.
"""

from unittest.mock import MagicMock, patch

from config.settings import settings
from truebrief.tasks import retention_task


def _db(rpc_return=5, raise_on=None):
    db = MagicMock()

    def rpc(name, params):
        chain = MagicMock()
        if raise_on and name == raise_on:
            chain.execute.side_effect = RuntimeError("PGRST202 function not found")
        else:
            chain.execute.return_value = MagicMock(data=rpc_return)
        rpc.calls.append((name, params))
        return chain

    rpc.calls = []
    db.rpc.side_effect = rpc
    return db, rpc


def test_prunes_with_configured_windows(monkeypatch):
    monkeypatch.setattr(settings, "TELEMETRY_PAYLOAD_RETENTION_DAYS", 30)
    monkeypatch.setattr(settings, "PIPELINE_TRACE_RETENTION_DAYS", 7)
    db, rpc = _db(rpc_return=12)
    with patch("truebrief.ledger.database.get_supabase", return_value=db):
        out = retention_task.prune_telemetry_task()

    assert ("prune_llm_call_payloads", {"days_to_keep": 30}) in rpc.calls
    assert ("prune_pipeline_trace", {"days_to_keep": 7}) in rpc.calls
    assert out["llm_payloads_pruned"] == 12
    assert out["trace_rows_deleted"] == 12
    assert out["errors"] == []


def test_never_raises_when_rpc_missing(monkeypatch):
    db, _ = _db(raise_on="prune_llm_call_payloads")
    with patch("truebrief.ledger.database.get_supabase", return_value=db):
        out = retention_task.prune_telemetry_task()

    assert out["llm_payloads_pruned"] == 0
    assert any("llm_payloads" in e for e in out["errors"])
    # the second prune still ran
    assert out["trace_rows_deleted"] == 5
