from typing import List, TypedDict


class InvestigationStep(TypedDict):
    id: int
    description: str
    status: str
    result_summary: str


# 旧别名，保留一版以便 Phase 1 骨架代码平滑迁移到调查语义
PlanStep = InvestigationStep


class AgentState(TypedDict, total=False):
    # 案件线索 {alert_id, subject_account, alert_type, window}
    case: dict
    # 案件上下文：机构类型 / 适用辖区 / 可用数据源 / 规则库版本
    case_context: str
    memory_context: str
    plan: List[InvestigationStep]
    current_step_id: int
    executor_messages: list
    # 证据链 {id, tool, args, digest, timestamp}，报告引用的锚点
    evidence: list
    # 规则引擎命中 {rule_id, name, level, citation, matched}
    rule_hits: list
    verdict: dict
    # 结构化研判报告与合规审查意见
    report: dict
    consecutive_failures: int
    replan_count: int
    step_count: int

    # 旧字段，保留一版以便平滑迁移（Executor / Verifier prompt 领域化归 2.3）
    goal: str
    system_info: str


def apply_plan_patch(plan: List[InvestigationStep], patch: List[dict]) -> List[InvestigationStep]:
    """Apply a list of add/update/delete operations to a plan and return a new plan.

    Patch operations:
    - {"op": "add", "step": InvestigationStep}
    - {"op": "update", "id": int, ...fields to overwrite}
    - {"op": "delete", "id": int}

    The input plan is never mutated; a new list is returned.
    """
    result = [dict(step) for step in plan]
    index_by_id = {step["id"]: i for i, step in enumerate(result)}

    for operation in patch:
        op = operation.get("op")

        if op == "add":
            step = operation["step"]
            step_id = step["id"]
            if step_id in index_by_id:
                raise ValueError(f"duplicate step id: {step_id}")
            index_by_id[step_id] = len(result)
            result.append(dict(step))

        elif op == "update":
            step_id = operation["id"]
            if step_id not in index_by_id:
                raise ValueError(f"step id out of range: {step_id}")
            i = index_by_id[step_id]
            fields = {k: v for k, v in operation.items() if k not in ("op", "id")}
            result[i].update(fields)

        elif op == "delete":
            step_id = operation["id"]
            if step_id not in index_by_id:
                raise ValueError(f"step id out of range: {step_id}")
            i = index_by_id[step_id]
            result.pop(i)
            index_by_id = {step["id"]: j for j, step in enumerate(result)}

        else:
            raise ValueError(f"unknown patch op: {op}")

    return result
