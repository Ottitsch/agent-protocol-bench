# Minimal MCP echo/calculator server
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import anyio

srv = Server("mcp-echo")

@srv.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="echo",
            description="Echo back the input message",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message to echo"}
                },
                "required": ["message"]
            }
        ),
        Tool(
            name="add",
            description="Add two numbers",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "integer", "description": "First number"},
                    "b": {"type": "integer", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
        )
    ]

@srv.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "echo":
        result = arguments.get("message", "")
        return [TextContent(type="text", text=result)]
    elif name == "add":
        a = arguments.get("a", 0)
        b = arguments.get("b", 0)
        result = str(a + b)
        return [TextContent(type="text", text=result)]
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read, write):
        await srv.run(read, write, srv.create_initialization_options())

if __name__ == "__main__":
    anyio.run(main)
