"""Sensores de arquitectura y de política del agente (sin red ni LLM)."""
import ast
from pathlib import Path

from ops_agent.tools import ALLOWED_TOOLS, NEEDS_APPROVAL

SRC = Path(__file__).resolve().parents[1] / "src" / "ops_agent"


def imported_modules(filename: str) -> set[str]:
    tree = ast.parse((SRC / filename).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_business_rules_are_framework_free():
    for module in ("orders.py", "security.py"):
        forbidden = {"openai", "langgraph", "mcp"} & imported_modules(module)
        assert not forbidden, (
            f"{module} importa {forbidden}: reglas de negocio y controles de seguridad deben ser Python puro, "
            "independientes del modelo y del transporte"
        )


def test_graph_does_not_call_providers_directly():
    forbidden = {"openai", "mcp", "orders"} & imported_modules("graph.py")
    assert not forbidden, (
        f"graph.py importa {forbidden}: el runtime no debe depender del proveedor, transporte ni dominio de pedidos"
    )


def test_runtime_contracts_and_agent_definition_are_domain_independent():
    forbidden_modules = {"openai", "langgraph", "mcp", "orders", "tools"}
    for module in ("agent_definition.py", "runtime_contracts.py"):
        forbidden = forbidden_modules & imported_modules(module)
        assert not forbidden, f"{module} importa {forbidden}: los contratos del runtime deben ser independientes"


def test_actions_with_side_effects_need_approval():
    assert "request_refund" in NEEDS_APPROVAL, "request_refund mueve dinero: debe pasar por interrupt()"
    assert NEEDS_APPROVAL <= ALLOWED_TOOLS, "toda herramienta con aprobación debe estar en TOOL_SPECS"


def test_mcp_server_matches_tool_specs():
    tree = ast.parse((SRC / "mcp_server.py").read_text(encoding="utf-8"))
    served = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "tool" for d in node.decorator_list)
    }
    assert served == ALLOWED_TOOLS, (
        f"mcp_server.py expone {sorted(served)} pero TOOL_SPECS declara {sorted(ALLOWED_TOOLS)}: actualizá ambos"
    )
