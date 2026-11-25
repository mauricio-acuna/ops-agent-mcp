"""Grafo del agente: plan → (aprobación humana) → ejecutar → plan ... hasta respuesta final o límite de pasos."""
import json
import operator
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from ops_agent import telemetry
from ops_agent.planner import Final, Planner, ToolCall
from ops_agent.security import AuditLog, validate_args
from ops_agent.tools import NEEDS_APPROVAL, ToolExecutor, to_tool_message

MAX_STEPS = 6


class AgentState(TypedDict, total=False):
    messages: Annotated[list[dict], operator.add]
    pending: dict | None
    approved: bool
    steps: int
    final: str


def build_graph(planner: Planner, executor: ToolExecutor, checkpointer=None,
                audit: AuditLog | None = None, tracer=None):
    audit = audit if audit is not None else AuditLog()

    def plan(state: AgentState) -> dict[str, Any]:
        if state.get("steps", 0) >= MAX_STEPS:
            return {"final": "No pude completar la tarea dentro del límite de pasos.", "pending": None}
        action = planner.next_action(state["messages"])
        if isinstance(action, Final):
            return {"final": action.text, "pending": None}
        assert isinstance(action, ToolCall)
        assistant_msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": action.id,
                "type": "function",
                "function": {"name": action.name, "arguments": json.dumps(action.args)},
            }],
        }
        return {"messages": [assistant_msg], "pending": {
            "id": action.id, "name": action.name, "args": action.args,
            "problem": validate_args(action.name, action.args),
        }}

    def route_after_plan(state: AgentState) -> str:
        pending = state.get("pending")
        if not pending:
            return END
        if pending.get("problem"):
            return "reject"
        return "approval" if pending["name"] in NEEDS_APPROVAL else "execute"

    def approval(state: AgentState) -> dict[str, Any]:
        pending = state["pending"]
        # Pausa el grafo; se reanuda con Command(resume="approve" | "reject").
        decision = interrupt({"tool": pending["name"], "args": pending["args"]})
        approved = decision == "approve"
        audit.record("approved_by_human" if approved else "rejected_by_human", pending["name"], pending["args"])
        return {"approved": approved}

    def route_after_approval(state: AgentState) -> str:
        return "execute" if state.get("approved") else "reject"

    async def execute(state: AgentState) -> dict[str, Any]:
        pending = state["pending"]
        with telemetry.execute_tool(tracer, pending["name"], pending["id"]) as span:
            result = await executor.call(pending["name"], pending["args"])
            ok = result.get("ok", "error" not in result)
            if not ok:
                span.set_attribute("error.type", "tool_error")
        audit.record("executed", pending["name"], pending["args"], ok=ok)
        return {
            "messages": [to_tool_message(pending["id"], result)],
            "pending": None,
            "approved": False,
            "steps": state.get("steps", 0) + 1,
        }

    def reject(state: AgentState) -> dict[str, Any]:
        pending = state["pending"]
        problem = pending.get("problem")
        if problem:
            audit.record("blocked_by_policy", pending["name"], pending["args"] if isinstance(pending["args"], dict) else {},
                         reason=problem)
        reason = f"acción rechazada: {problem}" if problem else "acción rechazada por el operador"
        result = {"ok": False, "error": reason}
        return {
            "messages": [to_tool_message(pending["id"], result)],
            "pending": None,
            "steps": state.get("steps", 0) + 1,
        }

    g = StateGraph(AgentState)
    g.add_node("plan", plan)
    g.add_node("approval", approval)
    g.add_node("execute", execute)
    g.add_node("reject", reject)
    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", route_after_plan, ["approval", "execute", "reject", END])
    g.add_conditional_edges("approval", route_after_approval, ["execute", "reject"])
    g.add_edge("execute", "plan")
    g.add_edge("reject", "plan")
    return g.compile(checkpointer=checkpointer or InMemorySaver())
