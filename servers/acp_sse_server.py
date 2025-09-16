from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import Response
import uvicorn
import anyio
from acp.server.lowlevel import Server, NotificationOptions
from acp.server.sse import SseServerTransport
import acp.types as types


srv = Server("acp-echo-sse")


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


def create_app() -> Starlette:
    sse = SseServerTransport("/acp/messages/")

    async def handle_sse(request):  # type: ignore[override]
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:  # noqa: SLF001
            await srv.run(
                streams[0],
                streams[1],
                srv.create_initialization_options(notification_options=NotificationOptions()),
            )
        return Response()

    routes = [
        Route("/acp/sse", endpoint=handle_sse, methods=["GET"]),
        Mount("/acp/messages/", app=sse.handle_post_message),
    ]
    return Starlette(routes=routes)


async def main():
    app = create_app()
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8101, log_level="error")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    anyio.run(main)

