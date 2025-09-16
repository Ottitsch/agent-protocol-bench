ACP Implementation Note (Deprecated as separate protocol)

- Upstream status (per BeeAI announcement): “ACP is now part of A2A under the Linux Foundation.” This project no longer treats ACP as a distinct standardized protocol.
- The `acp` Python SDK used here has historically mirrored MCP transport shapes (stdio, SSE) and concepts to offer an alternate code path. In this repository, ACP remains available only as an optional MCP‑compatible variant for transport parity experiments.
- By default ACP is excluded from benchmarks. You can include it with `--include-acp` to run side‑by‑side with MCP/A2A/ANP, but interpret the results as a codepath variant rather than a separate protocol.

