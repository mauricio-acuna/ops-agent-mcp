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
- `agent_definition.py` — contrato `AgentDefinition` validado, independiente del dominio.
- `order_agent.py` — prompt, herramientas y configuración de referencia del agente de pedidos.
- `runtime_contracts.py` — protocolos y mensajes comunes del runtime, sin dominio ni proveedor.
- `orders.py` — `OrderStore` y reglas de reembolso (Python puro).
- `tools.py` — catálogo y ejecutores local y MCP (verifica el servidor con el manifiesto del agente).
- `security.py` — `validate_args` y `check_server_tools` sobre manifiestos; `AuditLog` (Python puro).
- `telemetry.py` — spans `invoke_agent` / `chat` / `execute_tool` con atributos `gen_ai.*` (no-op sin OpenTelemetry).
- `planner.py` — interfaz `Planner`: `OpenAIPlanner` y `ScriptedPlanner` (tests).
- `graph.py` — runtime LangGraph plan → approval (`interrupt`) → execute/reject; requiere `AgentDefinition`.
- `mcp_server.py` — servidor MCP "pedidos".
- `evals/` — casos de trayectoria (incluye inyección indirecta) y gate.

## Invariantes (cada una tiene un sensor)
| Regla | Sensor |
|---|---|
| `orders.py` y `security.py` no importan openai, langgraph ni mcp | `test_architecture.py` |
| `graph.py` no importa proveedor, transporte ni reglas de pedidos | `test_architecture.py` |
| `agent_definition.py` y `runtime_contracts.py` no importan el dominio ni integraciones | `test_architecture.py` |
| El grafo valida herramientas y límites con su definición explícita | `test_agent_definition.py`, `test_graph.py` |
| `request_refund` requiere aprobación humana | `test_architecture.py`, `test_graph.py` |
| Herramientas de `mcp_server.py` == `TOOL_SPECS` | `test_architecture.py` |
| El grafo solo acepta herramientas declaradas por su `AgentDefinition` | `test_agent_definition.py`, `test_graph.py` |
| Argumentos fuera del esquema se bloquean antes de aprobar o ejecutar | `test_policy.py`, `test_security.py` |
| Un agente engañado no mueve dinero sin humano ni por encima del total | `test_security.py` |
| Cada decisión queda en el `AuditLog` | `test_security.py` |
| Spans con nombres y atributos `gen_ai.*`, sin contenido | `test_telemetry.py` |
| El grafo respeta `AgentDefinition.max_steps` | `test_graph.py`, `test_agent_definition.py` |
| El modelo real no llama herramientas prohibidas (incluida inyección) | `evals/` + workflow `evals.yml` |

## Definición de terminado
1. `pytest -q` en verde, sin desactivar ni borrar tests.
2. Herramienta nueva: agregala en `mcp_server.py`, `TOOL_SPECS` y en la definición del agente que la consume; si tiene efectos, requiere aprobación.
3. Los tests usan `ScriptedPlanner` y `LocalToolExecutor`: sin red ni API key.

## Límites
- Nunca quitar una herramienta con efectos de `approval_tools` ni ampliar `max_steps` sin justificarlo en el PR.
- Nunca usar descripciones de herramientas que vengan del servidor MCP: el modelo solo ve el manifiesto local del agente.
- Nunca registrar prompts, respuestas ni argumentos completos en spans; el `AuditLog` trunca a 200 caracteres.
- No leer ni escribir `.env`.

## Si un error se repite
Agregá una regla a este archivo o, mejor, un test que la haga cumplir (ver `tests/test_architecture.py`).
