import time
import argparse
import json
from typing import Tuple
from httpx_sse import aconnect_sse


async def once_stream_echo(base_url: str, message: str, chunks: int = 3, delay_ms: int = 10, token: str | None = None) -> tuple[float, float, str]:
    """Connects to A2A SSE echo endpoint and measures TTFB and total time.

    Returns (ttfb_ms, total_ms, concatenated_output)
    """
    url = f"{base_url.rstrip('/')}/a2a/sse/echo?message={message}&chunks={chunks}&delay_ms={delay_ms}"
    headers = {"Accept": "text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    t0 = time.perf_counter()
    out_parts = []
    ttfb_ms = 0.0
    async with aconnect_sse(url, method="GET", headers=headers) as event_source:
        # First event arrival marks TTFB
        async for sse in event_source.aiter_sse():
            if ttfb_ms == 0.0:
                ttfb_ms = (time.perf_counter() - t0) * 1000
            if sse.data:
                out_parts.append(sse.data)
    total_ms = (time.perf_counter() - t0) * 1000
    return ttfb_ms, total_ms, "".join(out_parts)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8201")
    ap.add_argument("--message", default="hello")
    ap.add_argument("--chunks", type=int, default=3)
    ap.add_argument("--delay-ms", type=int, default=5)
    ap.add_argument("--token", default=None)
    args = ap.parse_args()
    ttfb, total, out = await once_stream_echo(args.base_url, args.message, args.chunks, args.delay_ms, args.token)
    print(json.dumps({"ttfb_ms": ttfb, "stream_total_ms": total, "echo": out}))


