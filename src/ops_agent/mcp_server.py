"""Servidor MCP que expone las operaciones de pedidos (SDK oficial de MCP v2).

Probar con el inspector:      uv run mcp dev src/ops_agent/mcp_server.py
Servir por HTTP:              uv run mcp run src/ops_agent/mcp_server.py --transport streamable-http
"""
from mcp.server import MCPServer

from ops_agent.orders import OrderStore

mcp = MCPServer("pedidos")
store = OrderStore()


@mcp.tool()
def get_order(order_id: str) -> dict:
    """Devuelve el detalle de un pedido por su ID (ej. A-1001)."""
    return store.get(order_id)


@mcp.tool()
def list_customer_orders(customer_id: str) -> dict:
    """Lista los pedidos de un cliente por su ID (ej. C-1)."""
    return {"orders": store.by_customer(customer_id)}


@mcp.tool()
def request_refund(order_id: str, amount: float, reason: str) -> dict:
    """Registra un reembolso parcial o total de un pedido ENTREGADO. Acción con efecto: requiere aprobación humana."""
    return store.refund(order_id, amount, reason)
