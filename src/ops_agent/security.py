"""Controles de seguridad del agente, sin dependencias externas (OWASP Agentic Top 10 2026).

- validate_args: el modelo no puede inventar parámetros ni tipos (ASI02 Tool Misuse).
- check_server_tools: el servidor MCP expone exactamente lo que esperamos (ASI04 Supply Chain).
- AuditLog: traza append-only de cada decisión: qué pidió el agente y qué aprobó un humano (ASI09, ASI10).
"""
import json
import time
from pathlib import Path
from typing import Any

from ops_agent.tools import TOOL_SPECS

_JSON_TYPES: dict[str, tuple[type, ...]] = {"string": (str,), "number": (int, float), "integer": (int,), "boolean": (bool,)}
_SCHEMAS = {spec["function"]["name"]: spec["function"]["parameters"] for spec in TOOL_SPECS}
MAX_ARG_CHARS = 200


def validate_args(tool: str, args: Any) -> str | None:
    """Devuelve un motivo de rechazo o None si los argumentos cumplen el esquema declarado."""
    schema = _SCHEMAS.get(tool)
    if schema is None:
        return "herramienta no permitida"
    if not isinstance(args, dict):
        return "argumentos inválidos: se esperaba un objeto"
    props = schema["properties"]
    extra = set(args) - set(props)
    if extra:
        return f"argumentos inválidos: parámetros no declarados {sorted(extra)}"
    missing = [name for name in schema.get("required", []) if name not in args]
    if missing:
        return f"argumentos inválidos: faltan {missing}"
    for name, value in args.items():
        expected = _JSON_TYPES.get(props[name].get("type", ""), ())
        # bool es subclase de int en Python: no aceptarlo como número.
        if expected and (not isinstance(value, expected) or (isinstance(value, bool) and bool not in expected)):
            return f"argumentos inválidos: {name} debe ser {props[name]['type']}"
        if isinstance(value, str) and len(value) > MAX_ARG_CHARS:
            return f"argumentos inválidos: {name} supera {MAX_ARG_CHARS} caracteres"
    return None


def check_server_tools(served: dict[str, dict]) -> list[str]:
    """Compara las herramientas del servidor (nombre -> input_schema) con TOOL_SPECS."""
    problems = []
    for name in sorted(set(served) - set(_SCHEMAS)):
        problems.append(f"el servidor expone una herramienta no esperada: {name}")
    for name, schema in _SCHEMAS.items():
        if name not in served:
            problems.append(f"falta la herramienta {name} en el servidor")
            continue
        expected = set(schema.get("required", []))
        actual = set(served[name].get("required", []))
        if expected != actual:
            problems.append(f"{name}: parámetros requeridos {sorted(actual)} != esperados {sorted(expected)}")
    return problems


def _redact(args: dict) -> dict:
    return {k: (v[:MAX_ARG_CHARS] if isinstance(v, str) else v) for k, v in args.items()}


class AuditLog:
    """Registro append-only. En memoria para tests; en archivo JSONL para operación."""

    def __init__(self, path: str | Path | None = None, session: str = "local") -> None:
        self.path = Path(path) if path else None
        self.session = session
        self.events: list[dict] = []

    def record(self, decision: str, tool: str, args: dict | None = None, **details: Any) -> None:
        event = {"ts": time.time(), "session": self.session, "decision": decision, "tool": tool,
                 "args": _redact(args or {}), **details}
        self.events.append(event)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def decisions(self) -> list[tuple[str, str]]:
        return [(e["decision"], e["tool"]) for e in self.events]
