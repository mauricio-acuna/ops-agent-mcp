"""Controles de seguridad puros: corren sin langgraph, sin red y sin LLM."""
import json

from ops_agent.security import AuditLog, check_server_tools, validate_args
from ops_agent.tools import TOOL_SPECS

VALID_REFUND = {"order_id": "A-1001", "amount": 20, "reason": "dañado"}


def test_valid_args_pass():
    assert validate_args("request_refund", VALID_REFUND, TOOL_SPECS) is None
    assert validate_args("get_order", {"order_id": "A-1001"}, TOOL_SPECS) is None


def test_unknown_tool_is_blocked():
    assert validate_args("delete_database", {}, TOOL_SPECS) == "herramienta no permitida"


def test_undeclared_parameter_is_blocked():
    problem = validate_args("request_refund", {**VALID_REFUND, "approved": True}, TOOL_SPECS)
    assert problem and "no declarados" in problem


def test_missing_and_wrong_types_are_blocked():
    assert "faltan" in validate_args("request_refund", {"order_id": "A-1001"}, TOOL_SPECS)
    assert "amount" in validate_args("request_refund", {**VALID_REFUND, "amount": "9999"}, TOOL_SPECS)
    assert "amount" in validate_args("request_refund", {**VALID_REFUND, "amount": True}, TOOL_SPECS)


def test_oversized_strings_are_blocked():
    assert "supera" in validate_args("request_refund", {**VALID_REFUND, "reason": "x" * 1000}, TOOL_SPECS)


def _served(specs=TOOL_SPECS):
    return {s["function"]["name"]: {"required": s["function"]["parameters"]["required"]} for s in specs}


def test_server_matching_specs_is_trusted():
    assert check_server_tools(_served(), TOOL_SPECS) == []


def test_server_with_extra_or_changed_tools_is_not_trusted():
    served = _served()
    served["exec_shell"] = {"required": ["cmd"]}
    served["request_refund"] = {"required": ["order_id"]}
    problems = check_server_tools(served, TOOL_SPECS)
    assert any("exec_shell" in p for p in problems)
    assert any("request_refund" in p for p in problems)


def test_audit_log_is_append_only_jsonl(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path, session="s1")
    log.record("blocked_by_policy", "delete_database", {}, reason="herramienta no permitida")
    log.record("executed", "get_order", {"order_id": "A-1001"}, ok=True)

    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [e["decision"] for e in lines] == ["blocked_by_policy", "executed"]
    assert all(e["session"] == "s1" for e in lines)


def test_audit_log_truncates_long_arguments():
    log = AuditLog()
    log.record("executed", "request_refund", {"reason": "x" * 5000})
    assert len(log.events[0]["args"]["reason"]) == 200
