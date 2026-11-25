"""Catálogo de herramientas, política de aprobación y ejecutores (MCP remoto o local)."""
from copy import deepcopy
from typing import Any

from ops_agent.orders import OrderStore
from ops_agent.runtime_contracts import ToolExecutor, to_tool_message

# Esquemas en formato de function calling de OpenAI; deben coincidir con mcp_server.py.
TOOL_SPECS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "Devuelve el detalle de un pedido por su ID (ej. A-1001).",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_customer_orders",
            "description": "Lista los pedidos de un cliente por su ID (ej. C-1).",
            "parameters": {
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_refund",
            "description": "Registra un reembolso de un pedido entregado. Requiere aprobación humana.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "amount": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["order_id", "amount", "reason"],
                "additionalProperties": False,
            },
        },
    },
]

ALLOWED_TOOLS = {spec["function"]["name"] for spec in TOOL_SPECS}
NEEDS_APPROVAL = {"request_refund"}


class LocalToolExecutor:
    """Ejecuta contra OrderStore en memoria: útil para tests y demos sin servidor."""

    def __init__(self, store: OrderStore | None = None) -> None:
        self.store = store or OrderStore()

    async def call(self, name: str, args: dict[str, Any]) -> dict:
        if name == "get_order":
            return self.store.get(str(args["order_id"]))
        if name == "list_customer_orders":
            return {"orders": self.store.by_customer(str(args["customer_id"]))}
        if name == "request_refund":
            return self.store.refund(str(args["order_id"]), float(args["amount"]), str(args["reason"]))
        raise ValueError(f"herramienta no permitida: {name}")


class McpToolExecutor:
    """Llama a las herramientas en un servidor MCP remoto (Streamable HTTP).

    Las descripciones que ve el modelo salen del manifiesto local del agente, nunca del servidor:
    un servidor comprometido no puede inyectar instrucciones vía descripciones de herramientas.
    """

    def __init__(self, url: str, tool_specs: tuple[dict, ...] | None = None) -> None:
        self.url = url
        self.tool_specs = deepcopy(tuple(tool_specs) if tool_specs is not None else tuple(TOOL_SPECS))
        self._verified = False

    async def call(self, name: str, args: dict[str, Any]) -> dict:
        from mcp import Client  # import diferido: los tests no necesitan red

        from ops_agent.security import check_server_tools

        async with Client(self.url) as client:
            if not self._verified:
                listed = await client.list_tools()
                problems = check_server_tools({t.name: t.input_schema for t in listed.tools}, self.tool_specs)
                if problems:
                    raise RuntimeError("servidor MCP no confiable: " + "; ".join(problems))
                self._verified = True
            result = await client.call_tool(name, args)
            if result.is_error:
                return {"ok": False, "error": "la herramienta devolvió un error"}
            return result.structured_content or {"ok": False, "error": "respuesta sin contenido estructurado"}
