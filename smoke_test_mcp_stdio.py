from __future__ import annotations

from pathlib import Path

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main() -> None:
    repo_root = Path(__file__).resolve().parent
    params = StdioServerParameters(
        command="python",
        args=["-m", "mcp_thrift_server"],
        cwd=str(repo_root),
        env={
            "THRIFT_REGISTRY_HOST": "127.0.0.1",
            "THRIFT_REGISTRY_PORT": "55932",
        },
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            tool_names = sorted(t.name for t in tools.tools)
            print("TOOL_COUNT", len(tool_names))
            print("TOOLS", tool_names)

            version = await session.call_tool("debugger_get_version", {})
            print("VERSION_CALL", version.model_dump())

            online = await session.call_tool("debugger_is_online", {})
            print("ONLINE_CALL", online.model_dump())

            methods = await session.call_tool("debugger_list_methods", {})
            print("METHODS_CALL", methods.model_dump())


if __name__ == "__main__":
    anyio.run(main)
