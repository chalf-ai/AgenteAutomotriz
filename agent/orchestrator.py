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


def _looks_like_budget_or_short_reply(text: str) -> bool:
    """Mensajes como '15 millones', '20 m', '12' son respuestas de presupuesto → no off-topic."""
    t = text.strip().lower()
    if not t or len(t) > 80:
        return False
    if "millon" in t or "millones" in t:
        return True
    if t.endswith(" m") and len(t) <= 10:
        return True
    if t.replace(".", "").replace(",", "").replace(" ", "").isdigit() and len(t) <= 15:
        return True
    return False


def _looks_like_option_choice(text: str) -> bool:
    """'opcion 5', 'opción 3', 'la 2' = eligiendo de una lista → no off-topic."""
    t = text.strip().lower()
    if not t or len(t) > 25:
        return False
    if "opcion" in t or "opción" in t or "opciòn" in t or "opciin" in t:
        return True
    if (t.startswith("la ") or t.startswith("el ")) and len(t) <= 8 and any(c.isdigit() for c in t):
        return True
    return False


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

    # No marcar como off-topic: presupuesto ("15 millones"), o elegir opción ("opcion 5", "la 2")
    skip_off_topic = _looks_like_budget_or_short_reply(user_message) or _looks_like_option_choice(user_message)
    if check_off_topic and not skip_off_topic and not is_automotive_related(user_message):
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
        import asyncio
        # Ejecutar en executor para usar checkpointer SQLite (sync) sin bloquear el event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: agent.invoke(inputs, config=config),
        )
        messages = result.get("messages") or []
        answer = _extract_answer(messages)
        yield answer
        if use_faq_cache and answer and len(answer) < 2000:
            _get_faq().set(user_message, answer)
    except Exception as e:
        yield f"Disculpa, hubo un error: {e}"
