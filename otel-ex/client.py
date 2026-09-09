"""
bookshop MCP client — thin wrapper around the MCP SDK's stdio transport,
exposing tool discovery and invocation as plain async methods. This class
owns only the MCP session lifecycle; it knows nothing about Claude,
conversation state, or tracing spans — that's BookshopAgent's job
(see agent.py).
"""

import logging
from contextlib import AsyncExitStack
from typing import Any, Callable

from mcp.client import Client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp_types import TextResourceContents

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(
        self,
        name: str,
        command: str,
        server_args: list[str],
        env_vars: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.command = command
        self.server_args = server_args
        self.env_vars = env_vars
        self._client: Client | None = None
        self._exit_stack: AsyncExitStack = AsyncExitStack()
        self._connected: bool = False

    async def __aenter__(self) -> "MCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        """
        Connect to the server set in the constructor.
        """
        if self._connected:
            raise RuntimeError("Client is already connected")

        server_parameters = StdioServerParameters(
            command=self.command,
            args=self.server_args,
            env=self.env_vars if self.env_vars else None,
        )

        transport = stdio_client(server_parameters)
        self._client = Client(transport)

        await self._exit_stack.enter_async_context(self._client)
        self._connected = True

    async def get_available_tools(self) -> list[dict[str, Any]]:
        if not self._connected:
            raise RuntimeError("Client not connected to a server")

        tools_result = await self._client.list_tools()
        if not tools_result.tools:
            logger.warning("No tools found on server %s", self.name)

        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in tools_result.tools
        ]

    async def use_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        progress_callback: Callable | None = None,
    ) -> list[str]:
        if not self._connected:
            raise RuntimeError("Client not connected to a server")

        logger.debug("Calling tool %s with arguments %s", tool_name, arguments)
        tool_call_result = await self._client.call_tool(
            name=tool_name,
            arguments=arguments,
            progress_callback=progress_callback,
        )

        results: list[str] = []
        if tool_call_result.content:
            for content in tool_call_result.content:
                match content.type:
                    case "text":
                        results.append(content.text)
                    case "image" | "audio":
                        results.append(content.data)
                    case "resource":
                        if isinstance(content.resource, TextResourceContents):
                            results.append(content.resource.text)
                        else:
                            results.append(content.resource.blob)
        else:
            logger.warning("No content in tool call result for tool %s", tool_name)

        return results

    async def disconnect(self) -> None:
        """
        Clean up any resources
        """
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._connected = False
            self._client = None
