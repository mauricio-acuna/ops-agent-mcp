import asyncio
import json

from langgraph.types import Command

from ops_agent.graph import MAX_STEPS, build_graph
from ops_agent.orders import OrderStore
from ops_agent.planner import Final, ScriptedPlanner, ToolCall
from ops_agent.tools import LocalToolExecutor


def run(coro):
    return asyncio.run(coro)


def start(graph, question="hola", thread="t1"):
    config = {"configurable": {"thread_id": thread}}
    result = run(graph.ainvoke({"messages": [{"role": "user", "content": question}], "steps": 0}, config))
    return result, config


def test_consulta_de_solo_lectura_no_pide_aprobacion():
    planner = ScriptedPlanner([ToolCall("c1", "get_order", {"order_id": "A-1001"}), Final("Tu pedido fue entregado.")])
    graph = build_graph(planner, LocalToolExecutor())

    result, _ = start(graph)

    assert "__interrupt__" not in result
    assert result["final"] == "Tu pedido fue entregado."
    tool_msg = json.loads(result["messages"][-1]["content"])
    assert tool_msg["status"] == "DELIVERED"


def test_reembolso_se_pausa_y_se_ejecuta_al_aprobar():
    store = OrderStore()
    planner = ScriptedPlanner([
        ToolCall("c1", "request_refund", {"order_id": "A-1001", "amount": 20, "reason": "producto dañado"}),
        Final("Reembolso registrado."),
    ])
    graph = build_graph(planner, LocalToolExecutor(store))

    result, config = start(graph)
    assert result["__interrupt__"][0].value["tool"] == "request_refund"
    assert store.get("A-1001")["refunded"] == 0.0  # nada se ejecutó todavía

    result = run(graph.ainvoke(Command(resume="approve"), config))
    assert result["final"] == "Reembolso registrado."
    assert store.get("A-1001")["refunded"] == 20.0


def test_reembolso_rechazado_no_se_ejecuta():
    store = OrderStore()
    planner = ScriptedPlanner([
        ToolCall("c1", "request_refund", {"order_id": "A-1001", "amount": 20, "reason": "x"}),
        Final("No se realizó el reembolso."),
    ])
    graph = build_graph(planner, LocalToolExecutor(store))

    _, config = start(graph)
    result = run(graph.ainvoke(Command(resume="reject"), config))

    assert store.get("A-1001")["refunded"] == 0.0
    assert "rechazada" in result["messages"][-1]["content"]


def test_herramienta_no_permitida_se_rechaza_sin_ejecutar():
    planner = ScriptedPlanner([ToolCall("c1", "delete_database", {}), Final("ok")])
    graph = build_graph(planner, LocalToolExecutor())

    result, _ = start(graph)

    assert "no permitida" in result["messages"][-1]["content"]


def test_limite_de_pasos():
    planner = ScriptedPlanner([ToolCall(f"c{i}", "get_order", {"order_id": "A-1001"}) for i in range(20)])
    graph = build_graph(planner, LocalToolExecutor())

    result, _ = start(graph)

    assert "límite de pasos" in result["final"]
    assert result["steps"] == MAX_STEPS


def test_reglas_de_negocio_del_reembolso():
    store = OrderStore()
    assert store.refund("A-1002", 10, "x")["ok"] is False      # no entregado
    assert store.refund("A-1001", 500, "x")["ok"] is False     # supera el total
    assert store.refund("A-1001", 120, "x")["ok"] is True
