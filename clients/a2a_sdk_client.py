import asyncio
import time
import json
import argparse
from a2a.client.client_factory import ClientFactory, ClientConfig, minimal_agent_card
from a2a.client.helpers import create_text_message_object
from a2a.types import Role


class A2AClientPersistent:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = None

    async def start(self) -> None:
        config = ClientConfig(streaming=False)
        factory = ClientFactory(config)
        card = minimal_agent_card(url=f"{self._base_url}/a2a/jsonrpc", transports=["JSONRPC"])
        self._client = factory.create(card)
        # No explicit initialize method; client initializes on first call

    async def echo(self, message: str) -> tuple[float, float, str]:
        if not self._client:
            raise RuntimeError("client not started")
        req_msg = create_text_message_object(Role.user, message)
        t_rpc0 = time.perf_counter()
        async for result in self._client.send_message(req_msg):
            if hasattr(result, "parts"):
                for p in result.parts:
                    if hasattr(p.root, "text"):
                        t_rpc1 = time.perf_counter()
                        return (t_rpc1 - t_rpc0) * 1000, (t_rpc1 - t_rpc0) * 1000, p.root.text or ""
        return 0.0, 0.0, ""

    async def close(self) -> None:
        # Underlying SDK manages HTTP session; no explicit close exposed here
        self._client = None


async def once_echo(base_url: str, message: str) -> tuple[float, float, str]:
    try:
        config = ClientConfig(streaming=False)
        factory = ClientFactory(config)
        card = minimal_agent_card(url=f"{base_url}/a2a/jsonrpc", transports=["JSONRPC"])
        client = factory.create(card)
        req_msg = create_text_message_object(Role.user, message)
        t0 = time.perf_counter()
        async for result in client.send_message(req_msg):
            # Non-streaming returns a Message
            if hasattr(result, "parts"):
                parts = result.parts
                for p in parts:
                    if hasattr(p.root, "text"):
                        t1 = time.perf_counter()
                        return (t1 - t0) * 1000, (t1 - t0) * 1000, p.root.text or ""
        return 0.0, 0.0, ""
    except Exception as e:
        print(f"A2A SDK echo failed: {e}")
        return 0.0, 0.0, ""


async def once_add(base_url: str, a: int, b: int) -> int:
    # Use simple ADD command understood by the server handler
    config = ClientConfig(streaming=False)
    factory = ClientFactory(config)
    card = minimal_agent_card(url=f"{base_url}/a2a/jsonrpc", transports=["JSONRPC"])
    client = factory.create(card)
    req_msg = create_text_message_object(Role.user, f"ADD {a} {b}")
    async for result in client.send_message(req_msg):
        if hasattr(result, "parts"):
            for p in result.parts:
                if hasattr(p.root, "text"):
                    try:
                        return int(p.root.text or "0")
                    except Exception:
                        return 0
    return 0


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8201")
    ap.add_argument("--message", default="hello")
    args = ap.parse_args()
    lat_total, lat_rpc, out = await once_echo(args.base_url, args.message)
    print(json.dumps({"latency_total_ms": lat_total, "latency_rpc_ms": lat_rpc, "echo": out}))


if __name__ == "__main__":
    asyncio.run(main())
