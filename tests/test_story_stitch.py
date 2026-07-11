"""
Story stitch parsing regression tests (2026-07-10).

Root cause of "No connectors generated": Groq's json_object response format
forces a top-level JSON OBJECT, but the legacy prompt demanded a bare array —
so the model always returned {"connectors": [...]} (or similar), the endpoint's
isinstance(list) check failed, and every story request came back empty.

_parse_story_connectors must accept the object form, the bare-array form,
and degrade to padded-empty on garbage.
"""
from __future__ import annotations

import json

import pytest

from truebrief.api.routes import _parse_story_connectors


def test_parses_connectors_object():
    raw = json.dumps({"connectors": ["A led to B.", "B triggered C."]})
    assert _parse_story_connectors(raw, 2) == ["A led to B.", "B triggered C."]


def test_parses_bare_array():
    raw = json.dumps(["A led to B.", "B triggered C."])
    assert _parse_story_connectors(raw, 2) == ["A led to B.", "B triggered C."]


def test_parses_alt_keys():
    assert _parse_story_connectors(json.dumps({"bridges": ["x"]}), 1) == ["x"]
    assert _parse_story_connectors(json.dumps({"passages": ["y"]}), 1) == ["y"]


def test_pads_short_output_to_n_pairs():
    raw = json.dumps({"connectors": ["only one"]})
    assert _parse_story_connectors(raw, 3) == ["only one", "", ""]


def test_truncates_long_output_to_n_pairs():
    raw = json.dumps({"connectors": ["a", "b", "c", "d"]})
    assert _parse_story_connectors(raw, 2) == ["a", "b"]


def test_unparseable_shapes_return_padded_empty():
    assert _parse_story_connectors(json.dumps({"error": "no facts"}), 2) == ["", ""]
    assert _parse_story_connectors(json.dumps("just a string"), 2) == ["", ""]
    assert _parse_story_connectors(json.dumps({"connectors": "not-a-list"}), 2) == ["", ""]


def test_invalid_json_raises_for_caller_to_catch():
    with pytest.raises(json.JSONDecodeError):
        _parse_story_connectors("not json at all", 2)


def test_strips_and_drops_empty_entries():
    raw = json.dumps({"connectors": ["  padded  ", "", None, "ok"]})
    assert _parse_story_connectors(raw, 3) == ["padded", "ok", ""]
