from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import Response
import uvicorn
import anyio
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent


srv = Server("mcp-echo-sse")


@srv.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="echo",
            description="Echo back the input message",
            inputSchema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
        ),
        Tool(
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
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "echo":
        msg = arguments.get("message", "")
        return [TextContent(type="text", text=str(msg))]
    if name == "add":
        a = int(arguments.get("a", 0))
        b = int(arguments.get("b", 0))
        return [TextContent(type="text", text=str(a + b))]
    raise ValueError(f"Unknown tool: {name}")


def create_app() -> Starlette:
    sse = SseServerTransport("/mcp/messages/")

    async def handle_sse(request):  # type: ignore[override]
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:  # noqa: SLF001
            await srv.run(streams[0], streams[1], srv.create_initialization_options())
        return Response()

    routes = [
        Route("/mcp/sse", endpoint=handle_sse, methods=["GET"]),
        Mount("/mcp/messages/", app=sse.handle_post_message),
    ]
    return Starlette(routes=routes)


async def main():
    app = create_app()
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8001, log_level="error")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    anyio.run(main)

