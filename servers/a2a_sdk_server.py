from fastapi import FastAPI, Request, Header, HTTPException
import uvicorn
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers.request_handler import RequestHandler
from a2a.server.context import ServerCallContext
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    HTTPAuthSecurityScheme,
    Message,
    MessageSendParams,
    Role,
    Part,
    TextPart,
    Task,
    TaskIdParams,
    TaskPushNotificationConfig,
    TaskQueryParams,
)
from typing import AsyncGenerator
from collections.abc import AsyncGenerator as ABCAsyncGenerator
from datetime import datetime, timezone
import uuid
import os
import asyncio
from sse_starlette.sse import EventSourceResponse


class EchoRequestHandler(RequestHandler):
    async def on_get_task(
        self, params: TaskQueryParams, context: ServerCallContext | None = None
    ) -> Task | None:
        return None

    async def on_cancel_task(
        self, params: TaskIdParams, context: ServerCallContext | None = None
    ) -> Task | None:
        return None

    async def on_message_send(
        self, params: MessageSendParams, context: ServerCallContext | None = None
    ) -> Task | Message:
        # Expect a single-part text message; echo back or perform add if pattern matches
        text = ""
        if params.message and params.message.parts:
            for p in params.message.parts:
                if isinstance(p.root, TextPart):
                    text = p.root.text or ""
                    break
        result = text
        # Support simple add: "ADD a b"
        if text.upper().startswith("ADD "):
            try:
                _, a_str, b_str = text.split()
                result = str(int(a_str) + int(b_str))
            except Exception:
                result = "0"
        return Message(
            role=Role.agent,
            parts=[Part(TextPart(text=result))],
            message_id=str(uuid.uuid4()),
        )

    async def on_message_send_stream(
        self, params: MessageSendParams, context: ServerCallContext | None = None
    ) -> ABCAsyncGenerator:
        # For simplicity, not implementing streaming; fall back to non-streaming
        if False:
            yield  # type: ignore
        raise NotImplementedError

    async def on_set_task_push_notification_config(
        self,
        params: TaskPushNotificationConfig,
        context: ServerCallContext | None = None,
    ) -> TaskPushNotificationConfig:
        return params

    async def on_get_task_push_notification_config(
        self,
        params: TaskIdParams | TaskQueryParams,
        context: ServerCallContext | None = None,
    ) -> TaskPushNotificationConfig:
        return TaskPushNotificationConfig(task_id=params.task_id, config={})  # type: ignore

    async def on_resubscribe_to_task(
        self, params: TaskIdParams, context: ServerCallContext | None = None
    ) -> ABCAsyncGenerator:
        if False:
            yield  # type: ignore
        raise NotImplementedError

    async def on_list_task_push_notification_config(
        self, params, context: ServerCallContext | None = None
    ) -> list[TaskPushNotificationConfig]:
        return []

    async def on_delete_task_push_notification_config(
        self, params, context: ServerCallContext | None = None
    ) -> None:
        return None


def build_agent_card(base_url: str) -> AgentCard:
    # Simple HTTP Bearer scheme (optional use via env)
    security = [{"bearer": []}]
    security_schemes = {
        "bearer": HTTPAuthSecurityScheme(type="http", scheme="bearer"),
    }
    return AgentCard(
        url=f"{base_url}/a2a/jsonrpc",
        preferred_transport="JSONRPC",
        version="1.0.0",
        protocol_version="0.3.0",
        name="A2A Echo Agent",
        description="Echo messages and simple add via A2A",
        provider=AgentProvider(organization="Benchmark", url=base_url),
        security=security,
        security_schemes=security_schemes,
        capabilities=AgentCapabilities(),
        skills=[
            AgentSkill(
                id="echo",
                name="Echo",
                description="Echo text messages",
                tags=["echo"],
            ),
            AgentSkill(
                id="add",
                name="Add",
                description="Add two integers",
                tags=["math"],
            ),
        ],
        default_input_modes=[],
        default_output_modes=[],
        supports_authenticated_extended_card=False,
        additional_interfaces=[
            AgentInterface(transport="HTTP+JSON", url=f"{base_url}/a2a/jsonrpc")
        ],
    )


def create_app() -> FastAPI:
    base_url = "http://127.0.0.1:8201"
    card = build_agent_card(base_url)
    handler = EchoRequestHandler()
    app_builder = A2AFastAPIApplication(agent_card=card, http_handler=handler)
    app = app_builder.build(agent_card_url="/a2a/agent-card", rpc_url="/a2a/jsonrpc")

    # Optional bearer token auth (enabled when A2A_BEARER_TOKEN is set)
    token_env = os.environ.get("A2A_BEARER_TOKEN")

    @app.middleware("http")
    async def bearer_auth_middleware(request: Request, call_next):
        if token_env and request.url.path.startswith("/a2a/") and request.url.path.endswith("/jsonrpc"):
            auth = request.headers.get("authorization") or request.headers.get("Authorization")
            if not auth or not auth.lower().startswith("bearer ") or auth.split(" ", 1)[1] != token_env:
                raise HTTPException(status_code=401, detail="Unauthorized")
        return await call_next(request)

    # Simple SSE echo for streaming tests
    @app.get("/a2a/sse/echo")
    async def a2a_sse_echo(request: Request, message: str = "hello", chunks: int = 3, delay_ms: int = 5, authorization: str | None = Header(default=None)):
        if token_env:
            if not authorization or not authorization.lower().startswith("bearer ") or authorization.split(" ", 1)[1] != token_env:
                raise HTTPException(status_code=401, detail="Unauthorized")

        async def event_generator():
            # Stream message in N chunks to simulate streaming
            part_len = max(1, len(message) // max(1, chunks))
            for i in range(chunks):
                if await request.is_disconnected():
                    break
                start = i * part_len
                data = message[start : start + part_len] if i < chunks - 1 else message[start:]
                yield {"event": "message", "data": data}
                await asyncio.sleep(max(0, delay_ms) / 1000)
        return EventSourceResponse(event_generator())

    return app


async def main():
    app = create_app()
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8201, log_level="error")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
