from acp.server.lowlevel import Server, NotificationOptions
from acp.server.stdio import stdio_server
import anyio
import acp.types as types


srv = Server("acp-echo")


@srv.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="echo",
            description="Echo back the input message",
            inputSchema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
        ),
        types.Tool(
            name="add",
            description="Add two numbers",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
            },
        ),
    ]


@srv.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "echo":
        msg = arguments.get("message", "")
        return [types.TextContent(type="text", text=str(msg))]
    if name == "add":
        a = int(arguments.get("a", 0))
        b = int(arguments.get("b", 0))
        return [types.TextContent(type="text", text=str(a + b))]
    raise ValueError(f"Unknown tool: {name}")


async def main():
    async with stdio_server() as (read, write):
        await srv.run(
            read,
            write,
            srv.create_initialization_options(notification_options=NotificationOptions()),
        )


if __name__ == "__main__":
    anyio.run(main)

