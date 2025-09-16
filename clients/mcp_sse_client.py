import time
import json
import argparse
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.sse import sse_client


class MCPHttpPersistent:
    def __init__(self, base_url: str) -> None:
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._base_url = base_url.rstrip("/")

    async def start(self) -> None:
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        streams = await self._stack.enter_async_context(
            sse_client(f"{self._base_url}/mcp/sse")
        )
        session = ClientSession(*streams)
        await self._stack.enter_async_context(session)
        await session.initialize()
        await session.list_tools()
        self._session = session

    async def echo(self, message: str) -> tuple[float, float, str]:
        if not self._session:
            raise RuntimeError("client not started")
        t_rpc0 = time.perf_counter()
        res = await self._session.call_tool("echo", {"message": message})
        t_rpc1 = time.perf_counter()
        return (t_rpc1 - t_rpc0) * 1000, (t_rpc1 - t_rpc0) * 1000, res.content[0].text if res.content else ""

    async def close(self) -> None:
        if self._stack:
            await self._stack.aclose()
            self._stack = None
            self._session = None


async def once_echo(base_url: str, message: str) -> tuple[float, float, str]:
    t0 = time.perf_counter()
    async with sse_client(f"{base_url.rstrip('/')}/mcp/sse") as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            await session.list_tools()
            t_rpc0 = time.perf_counter()
            res = await session.call_tool("echo", {"message": message})
            t_rpc1 = time.perf_counter()
            t1 = time.perf_counter()
            return (t1 - t0) * 1000, (t_rpc1 - t_rpc0) * 1000, res.content[0].text if res.content else ""


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8001")
    ap.add_argument("--message", default="hello")
    args = ap.parse_args()
    lat_total, lat_rpc, out = await once_echo(args.base_url, args.message)
    print(json.dumps({"latency_total_ms": lat_total, "latency_rpc_ms": lat_rpc, "echo": out}))

