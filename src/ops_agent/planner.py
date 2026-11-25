"""El planner decide el próximo paso. La interfaz permite cambiar de proveedor o usar uno falso en tests."""
import json
import os
from dataclasses import dataclass
from typing import Protocol

from ops_agent.agent_definition import AgentDefinition


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class Final:
    text: str


Action = ToolCall | Final


class Planner(Protocol):
    def next_action(self, messages: list[dict]) -> Action: ...


class OpenAIPlanner:
    def __init__(self, definition: AgentDefinition, model: str | None = None, tracer=None) -> None:
        from openai import OpenAI

        self.client = OpenAI()
        self.model = model or os.environ["OPENAI_MODEL"]
        self.tracer = tracer
        self.definition = definition

    def next_action(self, messages: list[dict]) -> Action:
        from ops_agent import telemetry

        with telemetry.chat(self.tracer, self.model) as span:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "developer", "content": self.definition.system_prompt}, *messages],
                tools=self.definition.model_tool_specs(),
                parallel_tool_calls=False,
            )
            span.set_attribute("gen_ai.response.model", response.model)
            span.set_attribute("gen_ai.response.id", response.id)
            span.set_attribute("gen_ai.response.finish_reasons", [c.finish_reason for c in response.choices])
            if response.usage:
                span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", response.usage.completion_tokens)
        msg = response.choices[0].message
        if msg.tool_calls:
            call = msg.tool_calls[0]
            return ToolCall(call.id, call.function.name, json.loads(call.function.arguments or "{}"))
        return Final(msg.content or "")


class ScriptedPlanner:
    """Planner determinista para tests: devuelve las acciones en orden."""

    def __init__(self, actions: list[Action]) -> None:
        self.actions = list(actions)
        self.seen: list[list[dict]] = []

    def next_action(self, messages: list[dict]) -> Action:
        self.seen.append(list(messages))
        return self.actions.pop(0) if self.actions else Final("(sin más acciones)")
