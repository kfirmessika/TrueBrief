"""
Tests for IC7 StateOfPlayGenerator (architecture §7.4).

The LLM call is mocked, so these are fast/deterministic. They lock in the
contract: valid statuses only, threads capped, situation+threads parsed,
graceful None on bad/empty input, and the runner's "regenerate only on
state_change" trigger logic.
"""

from truebrief.briefer.state_of_play import (
    StateOfPlayGenerator,
    VALID_STATUSES,
    MAX_THREADS,
)


class _FakeLLM:
    """Stand-in LLMClient that returns a canned string for `call`."""
    def __init__(self, response: str):
        self._response = response

    def call(self, **kwargs):
        return self._response


def _facts(n=3):
    return [
        {"alpha_text": f"Fact {i}", "event_class": "state_change",
         "event_date": "2026-06-17", "source_domain": "cnn.com"}
        for i in range(n)
    ]


def test_parses_situation_and_threads():
    raw = """{
      "situation": "Fragile US-Iran framework signed Jun 17.",
      "threads": [
        {"label": "US-Iran 60-day track", "status": "agreed", "note": "signed Jun 17"},
        {"label": "Strait of Hormuz", "status": "contested", "note": "conflicting claims"}
      ]
    }"""
    gen = StateOfPlayGenerator(llm_client=_FakeLLM(raw))
    block = gen.generate(_facts(), "Iran War")
    assert block is not None
    assert block["situation"].startswith("Fragile")
    assert len(block["threads"]) == 2
    assert block["threads"][0]["status"] == "agreed"
    assert "generated_at" in block


def test_drops_invalid_status_threads():
    raw = """{
      "situation": "x",
      "threads": [
        {"label": "good", "status": "escalating", "note": ""},
        {"label": "bad", "status": "totally-made-up", "note": ""},
        {"label": "nolabel", "status": "agreed", "note": ""}
      ]
    }"""
    gen = StateOfPlayGenerator(llm_client=_FakeLLM(raw))
    block = gen.generate(_facts(), "Iran War")
    labels = [t["label"] for t in block["threads"]]
    assert "good" in labels
    assert "bad" not in labels          # invalid status dropped
    assert all(t["status"] in VALID_STATUSES for t in block["threads"])


def test_threads_capped_at_max():
    threads = ",".join(
        f'{{"label": "t{i}", "status": "agreed", "note": ""}}' for i in range(MAX_THREADS + 4)
    )
    raw = f'{{"situation": "s", "threads": [{threads}]}}'
    gen = StateOfPlayGenerator(llm_client=_FakeLLM(raw))
    block = gen.generate(_facts(), "Iran War")
    assert len(block["threads"]) <= MAX_THREADS


def test_empty_facts_returns_none():
    gen = StateOfPlayGenerator(llm_client=_FakeLLM("{}"))
    assert gen.generate([], "Iran War") is None


def test_unparseable_output_returns_none():
    gen = StateOfPlayGenerator(llm_client=_FakeLLM("the model rambled with no json"))
    assert gen.generate(_facts(), "Iran War") is None


def test_block_with_no_situation_and_no_threads_returns_none():
    raw = '{"situation": "", "threads": []}'
    gen = StateOfPlayGenerator(llm_client=_FakeLLM(raw))
    assert gen.generate(_facts(), "Iran War") is None


def test_json_wrapped_in_fences_still_parses():
    raw = '```json\n{"situation": "ok", "threads": []}\n```'
    gen = StateOfPlayGenerator(llm_client=_FakeLLM(raw))
    block = gen.generate(_facts(), "Iran War")
    assert block is not None
    assert block["situation"] == "ok"


def test_llm_exception_returns_none():
    class _BoomLLM:
        def call(self, **kwargs):
            raise RuntimeError("quota exhausted")
    gen = StateOfPlayGenerator(llm_client=_BoomLLM())
    assert gen.generate(_facts(), "Iran War") is None
