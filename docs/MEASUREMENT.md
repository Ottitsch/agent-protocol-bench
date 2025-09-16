Measurement Methodology

- Transport parity
  - Default runs use SSE for MCP/ACP and HTTP JSON for A2A/ANP.
  - A fallback stdio mode is available via `--transport stdio` for MCP/ACP only.
  - Optional A2A SSE is available when `--enable-a2a-sse` is set; this enables streaming tests.
  - A `--transport grpc` mode (A2A only) is exposed; others are reported as skipped.
  - ACP is optional and excluded by default; include with `--include-acp` if you want to compare the MCP‑compatible variant.

- Connection reuse parity
  - `--connection-mode reuse` maintains a single persistent client/session per protocol:
    - MCP/ACP: persistent SSE sessions.
    - A2A: persistent SDK client; optional SSE persistent connection for streaming tests.
    - ANP: persistent `httpx.AsyncClient` with cached DID/auth header builder.
  - `--connection-mode cold` creates a fresh client/session per call.

- Timing windows
  - Timing is reported for:
    - `connect_ms` and `init_ms` (where applicable) for first-use setup.
    - `latency_total_ms`: end-to-end per-call, including any connect/init work in cold mode.
    - `latency_rpc_ms`: RPC-only portion (post-init call path).
    - For streaming tests: `ttfb_ms` (time-to-first-byte/event) and `stream_total_ms`.
  - Summaries are reported for both `stats_total` and `stats_rpc`.

- Authentication symmetry
  - `--auth-mode none` disables ANP verification (`ANP_DISABLE_AUTH=true`).
  - `--auth-mode default` enables ANP DID-WBA verification.
  - `--auth-mode all` enables ANP DID-WBA and A2A bearer token checks; MCP/ACP remain unauth due to SDK transport limitations.

- Statistical comparison
  - Mann-Whitney U is applied to total latency distributions by protocol pairs; results include p-value and effect size.

- Outputs
  - `benchmarks/out/last_run.json` contains per-protocol summaries and statistical comparisons; raw latency arrays are omitted to keep file size reasonable.
