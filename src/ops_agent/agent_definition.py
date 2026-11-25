"""Configuración validada que separa un agente concreto del motor de ejecución."""
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

_SUPPORTED_JSON_TYPES = {"string", "number", "integer", "boolean"}


@dataclass(frozen=True, init=False)
class AgentDefinition:
    agent_id: str
    version: str
    system_prompt: str
    _tool_specs: tuple[dict[str, Any], ...]
    approval_tools: frozenset[str]
    max_steps: int

    def __init__(
        self,
        agent_id: str,
        version: str,
        system_prompt: str,
        tool_specs: tuple[dict[str, Any], ...],
        approval_tools: frozenset[str] = frozenset(),
        max_steps: int = 6,
    ) -> None:
        object.__setattr__(self, "agent_id", agent_id)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "system_prompt", system_prompt)
        object.__setattr__(self, "_tool_specs", tool_specs)
        object.__setattr__(self, "approval_tools", approval_tools)
        object.__setattr__(self, "max_steps", max_steps)
        self.__post_init__()

    def __post_init__(self) -> None:
        if not isinstance(self.agent_id, str) or not self.agent_id.strip():
            raise ValueError("agent_id no puede estar vacío")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version no puede estar vacía")
        if not isinstance(self.system_prompt, str) or not self.system_prompt.strip():
            raise ValueError("system_prompt no puede estar vacío")
        if isinstance(self.max_steps, bool) or not isinstance(self.max_steps, int) or self.max_steps < 1:
            raise ValueError("max_steps debe ser un entero positivo")

        specs = tuple(deepcopy(self._tool_specs))
        names: list[str] = []
        for spec in specs:
            if not isinstance(spec, dict) or spec.get("type") != "function":
                raise ValueError("cada herramienta debe tener type=function")
            function = spec.get("function")
            if (
                not isinstance(function, dict)
                or not isinstance(function.get("name"), str)
                or not function["name"].strip()
            ):
                raise ValueError("cada herramienta debe declarar function.name")
            parameters = function.get("parameters")
            if (
                not isinstance(parameters, dict)
                or parameters.get("type") != "object"
                or not isinstance(parameters.get("properties"), dict)
            ):
                raise ValueError(f"{function['name']}: parameters.properties debe ser un objeto")
            properties = parameters["properties"]
            for property_name, property_schema in properties.items():
                if (
                    not isinstance(property_name, str)
                    or not property_name.strip()
                    or not isinstance(property_schema, dict)
                    or property_schema.get("type") not in _SUPPORTED_JSON_TYPES
                ):
                    raise ValueError(f"{function['name']}: propiedad inválida {property_name!r}")
            required = parameters.get("required", [])
            if (
                not isinstance(required, list)
                or any(not isinstance(name, str) for name in required)
                or len(required) != len(set(required))
                or not set(required) <= set(properties)
            ):
                raise ValueError(f"{function['name']}: parameters.required inválido")
            names.append(function["name"])

        if len(names) != len(set(names)):
            raise ValueError("tool_specs contiene nombres duplicados")
        approvals = frozenset(self.approval_tools)
        unknown_approvals = approvals - set(names)
        if unknown_approvals:
            raise ValueError(f"approval_tools no declaradas en tool_specs: {sorted(unknown_approvals)}")

        object.__setattr__(self, "_tool_specs", specs)
        object.__setattr__(self, "approval_tools", approvals)

    @property
    def tool_specs(self) -> tuple[dict[str, Any], ...]:
        return tuple(deepcopy(self._tool_specs))

    @property
    def allowed_tools(self) -> frozenset[str]:
        return frozenset(spec["function"]["name"] for spec in self._tool_specs)

    def model_tool_specs(self) -> list[dict[str, Any]]:
        return deepcopy(list(self._tool_specs))
