from types import SimpleNamespace

from ops_agent.agent_definition import AgentDefinition
from ops_agent.order_agent import ORDER_AGENT
from ops_agent.planner import Final, OpenAIPlanner


def test_openai_planner_uses_its_agent_definition(monkeypatch):
    read_only = AgentDefinition(
        agent_id="read-only-orders",
        version="1",
        system_prompt="Responde con información de pedidos.",
        tool_specs=tuple(
            spec for spec in ORDER_AGENT.tool_specs
            if spec["function"]["name"] == "get_order"
        ),
    )
    request = {}

    def create(**kwargs):
        request.update(kwargs)
        message = SimpleNamespace(tool_calls=[], content="Pedido encontrado.")
        choice = SimpleNamespace(finish_reason="stop", message=message)
        return SimpleNamespace(model="test-model", id="response-1", choices=[choice], usage=None)

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    monkeypatch.setattr("openai.OpenAI", lambda: client)

    planner = OpenAIPlanner(definition=read_only, model="test-model")
    action = planner.next_action([{"role": "user", "content": "Busca el pedido."}])

    assert action == Final("Pedido encontrado.")
    assert request["messages"][0] == {
        "role": "developer",
        "content": "Responde con información de pedidos.",
    }
    assert [tool["function"]["name"] for tool in request["tools"]] == ["get_order"]
