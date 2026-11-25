"""Los spans siguen las convenciones GenAI de OpenTelemetry (nombres y atributos)."""
import asyncio

import pytest

sdk_trace = pytest.importorskip("opentelemetry.sdk.trace")
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter  # noqa: E402

from ops_agent import telemetry  # noqa: E402
from ops_agent.graph import build_graph  # noqa: E402
from ops_agent.order_agent import ORDER_AGENT  # noqa: E402
from ops_agent.planner import Final, ScriptedPlanner, ToolCall  # noqa: E402
from ops_agent.tools import LocalToolExecutor  # noqa: E402


@pytest.fixture
def spans():
    exporter = InMemorySpanExporter()
    provider = sdk_trace.TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return telemetry.get_tracer(provider), exporter


def test_tool_execution_span_follows_genai_conventions(spans):
    tracer, exporter = spans
    planner = ScriptedPlanner([ToolCall("call_1", "get_order", {"order_id": "A-1001"}), Final("ok")])
    graph = build_graph(planner, LocalToolExecutor(), ORDER_AGENT, tracer=tracer)

    with telemetry.invoke_agent(tracer):
        asyncio.run(graph.ainvoke({"messages": [{"role": "user", "content": "hola"}], "steps": 0},
                                  {"configurable": {"thread_id": "t"}}))

    by_name = {s.name: s for s in exporter.get_finished_spans()}
    tool = by_name["execute_tool get_order"]
    assert tool.attributes["gen_ai.operation.name"] == "execute_tool"
    assert tool.attributes["gen_ai.tool.name"] == "get_order"
    assert tool.attributes["gen_ai.tool.call.id"] == "call_1"
    agent = by_name["invoke_agent ops-agent"]
    assert agent.attributes["gen_ai.operation.name"] == "invoke_agent"


def test_tool_error_is_flagged_on_span(spans):
    tracer, exporter = spans
    planner = ScriptedPlanner([ToolCall("c1", "get_order", {"order_id": "NO-EXISTE"}), Final("ok")])
    graph = build_graph(planner, LocalToolExecutor(), ORDER_AGENT, tracer=tracer)

    asyncio.run(graph.ainvoke({"messages": [{"role": "user", "content": "hola"}], "steps": 0},
                              {"configurable": {"thread_id": "t"}}))

    (tool,) = [s for s in exporter.get_finished_spans() if s.name.startswith("execute_tool")]
    assert tool.attributes["error.type"] == "tool_error"


def test_without_tracer_everything_is_noop():
    with telemetry.execute_tool(None, "get_order") as span:
        span.set_attribute("x", 1)
