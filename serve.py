"""Despliegue del agente con Ray Serve. Endpoint /chat para conversación."""
import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from ray import serve

from agent.orchestrator import chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/chat")
async def chat_endpoint(request: Request):
    """POST con body: {"message": "...", "thread_id": "opcional"}. Devuelve la respuesta en texto."""
    body = await request.json()
    user_message = body.get("message", "")
    thread_id = body.get("thread_id") or request.headers.get("X-Thread-Id") or str(uuid4())

    async def stream() -> AsyncGenerator[str, None]:
        async for chunk in chat(user_message, thread_id):
            yield chunk

    return StreamingResponse(
        stream(),
        media_type="text/plain; charset=utf-8",
        headers={"X-Thread-Id": thread_id},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@serve.deployment(ray_actor_options={"num_cpus": 0.5})
@serve.ingress(app)
class AgenteAutomotrizDeployment:
    pass


deployment = AgenteAutomotrizDeployment.bind()
