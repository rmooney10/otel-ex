"""
bookshop agent — owns the Claude <-> MCP tool-use loop and the OTel
tracing around it. MCPClient (client.py) handles only the MCP session;
this class handles conversation state, calling the model, deciding when
to invoke a tool versus return a final answer, and the spans that tie a
full user turn together.
"""

import logging
from typing import Any

from anthropic import Anthropic, APIStatusError
from opentelemetry.trace import Tracer

from client import MCPClient

logger = logging.getLogger(__name__)


class BookshopAgent:
    def __init__(
        self,
        anthropic_client: Anthropic,
        mcp_client: MCPClient,
        tracer: Tracer,
        model: str = "claude-sonnet-5",
        max_tokens: int = 4096,
    ) -> None:
        self.anthropic_client = anthropic_client
        self.mcp_client = mcp_client
        self.tracer = tracer
        self.model = model
        self.max_tokens = max_tokens
        self._available_tools: list[dict[str, Any]] = []

    async def start(self) -> None:
        """Connect to the MCP server and load its tool list."""
        await self.mcp_client.connect()
        self._available_tools = await self.mcp_client.get_available_tools()
        tool_names = ", ".join(t["name"] for t in self._available_tools)
        logger.info("Connected. Available tools: %s", tool_names)

    async def stop(self) -> None:
        await self.mcp_client.disconnect()

    async def handle_turn(self, prompt: str) -> str:
        """
        Run one user turn to completion: send the prompt to Claude, execute
        any tool calls it requests, feed the results back, and repeat until
        Claude returns a final text answer. Everything in this method
        shares one root span, so the model call and every tool call nest
        under it in the same trace.
        """
        conversation_messages: list[dict[str, Any]] = [
            {"role": "user", "content": prompt}
        ]

        with self.tracer.start_as_current_span("user_turn") as turn_span:
            turn_span.set_attribute("user.prompt_length", len(prompt))

            while True:
                current_response = await self._call_model(conversation_messages)
                conversation_messages.append(
                    {"role": "assistant", "content": current_response.content}
                )

                if current_response.stop_reason == "tool_use":
                    tool_results = await self._run_tool_calls(current_response)
                    conversation_messages.append(
                        {"role": "user", "content": tool_results}
                    )
                    continue

                return self._extract_text(current_response)

    async def _call_model(self, conversation_messages: list[dict[str, Any]]):
        with self.tracer.start_as_current_span("llm.generate") as span:
            span.set_attribute("llm.model", self.model)
            try:
                response = self.anthropic_client.messages.create(
                    max_tokens=self.max_tokens,
                    messages=conversation_messages,
                    model=self.model,
                    tools=self._available_tools,
                    tool_choice={"type": "auto"},
                )
            except APIStatusError as exc:
                span.set_attribute("llm.error", True)
                span.set_attribute("llm.error.status_code", exc.status_code)
                logger.error("Anthropic API error: %s", exc)
                raise

            span.set_attribute("llm.stop_reason", response.stop_reason)
            span.set_attribute("llm.usage.input_tokens", response.usage.input_tokens)
            span.set_attribute("llm.usage.output_tokens", response.usage.output_tokens)
            return response

    async def _run_tool_calls(self, response: Any) -> list[dict[str, Any]]:
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        tool_results = []
        for tool_use in tool_use_blocks:
            logger.info("Using tool: %s", tool_use.name)
            tool_result = await self.mcp_client.use_tool(
                tool_name=tool_use.name,
                arguments=tool_use.input,
                progress_callback=self._progress_handler,
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": "\n".join(tool_result),
                }
            )
        return tool_results

    @staticmethod
    def _extract_text(response: Any) -> str:
        text_blocks = [
            block.text
            for block in response.content
            if hasattr(block, "text") and block.text.strip()
        ]
        return text_blocks[0] if text_blocks else "[No text response available]"

    @staticmethod
    async def _progress_handler(
        progress: float, total: float | None, message: str | None
    ) -> None:
        if message:
            logger.info(message)
        if total:
            logger.info("%.0f%% complete", progress / total * 100)
        else:
            logger.info("%s complete", progress)
