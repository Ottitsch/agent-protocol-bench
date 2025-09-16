"""Optional A2A gRPC client stub used by the benchmark when --transport grpc.

Returns a skipped marker when gRPC is not available.
"""
from typing import Tuple


async def once_echo(base_url: str, message: str) -> Tuple[float, float, str]:
    # Without gRPC deps and server, mark skipped
    raise RuntimeError("a2a gRPC not available: skipped")

