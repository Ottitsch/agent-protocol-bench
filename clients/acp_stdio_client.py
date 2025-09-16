import anyio
import time
import json
import argparse
from acp.client.stdio import stdio_client, StdioServerParameters
from acp.client.session import ClientSession


async def once_echo(message: str) -> tuple[float, str]:
    try:
        server_params = StdioServerParameters(
            command="python", args=["-m", "servers.acp_stdio_server"]
        )
        async with stdio_client(server_params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = [t.name for t in tools.tools]
                if "echo" not in names:
                    raise RuntimeError("echo tool not found")
                start = time.perf_counter()
                res = await session.call_tool("echo", {"message": message})
                latency = (time.perf_counter() - start) * 1000
                return latency, res.content[0].text if res.content else ""
    except Exception as e:
        print(f"ACP stdio echo failed: {e}")
        return 0.0, ""


async def once_add(a: int, b: int) -> int:
    server_params = StdioServerParameters(
        command="python", args=["-m", "servers.acp_stdio_server"]
    )
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

