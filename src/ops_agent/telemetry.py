"""Spans según las convenciones semánticas GenAI de OpenTelemetry (estado: Development).

Si opentelemetry-api no está instalado, todo es no-op: el agente funciona igual.
Nombres de span y atributos tomados de:
https://github.com/open-telemetry/semantic-conventions-genai/tree/main/docs/gen-ai
"""
from contextlib import contextmanager
from typing import Any, Iterator

try:
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind, Status, StatusCode
except ImportError:  # pragma: no cover - depende del entorno
    trace = None

AGENT_NAME = "ops-agent"


class _NoopSpan:
    def set_attribute(self, key: str, value: Any) -> None:
        pass


def get_tracer(provider: Any = None) -> Any:
    if trace is None:
        return None
    return provider.get_tracer("ops_agent") if provider else trace.get_tracer("ops_agent")


@contextmanager
def span(tracer: Any, name: str, attributes: dict[str, Any], client: bool = False) -> Iterator[Any]:
    if tracer is None:
        yield _NoopSpan()
        return
    kind = SpanKind.CLIENT if client else SpanKind.INTERNAL
    with tracer.start_as_current_span(name, kind=kind, attributes=attributes) as current:
        try:
            yield current
        except Exception as exc:
            current.set_attribute("error.type", type(exc).__qualname__)
            current.set_status(Status(StatusCode.ERROR))
            raise


def invoke_agent(tracer: Any) -> Any:
    return span(tracer, f"invoke_agent {AGENT_NAME}",
                {"gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": AGENT_NAME})


def chat(tracer: Any, model: str, provider: str = "openai") -> Any:
    return span(tracer, f"chat {model}",
                {"gen_ai.operation.name": "chat", "gen_ai.provider.name": provider, "gen_ai.request.model": model},
                client=True)


def execute_tool(tracer: Any, tool: str, call_id: str | None = None) -> Any:
    attrs = {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": tool,
             "gen_ai.tool.type": "function", "gen_ai.agent.name": AGENT_NAME}
    if call_id:
        attrs["gen_ai.tool.call.id"] = call_id
    return span(tracer, f"execute_tool {tool}", attrs)
