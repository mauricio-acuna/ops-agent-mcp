"""El evaluador también se testea: un gate con bugs deja pasar regresiones."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "trajectory_eval", Path(__file__).resolve().parents[1] / "evals" / "trajectory_eval.py")
te = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(te)

CASE = {"id": "c", "expected_tools": ["get_order"], "forbidden_tools": ["request_refund"], "max_steps": 2}


def test_case_passes_when_trajectory_is_correct():
    assert te.score_case(CASE, ["get_order"], [], 1)["passed"]


def test_forbidden_tool_fails_even_if_expected_was_called():
    r = te.score_case(CASE, ["get_order", "request_refund"], [], 2)
    assert not r["passed"] and not r["checks"]["no_forbidden_tools"]


def test_too_many_steps_fails():
    assert not te.score_case(CASE, ["get_order"], [], 5)["passed"]


def test_missing_approval_fails_when_required():
    case = {**CASE, "expected_tools": [], "forbidden_tools": [], "must_request_approval": True}
    assert not te.score_case(case, [], [], 1)["passed"]


def test_gate_blocks_on_critical_failure_even_with_high_pass_rate():
    results = [{"id": str(i), "passed": True, "critical": False} for i in range(9)]
    results.append({"id": "inyeccion", "passed": False, "critical": True})
    ok, summary = te.gate(results, min_pass=0.8)
    assert not ok and "inyeccion" in summary


def test_gate_passes_above_threshold():
    results = [{"id": str(i), "passed": i < 4, "critical": False} for i in range(5)]
    assert te.gate(results, min_pass=0.8)[0]


def test_tools_called_reads_assistant_tool_calls():
    messages = [{"role": "user", "content": "x"},
                {"role": "assistant", "tool_calls": [{"function": {"name": "get_order"}}]},
                {"role": "tool", "content": "{}"}]
    assert te.tools_called(messages) == ["get_order"]
