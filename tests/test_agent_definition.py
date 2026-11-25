import pytest

from ops_agent.agent_definition import AgentDefinition
from ops_agent.order_agent import ORDER_AGENT


def _definition(**overrides):
    values = {
        "agent_id": "read-only-orders",
        "version": "1",
        "system_prompt": "Responde solo con información de pedidos.",
        "tool_specs": tuple(spec for spec in ORDER_AGENT.tool_specs if spec["function"]["name"] == "get_order"),
        "approval_tools": frozenset(),
        "max_steps": 2,
    }
    values.update(overrides)
    return AgentDefinition(**values)


def test_definition_exposes_only_its_declared_tools():
    definition = _definition()

    assert definition.allowed_tools == frozenset({"get_order"})
    assert [spec["function"]["name"] for spec in definition.model_tool_specs()] == ["get_order"]


def test_model_tool_specs_are_copied():
    definition = _definition()
    exposed_specs = definition.model_tool_specs()
    exposed_specs[0]["function"]["name"] = "delete_database"

    assert definition.allowed_tools == frozenset({"get_order"})


def test_tool_specs_cannot_be_mutated_through_definition():
    definition = _definition()
    exposed_specs = definition.tool_specs
    exposed_specs[0]["function"]["name"] = "delete_database"

    assert definition.allowed_tools == frozenset({"get_order"})


@pytest.mark.parametrize("max_steps", [0, -1, True, 1.5])
def test_definition_rejects_invalid_step_limits(max_steps):
    with pytest.raises(ValueError, match="max_steps"):
        _definition(max_steps=max_steps)


def test_definition_rejects_approval_for_undeclared_tool():
    with pytest.raises(ValueError, match="approval_tools no declaradas"):
        _definition(approval_tools=frozenset({"request_refund"}))


def test_definition_rejects_duplicate_tools():
    get_order = next(spec for spec in ORDER_AGENT.tool_specs if spec["function"]["name"] == "get_order")
    with pytest.raises(ValueError, match="nombres duplicados"):
        _definition(tool_specs=(get_order, get_order))


def test_definition_rejects_argument_types_the_runtime_cannot_validate():
    invalid_spec = {
        "type": "function",
        "function": {
            "name": "search",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "array"}},
                "required": ["query"],
            },
        },
    }

    with pytest.raises(ValueError, match="propiedad inválida"):
        _definition(tool_specs=(invalid_spec,))


def test_definition_rejects_required_parameters_not_declared_in_properties():
    invalid_spec = {
        "type": "function",
        "function": {
            "name": "search",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": ["query"],
            },
        },
    }

    with pytest.raises(ValueError, match="parameters.required inválido"):
        _definition(tool_specs=(invalid_spec,))
