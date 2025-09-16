import asyncio
import httpx
import time
import json
import argparse
from pathlib import Path
from agent_connect.authentication import DIDWbaAuthHeader


BASE = Path(__file__).resolve().parent.parent
DID_PATH = BASE / "config" / "anp_did" / "client" / "did.json"
PRIV_KEY_PATH = BASE / "config" / "anp_did" / "client" / "key-1_private.pem"


class ANPClientPersistent:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._auth: DIDWbaAuthHeader | None = None
        self._sender_did: str | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient()
        self._auth = DIDWbaAuthHeader(str(DID_PATH), str(PRIV_KEY_PATH))
        self._sender_did = json.loads(DID_PATH.read_text())["id"]

    async def echo(self, message: str) -> tuple[float, float, str]:
        if not (self._client and self._auth and self._sender_did):
            raise RuntimeError("client not started")
        headers = self._auth.get_auth_header(self._base_url)
        payload = {
            "@context": [
                "https://schema.org/",
                "https://agentnetworkprotocol.com/context/v1",
            ],
            "@type": "anp:Message",
            "@id": "urn:uuid:bench-echo",
            "anp:sender": self._sender_did,
            "anp:receiver": "did:wba:localhost:anp-server",
            "schema:text": {"@type": "anp:EchoRequest", "anp:message": message},
            "schema:dateCreated": time.time(),
        }
        t_rpc0 = time.perf_counter()
        r = await self._client.post(f"{self._base_url}/anp/messages", json=payload, headers=headers)
        r.raise_for_status()
        t_rpc1 = time.perf_counter()
        data = r.json()
        content = data.get("schema:text", {})
        out = content.get("anp:originalMessage", "") if isinstance(content, dict) else ""
        return (t_rpc1 - t_rpc0) * 1000, (t_rpc1 - t_rpc0) * 1000, out

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
            self._auth = None
            self._sender_did = None


async def once_echo(base_url: str, message: str) -> tuple[float, float, str]:
    try:
        auth = DIDWbaAuthHeader(str(DID_PATH), str(PRIV_KEY_PATH))
        headers = auth.get_auth_header(base_url)
        payload = {
            "@context": [
                "https://schema.org/",
                "https://agentnetworkprotocol.com/context/v1",
            ],
            "@type": "anp:Message",
            "@id": "urn:uuid:bench-echo",
            "anp:sender": json.load(open(DID_PATH, "r"))["id"],
            "anp:receiver": "did:wba:localhost:anp-server",
            "schema:text": {"@type": "anp:EchoRequest", "anp:message": message},
            "schema:dateCreated": time.time(),
        }
        async with httpx.AsyncClient() as c:
            t0 = time.perf_counter()
            r = await c.post(f"{base_url}/anp/messages", json=payload, headers=headers)
            r.raise_for_status()
            t1 = time.perf_counter()
            data = r.json()
            content = data.get("schema:text", {})
            out = content.get("anp:originalMessage", "") if isinstance(content, dict) else ""
            return (t1 - t0) * 1000, (t1 - t0) * 1000, out
    except Exception as e:
        print(f"ANP SDK echo failed: {e}")
        return 0.0, ""


async def once_add(base_url: str, a: int, b: int) -> int:
    auth = DIDWbaAuthHeader(str(DID_PATH), str(PRIV_KEY_PATH))
    headers = auth.get_auth_header(base_url)
    payload = {
        "@context": [
            "https://schema.org/",
            "https://agentnetworkprotocol.com/context/v1",
        ],
        "@type": "anp:Message",
        "@id": "urn:uuid:bench-add",
        "anp:sender": json.load(open(DID_PATH, "r"))["id"],
        "anp:receiver": "did:wba:localhost:anp-server",
        "schema:text": {"@type": "anp:ArithmeticRequest", "anp:a": a, "anp:b": b},
        "schema:dateCreated": time.time(),
    }
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{base_url}/anp/messages", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json().get("schema:text", {})
        return int(data.get("anp:result", 0)) if isinstance(data, dict) else 0


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8301")
    ap.add_argument("--message", default="hello")
    args = ap.parse_args()
    lat_total, lat_rpc, out = await once_echo(args.base_url, args.message)
    print(json.dumps({"latency_total_ms": lat_total, "latency_rpc_ms": lat_rpc, "echo": out}))


if __name__ == "__main__":
    asyncio.run(main())
