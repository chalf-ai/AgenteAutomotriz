"""Orquestador: cache FAQ, off-topic e invocación del agente."""
from __future__ import annotations

from typing import AsyncGenerator

from agent.off_topic import is_automotive_related
from agent.faq_cache import FAQCache
from agent.builder import build_agent
from config import FAQ_CACHE_PATH

_faq: FAQCache | None = None
_agent = None


def _get_faq() -> FAQCache:
    global _faq
    if _faq is None:
        _faq = FAQCache(FAQ_CACHE_PATH)
    return _faq


def _get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


def _extract_answer(messages) -> str:
    answer = ""
    for m in reversed(messages):
        if hasattr(m, "content") and m.content:
            c = m.content
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                for part in c:
                    if isinstance(part, dict) and part.get("type") == "text":
                        return part.get("text", "")
    return answer or "No pude generar una respuesta. ¿Puedes reformular?"


async def chat(
    user_message: str,
    thread_id: str,
    *,
    use_faq_cache: bool = True,
    check_off_topic: bool = True,
) -> AsyncGenerator[str, None]:
    if not user_message or not user_message.strip():
        yield "Por favor escribe tu pregunta o lo que buscas en un auto."
        return

    if check_off_topic and not is_automotive_related(user_message):
        yield "Soy un asesor de ventas de automóviles. Solo puedo ayudarte con temas de autos: búsqueda, precios, marcas, modelos, etc. ¿En qué puedo ayudarte con tu próximo auto?"
        return

    if use_faq_cache:
        cached = _get_faq().get(user_message)
        if cached:
            yield cached
            return

    agent = _get_agent()
    config = {"configurable": {"thread_id": thread_id}}
    inputs = {"messages": [{"role": "user", "content": user_message}]}

    try:
        result = await agent.ainvoke(inputs, config=config)
        messages = result.get("messages") or []
        answer = _extract_answer(messages)
        yield answer
        if use_faq_cache and answer and len(answer) < 2000:
            _get_faq().set(user_message, answer)
    except Exception as e:
        yield f"Disculpa, hubo un error: {e}"
