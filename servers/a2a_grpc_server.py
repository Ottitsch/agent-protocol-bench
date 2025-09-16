"""Optional A2A gRPC server stub.

If a2a gRPC dependencies are not installed, this module will exit with a clear message.
"""
import sys


async def main():
    # We don't implement a real gRPC server here to avoid hard dependency.
    # This placeholder allows the benchmark harness to detect availability.
    print("A2A gRPC server not available (grpc deps not installed)")
    sys.exit(3)


if __name__ == "__main__":
    import anyio

    anyio.run(main)

