"""
Entry point — bootstraps OTel once, wires together the Anthropic client,
MCPClient (client.py), and BookshopAgent (agent.py)

Splitting things this way keeps three concerns apart: the MCP
session (client.py), the conversation/tool-use loop (agent.py), and
process wiring/bootstrap (this file).
"""

import asyncio
import logging
import os

from anthropic import Anthropic
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# Swap in once a collector (e.g. Jaeger) is listening on 4317:
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from agent import BookshopAgent
from client import MCPClient

load_dotenv()
logging.basicConfig(level=logging.INFO)

# --- OTel bootstrap: do this once, here, before anything else runs ---
provider = TracerProvider(resource=Resource.create({"service.name": "bookshop-agent"}))
#provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True))
)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("bookshop.agent")


async def main() -> None:
    anthropic_client = Anthropic(api_key=os.environ["LLM_API_KEY"])
    mcp_client = MCPClient(
        name="bookshop_server_connection",
        command="python",
        server_args=["otel-ex/otel_server.py"],
    )
    agent = BookshopAgent(anthropic_client, mcp_client, tracer)

    print("Welcome to the Bookshop Assistant. Type 'goodbye' to quit.")
    try:
        await agent.start()
        while True:
            prompt = input("You: ")
            if prompt.lower() == "goodbye" or prompt.lower() == "bye":
                print("Assistant: Goodbye!")
                break
            answer = await agent.handle_turn(prompt)
            print(f"Assistant: {answer}")
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
