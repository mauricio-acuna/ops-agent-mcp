"""Lógica de negocio de pedidos (datos ficticios). No depende de MCP ni de LLMs: se testea directo."""
from dataclasses import dataclass, field


@dataclass
class Order:
    order_id: str
    customer_id: str
    total: float
    status: str  # PENDING | SHIPPED | DELIVERED | CANCELLED
    refunded: float = 0.0
    items: list[str] = field(default_factory=list)


class OrderStore:
    def __init__(self) -> None:
        self._orders: dict[str, Order] = {
            "A-1001": Order("A-1001", "C-1", 120.0, "DELIVERED", items=["auriculares"]),
            "A-1002": Order("A-1002", "C-1", 45.5, "SHIPPED", items=["funda"]),
            "A-1003": Order("A-1003", "C-2", 899.0, "DELIVERED", items=["monitor"]),
        }

    def get(self, order_id: str) -> dict:
        order = self._orders.get(order_id)
        if order is None:
            return {"error": f"pedido {order_id} no existe"}
        return order.__dict__.copy()

    def by_customer(self, customer_id: str) -> list[dict]:
        return [o.__dict__.copy() for o in self._orders.values() if o.customer_id == customer_id]

    def refund(self, order_id: str, amount: float, reason: str) -> dict:
        order = self._orders.get(order_id)
        if order is None:
            return {"ok": False, "error": f"pedido {order_id} no existe"}
        if order.status != "DELIVERED":
            return {"ok": False, "error": "solo se reembolsan pedidos entregados"}
        if amount <= 0 or order.refunded + amount > order.total:
            return {"ok": False, "error": "monto inválido o superior al total del pedido"}
        order.refunded += amount
        return {"ok": True, "order_id": order_id, "refunded_total": order.refunded, "reason": reason[:200]}
