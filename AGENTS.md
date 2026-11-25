# AGENTS.md — ops-agent-mcp

Mapa para agentes de código (Copilot, Codex, Claude Code…). Es corto a propósito: indica dónde buscar, no repite el código.

## Qué es
Agente LangGraph que consulta pedidos y gestiona reembolsos vía MCP, con aprobación humana. Detalle en [README.md](README.md).

## Comandos
| Para | Comando |
|---|---|
| Verificar (obligatorio antes de terminar) | `pytest -q` |
| Evals de trayectoria con el modelo real (requiere API key) | `python evals/trajectory_eval.py --min-pass 0.8` |
| Inspeccionar el servidor MCP | `mcp dev src/ops_agent/mcp_server.py` |

## Mapa del código (`src/ops_agent/`)
- `orders.py` — `OrderStore` y reglas de reembolso (Python puro).
- `tools.py` — `TOOL_SPECS`, `ALLOWED_TOOLS`, `NEEDS_APPROVAL`, ejecutores local y MCP (verifica el servidor antes de usarlo).
- `security.py` — `validate_args`, `check_server_tools`, `AuditLog` (Python puro).
- `telemetry.py` — spans `invoke_agent` / `chat` / `execute_tool` con atributos `gen_ai.*` (no-op sin OpenTelemetry).
- `planner.py` — interfaz `Planner`: `OpenAIPlanner` y `ScriptedPlanner` (tests).
- `graph.py` — grafo plan → approval (`interrupt`) → execute/reject, `MAX_STEPS`.
- `mcp_server.py` — servidor MCP "pedidos".
- `evals/` — casos de trayectoria (incluye inyección indirecta) y gate.

## Invariantes (cada una tiene un sensor)
| Regla | Sensor |
|---|---|
| `orders.py` y `security.py` no importan openai, langgraph ni mcp | `test_architecture.py` |
| `graph.py` no llama proveedores directamente | `test_architecture.py` |
| `request_refund` requiere aprobación humana | `test_architecture.py`, `test_graph.py` |
| Herramientas de `mcp_server.py` == `TOOL_SPECS` | `test_architecture.py` |
| Argumentos fuera del esquema se bloquean antes de aprobar o ejecutar | `test_policy.py`, `test_security.py` |
| Un agente engañado no mueve dinero sin humano ni por encima del total | `test_security.py` |
| Cada decisión queda en el `AuditLog` | `test_security.py` |
| Spans con nombres y atributos `gen_ai.*`, sin contenido | `test_telemetry.py` |
| El grafo se detiene en `MAX_STEPS` | `test_graph.py` |
| El modelo real no llama herramientas prohibidas (incluida inyección) | `evals/` + workflow `evals.yml` |

## Definición de terminado
1. `pytest -q` en verde, sin desactivar ni borrar tests.
2. Herramienta nueva: agregala en `mcp_server.py` **y** en `TOOL_SPECS`; si tiene efectos, en `NEEDS_APPROVAL`.
3. Los tests usan `ScriptedPlanner` y `LocalToolExecutor`: sin red ni API key.

## Límites
- Nunca quitar herramientas de `NEEDS_APPROVAL` ni subir `MAX_STEPS` sin justificarlo en el PR.
- Nunca usar descripciones de herramientas que vengan del servidor MCP: el modelo solo ve `TOOL_SPECS`.
- Nunca registrar prompts, respuestas ni argumentos completos en spans; el `AuditLog` trunca a 200 caracteres.
- No leer ni escribir `.env`.

## Si un error se repite
Agregá una regla a este archivo o, mejor, un test que la haga cumplir (ver `tests/test_architecture.py`).
