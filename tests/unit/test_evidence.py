import pytest

from core.evidence import append_evidence, check_closure, resolve_refs


def test_append_evidence_assigns_monotonic_ids():
    state = {}
    e1 = append_evidence(state, "query_transactions", {"account": "A"}, {"count": 10})
    e2 = append_evidence(state, "screen_watchlist", {"name": "B"}, "no hit")
    e3 = append_evidence(state, "query_account_profile", {"account": "A"}, {"scope": "retail"})

    assert [e1["id"], e2["id"], e3["id"]] == ["E-001", "E-002", "E-003"]
    assert [e["id"] for e in state["evidence"]] == ["E-001", "E-002", "E-003"]


def test_append_evidence_ids_never_repeat_after_existing_entries():
    state = {"evidence": [{"id": "E-007", "tool": "x", "args": {}, "digest": ""}]}
    entry = append_evidence(state, "query_transactions", {}, "ok")

    assert entry["id"] == "E-008"
    ids = [e["id"] for e in state["evidence"]]
    assert len(ids) == len(set(ids))


def test_append_evidence_records_digest_and_timestamp():
    state = {}
    entry = append_evidence(state, "t", {"k": "v"}, {"b": 2, "a": 1})

    assert entry["tool"] == "t"
    assert entry["args"] == {"k": "v"}
    assert entry["digest"] == '{"a": 1, "b": 2}'
    assert "T" in entry["timestamp"]


def test_append_evidence_truncates_large_result():
    state = {}
    entry = append_evidence(state, "t", {}, "x" * 5000)
    assert entry["digest"].endswith("...(truncated)")
    assert len(entry["digest"]) < 5000


def test_resolve_refs_splits_resolved_and_missing():
    evidence = [
        {"id": "E-001", "tool": "a"},
        {"id": "E-002", "tool": "b"},
    ]
    out = resolve_refs(evidence, ["E-001", "E-999", "E-002", "E-999"])

    assert out["resolved"] == {"E-001": evidence[0], "E-002": evidence[1]}
    assert out["missing"] == ["E-999"]


def test_check_closure_passes_when_all_refs_exist():
    evidence = [{"id": "E-001"}, {"id": "E-002"}]
    report = {"findings": [{"statement": "s1", "evidence_refs": ["E-001"]},
                           {"statement": "s2", "evidence_refs": ["E-001", "E-002"]}]}

    result = check_closure(report, evidence)

    assert result["ok"] is True
    assert result["failures"] == []


def test_check_closure_reports_missing_ref_with_detail():
    evidence = [{"id": "E-001"}]
    report = {"findings": [{"statement": "claims B on sanctions", "evidence_refs": ["E-001", "E-042"]}]}

    result = check_closure(report, evidence)

    assert result["ok"] is False
    assert len(result["failures"]) == 1
    failure = result["failures"][0]
    assert failure["finding_index"] == 0
    assert failure["missing_refs"] == ["E-042"]


def test_check_closure_rejects_finding_without_refs():
    evidence = [{"id": "E-001"}]
    report = {"findings": [{"statement": "unsupported claim", "evidence_refs": []}]}

    result = check_closure(report, evidence)

    assert result["ok"] is False
    assert result["failures"][0]["missing_refs"] == []
