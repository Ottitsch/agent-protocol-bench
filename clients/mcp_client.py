import anyio, time, json, argparse
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from contextlib import AsyncExitStack

async def once_echo(message: str) -> tuple[float, str]:
    try:
        server_params = StdioServerParameters(command="python", args=["-m","servers.mcp_echo_server"])
        async with stdio_client(server_params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = [t.name for t in tools.tools]
                if "echo" not in names:
                    raise RuntimeError("echo tool not found")
                # Start timing after initialization and tool discovery for fair comparison
                start = time.perf_counter()
                res = await session.call_tool("echo", {"message": message})
                latency = (time.perf_counter()-start)*1000
                return latency, res.content[0].text if res.content else ""
    except Exception as e:
        print(f"MCP echo failed: {e}")
        return 0.0, ""

async def once_add(a: int, b: int) -> int:
    server_params = StdioServerParameters(command="python", args=["-m","servers.mcp_echo_server"])
    async with stdio_client(server_params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            res = await session.call_tool("add", {"a": a, "b": b})
            return int(res.content[0].text)

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--message", default="hello")
    args = ap.parse_args()
    lat, out = await once_echo(args.message)
    print(json.dumps({"latency_ms": lat, "echo": out}))

if __name__ == "__main__":
    anyio.run(main)


class MCPStdioPersistent:
    """Persistent MCP stdio client for reuse mode."""

    def __init__(self) -> None:
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def start(self) -> None:
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        server_params = StdioServerParameters(
            command="python", args=["-m", "servers.mcp_echo_server"]
        )
        streams = await self._stack.enter_async_context(stdio_client(server_params))
        session = ClientSession(*streams)
        await self._stack.enter_async_context(session)
        await session.initialize()
        # Eager tool discovery to exclude from per-call timing
        await session.list_tools()
        self._session = session

    async def echo(self, message: str) -> tuple[float, str]:
        if not self._session:
            raise RuntimeError("client not started")
        start = time.perf_counter()
        res = await self._session.call_tool("echo", {"message": message})
        latency = (time.perf_counter() - start) * 1000
        return latency, res.content[0].text if res.content else ""

    async def close(self) -> None:
        if self._stack:
            await self._stack.aclose()
            self._stack = None
            self._session = None
