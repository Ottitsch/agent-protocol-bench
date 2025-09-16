Agent Protocol Benchmark

**Purpose**
- Compare agent protocol stacks under controlled microbenchmarks (echo/add), with explicit transport and connection parity.
- Measure latency, throughput, connect/init overhead, and optional streaming time‑to‑first‑byte (TTFB).

**Protocols**
- MCP (Model Context Protocol)
- A2A (Agent‑to‑Agent)
- ANP (Agent Network Protocol; JSON‑LD; optional DID‑WBA auth)
- Optional: ACP variant (MCP‑compatible SDK) via `--include-acp` (not a separate standardized protocol)

**What’s Measured**
- Latency windows per protocol:
  - `latency_total_ms` (end‑to‑end per call; includes connect/init in cold mode)
  - `latency_rpc_ms` (post‑init call path)
  - `connect_init_ms` (first‑use connect + init time in reuse mode)
- Throughput (messages/sec) for the batch
- Non‑parametric stats: Mann‑Whitney U with effect size on total latency
- Optional streaming (A2A SSE): `ttfb_ms`, `stream_total_ms`

**Transports**
- Default transport parity:
  - MCP: SSE (HTTP)
  - A2A: HTTP JSON (JSON‑RPC)
  - ANP: HTTP JSON (JSON‑LD)
  - ACP: SSE (HTTP) when included
- Modes:
  - `--transport http` (default)
  - `--transport stdio` (MCP only; ACP optional when included)
  - `--transport grpc` (A2A only; optional and skipped if unavailable)
- Streaming (A2A SSE): `--enable-a2a-sse` + `--test-streaming`

**Authentication**
- `--auth-mode none`: disables ANP auth; no A2A Bearer token (baseline)
- `--auth-mode default`: enables ANP DID‑WBA only
- `--auth-mode all`: enables ANP DID‑WBA and A2A Bearer token (set via `A2A_BEARER_TOKEN`)

**Requirements**
- Python 3.10+
- Install deps: `python -m pip install -r requirements.txt`

**Quick Start**
- Validate and benchmark (HTTP, reuse, auth off):
  - Windows: `venv\Scripts\python.exe benchmarks\run_bench.py --validate --transport http --auth-mode none`
  - POSIX: `venv/bin/python benchmarks/run_bench.py --validate --transport http --auth-mode none`
- Streaming and timing breakdowns (A2A SSE):
  - `venv\Scripts\python.exe benchmarks\run_bench.py --transport http --enable-a2a-sse --test-streaming --connection-mode reuse`
- Include ACP variant:
  - `venv\Scripts\python.exe benchmarks\run_bench.py --include-acp --transport http`
- Auth “all” (ANP DID‑WBA + A2A Bearer):
  - `venv\Scripts\python.exe benchmarks\run_bench.py --transport http --auth-mode all`

**CLI Options**
- `--messages N` number of messages per protocol (default 200)
- `--concurrency K` concurrent requests (default 4)
- `--payload-bytes B` echo payload size (default 32)
- `--connection-mode reuse|cold` persistent session vs cold calls (default reuse)
- `--transport http|stdio|grpc` select transport parity (grpc is A2A only)
- `--auth-mode none|default|all` baseline vs ANP only vs ANP + A2A Bearer
- `--enable-a2a-sse` enable A2A SSE endpoints and client path
- `--test-streaming` run SSE streaming TTFB test (A2A)
- `--include-acp` include ACP variant (MCP‑compatible SDK) in runs
- `--validate` run endpoint shape checks before benchmarking

**Outputs**
- `benchmarks/out/last_run.json`: per‑protocol stats, comparisons, and run meta
  - `stats_total`, `stats_rpc`, `throughput_msgs_per_sec`, `success`, `connect_init_ms`
  - `statistical_comparisons` with p‑values and effect sizes
  - `meta`: `transport`, `connection_mode`, `auth_mode`, `protocols`, `include_acp`

**Notes on ACP**
- ACP is not benchmarked as a distinct standardized protocol. Include it as an MCP‑compatible variant for transport parity experiments. See `docs/ACP_NOTES.md`.

**Limitations**
- Microbenchmarks (echo/add) only; not representative of full protocol semantics, large payloads, or complex auth beyond ANP DID‑WBA and A2A Bearer.
- A2A gRPC is optional; the harness marks it “skipped” when unavailable.

**Related Docs**
- Measurement details: `docs/MEASUREMENT.md`
- Change plan / TODOs: `docs/TODO.md`

**Results (Sample Runs)**
- HTTP, auth=none (messages=200, concurrency=4, reuse)
  - mcp: avg_ms 6.615, p50_ms 6.559, p95_ms 7.891, throughput 536.1
  - a2a: avg_ms 3.817, p50_ms 3.723, p95_ms 4.113, throughput 874.2
  - anp: avg_ms 3.860, p50_ms 3.061, p95_ms 3.588, throughput 863.8
  - comparisons: mcp_vs_a2a large effect (p<1e-61), mcp_vs_anp medium effect (p<1e-59), a2a_vs_anp negligible effect (p<1e-51)
  - meta: transport http, connection reuse

- HTTP, auth=none, include_acp (messages=200, concurrency=4, reuse)
  - mcp: avg_ms 6.430, p50_ms 6.275, p95_ms 7.616, throughput 553.4
  - a2a: avg_ms 5.223, p50_ms 4.247, p95_ms 5.692, throughput 667.0
  - anp: avg_ms 3.529, p50_ms 3.454, p95_ms 3.903, throughput 923.2
  - acp (MCP-compatible): avg_ms 5.339, p50_ms 5.196, p95_ms 6.152, throughput 661.3
  - meta: transport http, connection reuse, include_acp true

Notes
- Numbers are from a single host at a point in time; expect hardware/OS variance.
- Auth=all currently enables ANP DID‑WBA; A2A Bearer enforcement is server‑side only in this repo to maintain SDK compatibility.
