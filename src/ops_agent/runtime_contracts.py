"""Contratos del runtime que no dependen de un dominio ni de un proveedor."""
import json
from typing import Any, Protocol


class ToolExecutor(Protocol):
    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]: ...


def to_tool_message(call_id: str, result: dict[str, Any]) -> dict[str, str]:
    return {"role": "tool", "tool_call_id": call_id, "content": json.dumps(result, ensure_ascii=False)}
