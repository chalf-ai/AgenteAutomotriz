"""
App FastAPI para despliegue en Railway (sin Ray).
Expone /health, /chat y preparado para webhook de WhatsApp.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

from config import STOCK_FILE, STOCK_DB_PATH
from stock.repository import StockRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Al arrancar, carga el stock desde el CSV si existe (entorno efímero en Railway)."""
    try:
        repo = StockRepository(STOCK_DB_PATH)
        repo.init_schema()
        n = repo.update_from_file(STOCK_FILE)
        if n > 0:
            print(f"[Startup] Stock cargado: {n} vehículos")
    except Exception as e:
        print(f"[Startup] Stock opcional: {e}")
    yield


app = FastAPI(title="Agente Pompeyo Carrasco Usados", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat_endpoint(request: Request):
    """POST body: {"message": "...", "thread_id": "opcional"}. Respuesta en texto."""
    from agent.orchestrator import chat

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


# Para verificación de webhook de WhatsApp (Meta)
@app.get("/webhook")
async def webhook_verify(request: Request):
    from config import WHATSAPP_WEBHOOK_VERIFY_TOKEN

    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(challenge)
    return PlainTextResponse("Forbidden", status_code=403)


@app.post("/webhook")
async def webhook_receive(request: Request):
    """Recibe mensajes de WhatsApp; responde con el agente (implementar cuando tengas la API)."""
    return {"ok": True}
