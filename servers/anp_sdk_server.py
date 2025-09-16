from fastapi import FastAPI, Header, HTTPException, Request
import uvicorn
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import json
from pathlib import Path
import os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# AgentConnect DID WBA verifier
from agent_connect.authentication import DidWbaVerifier, DidWbaVerifierConfig
import agent_connect.authentication.did_wba_verifier as did_wba_verifier
import agent_connect.authentication.did_wba as did_wba


app = FastAPI(title="ANP SDK Server (DID-WBA)")

BASE = Path(__file__).resolve().parent.parent
DID_DIR = BASE / "config" / "anp_did" / "client"
DID_PATH = DID_DIR / "did.json"
PRIV_KEY_PATH = DID_DIR / "key-1_private.pem"


def ensure_client_did_files() -> dict:
    DID_DIR.mkdir(parents=True, exist_ok=True)
    if DID_PATH.exists() and PRIV_KEY_PATH.exists():
        return json.loads(DID_PATH.read_text())
    # Create a client DID for localhost
    domain = os.environ.get("ANP_CLIENT_DOMAIN", "localhost")
    # allow embedding path segments to distinguish clients
    did_doc, keys = did_wba.create_did_wba_document(
        hostname=domain, port=None, path_segments=["client", "benchmark"]
    )
    # Write DID doc and private key
    DID_PATH.write_text(json.dumps(did_doc, indent=2))
    priv_pem, pub_pem = keys["key-1"]
    PRIV_KEY_PATH.write_bytes(priv_pem)
    return did_doc


def create_jwt_keys() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


# Monkeypatch resolver to return our local client DID document for tests
def install_local_resolver(local_doc: dict):
    async def _resolve(did: str) -> dict:
        # Return our local DID document if id matches
        if local_doc.get("id") == did:
            return local_doc
        # Fallback to original resolver (likely to fail on localhost without HTTPS)
        return None

    # Patch both the module function and the imported symbol in verifier module
    did_wba.resolve_did_wba_document = _resolve  # type: ignore
    did_wba_verifier.resolve_did_wba_document = _resolve  # type: ignore


@app.on_event("startup")
async def startup():
    # Dev mode local resolver can be disabled via env
    dev_local_resolver = os.environ.get("ANP_DEV_LOCAL_RESOLVER", "true").lower() in ("1","true","yes")
    client_doc = ensure_client_did_files()
    if dev_local_resolver:
        install_local_resolver(client_doc)
    priv, pub = create_jwt_keys()
    app.state.verifier = DidWbaVerifier(
        DidWbaVerifierConfig(
            jwt_private_key=priv, jwt_public_key=pub, jwt_algorithm="RS256"
        )
    )
    # Prepare server DID doc for discovery
    server_domain = os.environ.get("ANP_SERVER_DOMAIN", "did:wba:localhost:anp-server")
    app.state.server_did = {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": server_domain,
        "verificationMethod": [
            {
                "id": f"{server_domain}#key-1",
                "type": "Ed25519VerificationKey2020",
                "controller": server_domain,
                "publicKeyMultibase": "zDemoPublicKey",
            }
        ],
        "authentication": [f"{server_domain}#key-1"],
        "service": [
            {
                "id": f"{server_domain}#agent-service",
                "type": "AgentService",
                "serviceEndpoint": "http://127.0.0.1:8301/anp",
            }
        ],
        "created": datetime.now(timezone.utc).isoformat(),
        "updated": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/.well-known/did.json")
async def get_did():
    return app.state.server_did


@app.get("/anp/agent-description")
async def agent_description():
    return {
        "@context": [
            "https://schema.org/",
            "https://agentnetworkprotocol.com/context/v1",
        ],
        "@type": "anp:Agent",
        "@id": app.state.server_did["id"],
        "schema:name": "ANP Echo Agent (SDK)",
        "schema:description": "Echo and add with DID-WBA verification",
        "anp:version": "1.0.0",
        "anp:capabilities": [
            {"anp:name": "echo"},
            {"anp:name": "arithmetic_add"},
        ],
        "anp:supportedProtocols": ["anp:json-ld"],
        "anp:endpoints": {"messages": "/anp/messages"},
        "anp:didDocument": "/.well-known/did.json",
        "schema:dateCreated": datetime.now(timezone.utc).isoformat(),
        "schema:dateModified": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/anp/messages")
async def anp_messages(
    message: Dict[str, Any], authorization: Optional[str] = Header(None), request: Request = None
):
    # Optional auth disable for symmetric baseline
    disable_auth = os.environ.get("ANP_DISABLE_AUTH", "false").lower() in ("1", "true", "yes")
    if not disable_auth:
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing Authorization header")
        # Verify DID WBA or Bearer
        try:
            # Use the request hostname (no port) as domain to match client header
            domain = request.url.hostname if request and request.url else "localhost"
            _ = await app.state.verifier.verify_auth_header(authorization, domain=domain)
        except Exception as e:
            raise HTTPException(status_code=getattr(e, "status_code", 401), detail=str(e))

    content = message.get("schema:text", {})
    response_content: Dict[str, Any]
    if isinstance(content, dict) and content.get("@type") == "anp:EchoRequest":
        response_content = {
            "@type": "anp:EchoResponse",
            "anp:originalMessage": content.get("anp:message", ""),
        }
    elif isinstance(content, dict) and content.get("@type") == "anp:ArithmeticRequest":
        a = int(content.get("anp:a", 0))
        b = int(content.get("anp:b", 0))
        response_content = {
            "@type": "anp:ArithmeticResponse",
            "anp:result": a + b,
        }
    else:
        response_content = {"@type": "anp:TextResponse", "schema:text": str(content)}

    return {
        "@context": [
            "https://schema.org/",
            "https://agentnetworkprotocol.com/context/v1",
        ],
        "@type": "anp:Message",
        "@id": f"urn:uuid:{uuid.uuid4()}",
        "anp:sender": app.state.server_did["id"],
        "anp:receiver": message.get("anp:sender", "did:wba:client:unknown"),
        "schema:text": response_content,
        "schema:dateCreated": datetime.now(timezone.utc).isoformat(),
    }


async def main():
    # Optional TLS config via env: ANP_SSL_CERT, ANP_SSL_KEY
    ssl_cert = os.environ.get("ANP_SSL_CERT")
    ssl_key = os.environ.get("ANP_SSL_KEY")
    use_ssl = bool(ssl_cert and ssl_key)
    config = uvicorn.Config(
        app=app,
        host=os.environ.get("ANP_HOST", "127.0.0.1"),
        port=int(os.environ.get("ANP_PORT", "8301")),
        log_level="error",
        ssl_certfile=ssl_cert if use_ssl else None,
        ssl_keyfile=ssl_key if use_ssl else None,
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
