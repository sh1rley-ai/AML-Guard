"""证据链记录与引用解析。

证据链是报告结论的唯一真相源：Executor / Verifier 每次工具调用都追加一条带 id
的记录，报告中的每条结论通过 evidence_refs 引用这些 id。校验的本质就是检查
"结论 -> evidence 引用" 这条链是否闭合。
"""

import json
from datetime import datetime, timezone
from typing import Any

_MAX_DIGEST_CHARS = 2000


def _digest(result: Any) -> str:
    """把工具返回压成可读摘要，避免把上千条原始明细灌进上下文。"""
    if isinstance(result, str):
        text = result
    else:
        try:
            text = json.dumps(result, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            text = repr(result)
    if len(text) > _MAX_DIGEST_CHARS:
        return text[:_MAX_DIGEST_CHARS] + "...(truncated)"
    return text


def _next_evidence_id(evidence: list) -> str:
    max_seq = 0
    for entry in evidence:
        raw = str(entry.get("id", ""))
        if raw.startswith("E-"):
            try:
                max_seq = max(max_seq, int(raw[2:]))
            except ValueError:
                continue
    return f"E-{max_seq + 1:03d}"


def append_evidence(state: dict, tool: str, args: dict, result: Any) -> dict:
    """向 state["evidence"] 追加一条证据记录，分配单调递增的 E-XXX id。

    直接就地修改 state（与 LangGraph 节点内的状态更新一致）并返回新增的记录。
    """
    evidence = state.get("evidence")
    if evidence is None:
        evidence = []
        state["evidence"] = evidence

    entry = {
        "id": _next_evidence_id(evidence),
        "tool": tool,
        "args": args,
        "digest": _digest(result),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    evidence.append(entry)
    return entry


def resolve_refs(evidence: list, refs: list) -> dict:
    """把一组 evidence id 解析为对应记录。

    返回 {"resolved": {id: entry}, "missing": [id, ...]}，missing 保持输入顺序且去重。
    """
    by_id = {entry.get("id"): entry for entry in evidence}
    resolved: dict = {}
    missing: list = []
    for ref in refs:
        if ref in by_id:
            resolved[ref] = by_id[ref]
        elif ref not in missing:
            missing.append(ref)
    return {"resolved": resolved, "missing": missing}


def check_closure(report: dict, evidence: list) -> dict:
    """校验报告中每条 finding 的 evidence_refs 是否都能在证据链中找到。

    返回 {"ok": bool, "failures": [{"finding_index", "finding", "missing_refs"}, ...]}。
    finding 缺失 evidence_refs（空或不存在）同样视为不闭合。
    """
    by_id = {entry.get("id") for entry in evidence}
    findings = report.get("findings", []) if isinstance(report, dict) else []
    failures: list = []

    for index, finding in enumerate(findings):
        refs = finding.get("evidence_refs") or []
        if not refs:
            failures.append(
                {
                    "finding_index": index,
                    "finding": finding.get("statement", finding),
                    "missing_refs": [],
                    "reason": "finding 未提供 evidence_refs",
                }
            )
            continue
        missing = [ref for ref in refs if ref not in by_id]
        if missing:
            failures.append(
                {
                    "finding_index": index,
                    "finding": finding.get("statement", finding),
                    "missing_refs": missing,
                    "reason": "引用的证据 id 不存在",
                }
            )

    return {"ok": not failures, "failures": failures}
