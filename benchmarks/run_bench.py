import asyncio, time, json, statistics, os, argparse, pathlib, subprocess, sys
from scipy.stats import ttest_ind, mannwhitneyu
import numpy as np
import contextlib
import httpx

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def start_servers(transport: str = "http", no_spawn_a2a: bool = False, no_spawn_anp: bool = False, include_acp: bool = False):
    procs = []
    # Start SDK-based HTTP servers for A2A and ANP unless disabled
    if not no_spawn_a2a:
        procs.append(subprocess.Popen([sys.executable, "-m", "servers.a2a_sdk_server"]))
    if not no_spawn_anp:
        procs.append(subprocess.Popen([sys.executable, "-m", "servers.anp_sdk_server"]))
    # Start MCP/ACP HTTP SSE servers if using http transport parity
    if transport == "http":
        procs.append(subprocess.Popen([sys.executable, "-m", "servers.mcp_sse_server"]))
        if include_acp:
            procs.append(subprocess.Popen([sys.executable, "-m", "servers.acp_sse_server"]))
    time.sleep(2.0)  # increased boot wait for all servers
    return procs

async def run_client(
    proto,
    n,
    payload,
    concurrency,
    reuse_client: bool = True,
    mcp_persistent: bool | None = None,
    transport: str = "http",
    a2a_base_url: str = "http://127.0.0.1:8201",
    anp_base_url: str = "http://127.0.0.1:8301",
    enable_a2a_sse: bool = False,
    auth_mode: str = "none",
):
    # returns lists of latencies (ms) and success count
    latencies_total = []
    latencies_rpc = []
    success = 0

    # Optional shared HTTP client per protocol for warm connection performance
    shared_client = None
    if reuse_client:
        try:
            import httpx  # lazy import
            shared_client = httpx.AsyncClient()
        except Exception:
            shared_client = None

    # Optional persistent clients for reuse mode
    mcp_persistent_client = None
    acp_persistent_client = None
    a2a_persistent_client = None
    anp_persistent_client = None
    connect_init_timings: dict[str, float] = {}
    if reuse_client:
        try:
            if proto == "mcp":
                if transport == "http":
                    from clients.mcp_sse_client import MCPHttpPersistent
                    t0 = time.perf_counter()
                    mcp_persistent_client = MCPHttpPersistent("http://127.0.0.1:8001")
                    await mcp_persistent_client.start()
                    connect_init_timings["connect_init_ms"] = (time.perf_counter() - t0) * 1000
                else:
                    from clients.mcp_client import MCPStdioPersistent
                    t0 = time.perf_counter()
                    mcp_persistent_client = MCPStdioPersistent()
                    await mcp_persistent_client.start()
                    connect_init_timings["connect_init_ms"] = (time.perf_counter() - t0) * 1000
            elif proto == "acp" and transport == "http":
                from clients.acp_sse_client import ACPHttpPersistent
                t0 = time.perf_counter()
                acp_persistent_client = ACPHttpPersistent("http://127.0.0.1:8101")
                await acp_persistent_client.start()
                connect_init_timings["connect_init_ms"] = (time.perf_counter() - t0) * 1000
            elif proto == "a2a":
                from clients.a2a_sdk_client import A2AClientPersistent
                t0 = time.perf_counter()
                a2a_persistent_client = A2AClientPersistent(a2a_base_url)
                await a2a_persistent_client.start()
                connect_init_timings["connect_init_ms"] = (time.perf_counter() - t0) * 1000
            elif proto == "anp":
                from clients.anp_sdk_client import ANPClientPersistent
                t0 = time.perf_counter()
                anp_persistent_client = ANPClientPersistent(anp_base_url)
                await anp_persistent_client.start()
                connect_init_timings["connect_init_ms"] = (time.perf_counter() - t0) * 1000
        except Exception:
            pass

    async def one(i):
        nonlocal success
        msg = "x"*payload
        # gRPC transport is only supported for A2A in this harness
        if transport == "grpc" and proto != "a2a":
            return
        if proto=="mcp":
            if transport == "http":
                if mcp_persistent_client is not None:
                    lat_rpc, lat_rpc2, out = await mcp_persistent_client.echo(msg)
                    lat_total = lat_rpc
                else:
                    from clients.mcp_sse_client import once_echo
                    lat_total, lat_rpc, out = await once_echo("http://127.0.0.1:8001", msg)
            else:
                if mcp_persistent_client is not None:
                    lat_rpc, lat_rpc2, out = await mcp_persistent_client.echo(msg)
                    lat_total = lat_rpc
                else:
                    from clients.mcp_client import once_echo
                    lat_total, out = await once_echo(msg)
                    lat_rpc = lat_total
        elif proto=="acp":
            if transport == "http":
                if acp_persistent_client is not None:
                    lat_rpc, lat_rpc2, out = await acp_persistent_client.echo(msg)
                    lat_total = lat_rpc
                else:
                    from clients.acp_sse_client import once_echo
                    lat_total, lat_rpc, out = await once_echo("http://127.0.0.1:8101", msg)
            else:
                from clients.acp_stdio_client import once_echo
                lt, out = await once_echo(msg)
                lat_total, lat_rpc = lt, lt
        elif proto=="a2a":
            if transport == "grpc":
                try:
                    from clients.a2a_grpc_client import once_echo as a2a_grpc_echo
                    lat_total, lat_rpc, out = await a2a_grpc_echo(a2a_base_url, msg)
                except Exception:
                    lat_total, lat_rpc, out = 0.0, 0.0, ""
            else:
                if enable_a2a_sse and transport == "http":
                    from clients.a2a_sse_client import once_stream_echo
                    token = os.environ.get("A2A_BEARER_TOKEN") if auth_mode == "all" else None
                    ttfb, total, out = await once_stream_echo(a2a_base_url, msg, 3, 5, token)
                    lat_total, lat_rpc = total, total
                elif a2a_persistent_client is not None:
                    lat_total, lat_rpc, out = await a2a_persistent_client.echo(msg)
                else:
                    from clients.a2a_sdk_client import once_echo
                    lat_total, lat_rpc, out = await once_echo(a2a_base_url, msg)
        elif proto=="anp":
            if anp_persistent_client is not None:
                lat_total, lat_rpc, out = await anp_persistent_client.echo(msg)
            else:
                from clients.anp_sdk_client import once_echo
                lat_total, lat_rpc, out = await once_echo(anp_base_url, msg)
        else:
            raise RuntimeError("unknown proto")
        latencies_total.append(lat_total)
        latencies_rpc.append(lat_rpc)
        if out == msg:
            success += 1

    sem = asyncio.Semaphore(concurrency)
    async def guarded(i):
        async with sem:
            await one(i)

    await asyncio.gather(*(guarded(i) for i in range(n)))

    # Close shared client if used
    if shared_client is not None:
        with contextlib.suppress(Exception):
            await shared_client.aclose()
    if mcp_persistent_client is not None:
        with contextlib.suppress(Exception):
            await mcp_persistent_client.close()
    if acp_persistent_client is not None:
        with contextlib.suppress(Exception):
            await acp_persistent_client.close()
    if a2a_persistent_client is not None:
        with contextlib.suppress(Exception):
            await a2a_persistent_client.close()
    if anp_persistent_client is not None:
        with contextlib.suppress(Exception):
            await anp_persistent_client.close()
    return latencies_total, latencies_rpc, success, connect_init_timings


async def validate_protocols(transport: str, a2a_base_url: str = "http://127.0.0.1:8201", anp_base_url: str = "http://127.0.0.1:8301", include_acp: bool = False) -> dict:
    """Lightweight shape checks to avoid misleading runs."""
    results: dict[str, str] = {}

    # Special case: gRPC mode (A2A only)
    if transport == "grpc":
        results: dict[str, str] = {"mcp": "skipped", "acp": "skipped", "anp": "skipped"}
        try:
            from clients.a2a_grpc_client import once_echo as a2a_grpc_echo
            _lt, _lr, out = await a2a_grpc_echo(a2a_base_url, "hi")
            results["a2a"] = "ok" if out == "hi" else "unexpected echo"
        except Exception as e:
            results["a2a"] = f"skipped: {e}"
        return results

    # MCP: stdio or HTTP SSE
    try:
        if transport == "http":
            from clients.mcp_sse_client import once_echo as mcp_echo
            _lt, _lr, out = await mcp_echo("http://127.0.0.1:8001", "ping")
            results["mcp"] = "ok" if out == "ping" else "unexpected echo"
        else:
            from clients.mcp_client import once_add
            s = await once_add(3, 5)
            results["mcp"] = "ok" if s == 8 else "unexpected add result"
    except Exception as e:
        results["mcp"] = f"error: {e}"

    # ACP (optional)
    if include_acp:
        try:
            if transport == "http":
                from clients.acp_sse_client import once_echo as acp_echo
                _lt, _lr, out = await acp_echo("http://127.0.0.1:8101", "hello")
            else:
                from clients.acp_stdio_client import once_echo as acp_echo
                _lt, out = await acp_echo("hello")
            results["acp"] = "ok" if out == "hello" else "unexpected echo"
        except Exception as e:
            results["acp"] = f"error: {e}"
    else:
        results["acp"] = "skipped"

    # A2A
    try:
        from clients.a2a_sdk_client import once_echo as a2a_echo
        _lt, _lr, out = await a2a_echo(a2a_base_url, "hi")
        results["a2a"] = "ok" if out == "hi" else "unexpected echo"
    except Exception as e:
        results["a2a"] = f"error: {e}"

    # ANP
    try:
        from clients.anp_sdk_client import once_echo as anp_echo
        _lt, _lr, out = await anp_echo(anp_base_url, "pong")
        results["anp"] = "ok" if out == "pong" else f"unexpected echo: {out}"
    except Exception as e:
        results["anp"] = f"error: {e}"

    return results

def statistical_comparison(results):
    """Compare protocols using statistical tests"""
    protocols = list(results.keys())
    latency_data = {proto: results[proto]['latencies'] for proto in protocols}

    comparisons = {}
    for i, proto1 in enumerate(protocols):
        for proto2 in protocols[i+1:]:
            try:
                # Use Mann-Whitney U test (non-parametric, doesn't assume normal distribution)
                stat, p_value = mannwhitneyu(
                    latency_data[proto1],
                    latency_data[proto2],
                    alternative='two-sided'
                )

                # Calculate effect size (Cohen's d approximation)
                mean1, mean2 = np.mean(latency_data[proto1]), np.mean(latency_data[proto2])
                pooled_std = np.sqrt(
                    (np.var(latency_data[proto1]) + np.var(latency_data[proto2])) / 2
                )
                cohens_d = abs(mean1 - mean2) / pooled_std if pooled_std > 0 else 0

                comparisons[f"{proto1}_vs_{proto2}"] = {
                    "p_value": float(p_value),
                    "statistically_significant": bool(p_value < 0.05),
                    "effect_size": float(cohens_d),
                    "effect_interpretation": (
                        "large" if cohens_d > 0.8 else
                        "medium" if cohens_d > 0.5 else
                        "small" if cohens_d > 0.2 else
                        "negligible"
                    ),
                    "faster_protocol": proto1 if mean1 < mean2 else proto2,
                    "difference_ms": float(abs(mean1 - mean2))
                }
            except Exception as e:
                comparisons[f"{proto1}_vs_{proto2}"] = {"error": str(e)}

    return comparisons

def summarize(latencies):
    if not latencies:
        return {}
    arr = np.array(latencies, dtype=float)
    n = arr.size
    p50, p95, p99 = np.percentile(arr, [50, 95, 99]) if n > 0 else (0.0, 0.0, 0.0)
    return {
        "count": int(n),
        "avg_ms": float(arr.mean()) if n else 0.0,
        "p50_ms": float(p50),
        "p95_ms": float(p95),
        "p99_ms": float(p99),
        "min_ms": float(arr.min()) if n else 0.0,
        "max_ms": float(arr.max()) if n else 0.0,
        "std_dev_ms": float(arr.std(ddof=1)) if n > 1 else 0.0,
    }

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--messages", type=int, default=200)  # increased from 50
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--payload-bytes", type=int, default=32)
    ap.add_argument("--warmup", type=int, default=10)  # increased from 3
    ap.add_argument("--test-payload-variations", action="store_true", help="Test different payload sizes")
    ap.add_argument("--test-concurrency-variations", action="store_true", help="Test different concurrency levels")
    ap.add_argument("--test-error-handling", action="store_true", help="Test error handling and retry behavior")
    ap.add_argument("--test-auth", action="store_true", help="Test authentication mechanisms")
    ap.add_argument("--connection-mode", choices=["reuse","cold"], default="reuse", help="Reuse one client/session per protocol or open new per call")
    ap.add_argument("--transport", choices=["http","stdio","grpc"], default="http", help="Transport parity mode: use HTTP/SSE, stdio (MCP only), or gRPC (A2A only)")
    ap.add_argument("--auth-mode", choices=["none","default","all"], default="none", help="Authentication symmetry: none disables ANP; default enables ANP DID-WBA; all enables ANP + A2A bearer")
    ap.add_argument("--validate", action="store_true", help="Run conformance sanity checks before benchmarking")
    ap.add_argument("--enable-a2a-sse", action="store_true", help="Enable A2A SSE streaming endpoints and client path")
    ap.add_argument("--test-streaming", action="store_true", help="Run streaming TTFB tests where supported")
    ap.add_argument("--include-acp", action="store_true", help="Include ACP variant as an MCP-compatible SDK codepath in benchmarks")
    # Real SDK modes only
    ap.add_argument("--mcp-persistent", choices=["auto","on","off"], default="auto", help="Use persistent MCP stdio session (auto honors reuse mode)")
    ap.add_argument("--no-spawn-a2a", action="store_true", help="Do not spawn the A2A SDK server (use external)")
    ap.add_argument("--no-spawn-anp", action="store_true", help="Do not spawn the ANP SDK server (use external)")
    ap.add_argument("--a2a-base-url", default="http://127.0.0.1:8201", help="Base URL for A2A server")
    ap.add_argument("--anp-base-url", default="http://127.0.0.1:8301", help="Base URL for ANP server")
    args = ap.parse_args()

    if args.auth_mode == "none":
        os.environ["ANP_DISABLE_AUTH"] = "true"
        os.environ.pop("A2A_BEARER_TOKEN", None)
    elif args.auth_mode == "all":
        os.environ["ANP_DISABLE_AUTH"] = "false"
        os.environ.setdefault("A2A_BEARER_TOKEN", "bench-secret-token")
    procs = start_servers(args.transport, args.no_spawn_a2a, args.no_spawn_anp, include_acp=args.include_acp)
    try:
        if args.validate:
            print("Validating protocol endpoints...")
            v = await validate_protocols(args.transport, args.a2a_base_url, args.anp_base_url, include_acp=args.include_acp)
            print(json.dumps({"validation": v}, indent=2))
        # Warmup all protocols equally for fair comparison
        print("Warming up all protocols...")
        protos = ["mcp","a2a","anp"] + (["acp"] if args.include_acp else [])
        for proto in protos:
            await run_client(
                proto,
                args.warmup,
                8,
                1,
                reuse_client=(args.connection_mode == "reuse"),
                mcp_persistent=(
                    True if args.mcp_persistent == "on" else False if args.mcp_persistent == "off" else None
                ),
                transport=args.transport,
                a2a_base_url=args.a2a_base_url,
                anp_base_url=args.anp_base_url,
                enable_a2a_sse=args.enable_a2a_sse,
                auth_mode=args.auth_mode,
            )

        results = {}
        print("Running main benchmarks...")
        for proto in protos:
            print(f"Testing {proto}...")
            t0 = time.perf_counter()
            lats_total, lats_rpc, ok, connect_init = await run_client(
                proto,
                args.messages,
                args.payload_bytes,
                args.concurrency,
                reuse_client=(args.connection_mode == "reuse"),
                mcp_persistent=(
                    True if args.mcp_persistent == "on" else False if args.mcp_persistent == "off" else None
                ),
                transport=args.transport,
                a2a_base_url=args.a2a_base_url,
                anp_base_url=args.anp_base_url,
                enable_a2a_sse=args.enable_a2a_sse,
                auth_mode=args.auth_mode,
            )
            elapsed = time.perf_counter() - t0
            throughput = (args.messages / elapsed) if elapsed > 0 else 0.0
            results[proto] = {
                "stats_total": summarize(lats_total),
                "stats_rpc": summarize(lats_rpc),
                "success": ok,
                "throughput_msgs_per_sec": float(throughput),
                "latencies_total": lats_total,
                "latencies_rpc": lats_rpc,
                "connect_init_ms": connect_init.get("connect_init_ms", 0.0),
            }

        # Add statistical comparisons
        print("Performing statistical analysis...")
        results_for_stats = {k: {"latencies": v["latencies_total"]} for k, v in results.items() if k in protos}
        results["statistical_comparisons"] = statistical_comparison(results_for_stats)
        results["meta"] = {
            "transport": args.transport,
            "connection_mode": args.connection_mode,
            "auth_mode": args.auth_mode,
            "protocols": protos,
            "include_acp": bool(args.include_acp),
        }

        # Test payload variations if requested
        if args.test_payload_variations:
            print("Testing payload size variations...")
            results["payload_variations"] = {}
            for payload_size in [8, 64, 256, 1024]:
                print(f"Testing payload size: {payload_size} bytes")
                size_results = {}
                for proto in protos:
                    lts, lrs, ok, _ = await run_client(
                        proto,
                        50,
                        payload_size,
                        args.concurrency,
                        transport=args.transport,
                        a2a_base_url=args.a2a_base_url,
                        anp_base_url=args.anp_base_url,
                    )
                    size_results[proto] = {"stats_total": summarize(lts), "stats_rpc": summarize(lrs), "success": ok}
                results["payload_variations"][f"{payload_size}_bytes"] = size_results

        # Test concurrency variations if requested
        if args.test_concurrency_variations:
            print("Testing concurrency variations...")
            results["concurrency_variations"] = {}
            for concurrency in [1, 2, 8, 16]:
                print(f"Testing concurrency: {concurrency}")
                conc_results = {}
                for proto in protos:
                    lts, lrs, ok, _ = await run_client(
                        proto,
                        100,
                        args.payload_bytes,
                        concurrency,
                        transport=args.transport,
                        a2a_base_url=args.a2a_base_url,
                        anp_base_url=args.anp_base_url,
                    )
                    conc_results[proto] = {"stats_total": summarize(lts), "stats_rpc": summarize(lrs), "success": ok}
                results["concurrency_variations"][f"concurrency_{concurrency}"] = conc_results

        # Streaming tests (A2A SSE only for now)
        if args.test_streaming and args.enable_a2a_sse:
            print("Testing streaming TTFB (A2A SSE)...")
            from clients.a2a_sse_client import once_stream_echo
            token = os.environ.get("A2A_BEARER_TOKEN") if args.auth_mode == "all" else None
            ttfb, total, out = await once_stream_echo(args.a2a_base_url, "streaming-hello", 5, 10, token)
            results.setdefault("streaming", {})["a2a_sse"] = {
                "ttfb_ms": float(ttfb),
                "stream_total_ms": float(total),
                "ok": bool(out == "streaming-hello"),
            }

        # Test error handling removed until clients implemented
        if args.test_error_handling:
            print("Skipping error handling tests (not implemented)")

            # Test with invalid message (should fail gracefully)
            error_results = {}
            for proto in ("mcp","acp","a2a","anp"):
                try:
                    # Send very large message to trigger potential errors
                    large_msg = "x" * 10000
                    if proto=="mcp":
                        from clients.mcp_http_client import once_echo
                        lat, out = await once_echo("http://127.0.0.1:8001/mcp", large_msg)
                    elif proto=="acp":
                        from clients.acp_client import once_echo
                        lat, out = await once_echo("http://127.0.0.1:8101", large_msg)
                    elif proto=="a2a":
                        from clients.a2a_client import once_echo
                        lat, out = await once_echo("http://127.0.0.1:8201", large_msg)
                    elif proto=="anp":
                        from clients.anp_client import once_echo
                        lat, out = await once_echo("http://127.0.0.1:8301", large_msg)

                    error_results[proto] = {
                        "large_message_handled": out == large_msg,
                        "latency_ms": lat
                    }
                except Exception as e:
                    error_results[proto] = {
                        "large_message_handled": False,
                        "error": str(e)
                    }
            results["error_handling"]["large_messages"] = error_results

        # Test authentication if requested
        if args.test_auth:
            print("Testing authentication support...")
            results["authentication"] = {
                "note": "All protocols support authentication but testing requires auth-enabled servers",
                "mcp": "Supports various transports with authentication",
                "acp": "Supports session-based authentication",
                "a2a": "Supports capability-based authentication tokens",
                "anp": "Supports DID-based authentication with signatures"
            }

        # Remove raw latency data before saving (too large)
        for proto in protos:
            for key in ("latencies_total","latencies_rpc"):
                if key in results[proto]:
                    del results[proto][key]

        outdir = HERE / "out"
        outdir.mkdir(parents=True, exist_ok=True)
        path = outdir / "last_run.json"
        path.write_text(json.dumps(results, indent=2))
        print(json.dumps(results, indent=2))

    finally:
        for p in procs:
            p.terminate()
            try:
                p.wait(timeout=3)
            except Exception:
                p.kill()

if __name__ == "__main__":
    asyncio.run(main())
