"""CLI interactiva: pregunta → agente → aprobación humana en consola cuando corresponde."""
import argparse
import asyncio
import uuid

from dotenv import load_dotenv
from langgraph.types import Command

from ops_agent import telemetry
from ops_agent.graph import build_graph
from ops_agent.planner import OpenAIPlanner
from ops_agent.security import AuditLog
from ops_agent.tools import LocalToolExecutor, McpToolExecutor


async def run(question: str, mcp_url: str | None, audit_file: str) -> None:
    session = str(uuid.uuid4())
    tracer = telemetry.get_tracer()
    executor = McpToolExecutor(mcp_url) if mcp_url else LocalToolExecutor()
    audit = AuditLog(audit_file, session=session)
    graph = build_graph(OpenAIPlanner(tracer=tracer), executor, audit=audit, tracer=tracer)
    config = {"configurable": {"thread_id": session}}

    with telemetry.invoke_agent(tracer):
        result = await graph.ainvoke({"messages": [{"role": "user", "content": question}], "steps": 0}, config)
        while "__interrupt__" in result:
            request = result["__interrupt__"][0].value
            answer = input(f"\n¿Aprobar {request['tool']} con {request['args']}? [s/N]: ").strip().lower()
            decision = "approve" if answer == "s" else "reject"
            result = await graph.ainvoke(Command(resume=decision), config)

    print("\n" + result.get("final", "(sin respuesta)"))
    print(f"(auditoría: {audit_file}, sesión {session})")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Agente de operaciones de pedidos")
    parser.add_argument("question")
    parser.add_argument("--mcp-url", help="ej. http://localhost:8000/mcp; si se omite usa herramientas locales")
    parser.add_argument("--audit-file", default="audit.jsonl", help="registro append-only de decisiones")
    args = parser.parse_args()
    asyncio.run(run(args.question, args.mcp_url, args.audit_file))


if __name__ == "__main__":
    main()
