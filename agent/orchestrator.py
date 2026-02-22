"""Orquestador: cache FAQ, off-topic e invocación del agente."""
from __future__ import annotations

from typing import AsyncGenerator

from agent.off_topic import is_automotive_related
from agent.faq_cache import FAQCache
from agent.builder import build_agent
from config import FAQ_CACHE_PATH

_faq: FAQCache | None = None
_agent = None

# Contador de off-topic por thread: tras 3 respuestas off-topic, cerramos con mensaje gentil
_thread_off_topic_count: dict[str, int] = {}

OFF_TOPIC_MESSAGES = (
    "Soy un asesor de ventas de automóviles. Solo puedo ayudarte con temas de autos: búsqueda, precios, marcas, modelos, etc. ¿En qué puedo ayudarte con tu próximo auto?",
    "En este chat estamos para ayudarte con vehículos usados: búsqueda, financiamiento, opciones. Si tienes alguna duda sobre autos, dime.",
    "Por acá nos enfocamos en autos usados de Pompeyo Carrasco. ¿Buscas algún vehículo o quieres ver opciones de financiamiento?",
)
OFF_TOPIC_GOODBYE = "Para no ocupar este espacio con temas que no puedo atender, te dejo por acá. Cuando necesites algo de autos usados, aquí estaré. ¡Que tengas un buen día!"


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


def _looks_like_greeting_or_very_short(text: str) -> bool:
    """Saludos o mensajes muy cortos (hola, ok, sí, gracias) → no off-topic."""
    t = text.strip()
    if not t:
        return False
    lower = t.lower()
    # Saludos explícitos
    greetings = (
        "hola", "buenas", "buenos días", "buen día", "buenas tardes", "buenas noches",
        "hey", "hi", "hello", "qué tal", "tal", "saludos", "buenass", "ola",
    )
    if any(lower == g or lower.startswith(g + " ") or lower.startswith(g + ",") for g in greetings):
        return True
    if any(g in lower and len(lower) <= 25 for g in ("hola", "buenas", "buenos", "saludos", "qué tal")):
        return True
    # Mensajes muy cortos: el agente puede responder sin castigar (sí, no, ok, gracias, dale, etc.)
    if len(t) <= 20 and not any(c.isdigit() for c in t):
        letters_etc = sum(1 for c in t if c.isalpha() or c.isspace() or c in ".,!?¿¡'")
        if letters_etc >= len(t) * 0.8:
            return True
    return False


def _looks_like_lead_data_or_follow_up(text: str) -> bool:
    """Nombre, RUT, correo o frases tipo 'listo te envié mis datos' → no off-topic (es respuesta al agente)."""
    t = text.strip()
    if not t or len(t) > 120:
        return False
    lower = t.lower()
    # Correo electrónico
    if "@" in t and "." in t:
        return True
    # RUT: dígitos, opcionalmente con . - y k
    clean = t.replace(".", "").replace(",", "").replace("-", "").replace(" ", "").lower()
    if clean.endswith("k"):
        clean = clean[:-1]
    if clean.isdigit() and 7 <= len(clean) <= 12:
        return True
    # Frases cortas de seguimiento / envío de datos
    follow_phrases = (
        "listo", "te envi", "mi nombre", "mi correo", "mi rut", "ahí está", "envié", "enviado",
        "datos", "nombre es", "correo es", "rut es", "te pas", "aquí está", "es ", "soy ",
    )
    if len(lower) <= 80 and any(p in lower for p in follow_phrases):
        return True
    # Posible nombre: una o más palabras, mayormente letras
    words = t.split()
    if 1 <= len(words) <= 6 and len(t) <= 60:
        letters = sum(1 for c in t if c.isalpha() or c.isspace() or c in ".-'")
        if letters >= 0.7 * len(t):
            return True
    return False


def _looks_like_financing_follow_up(text: str) -> bool:
    """'La cuota es cara', 'muy alta', 'me parece cara' = seguimiento de financiamiento → no off-topic."""
    t = text.strip().lower()
    if not t or len(t) > 80:
        return False
    financing_words = (
        "cuota", "cara", "barata", "alta", "baja", "financiar", "financiamiento",
        "pie", "plazo", "plazos", "mensual", "pagando", "pagar ",
    )
    return any(w in t for w in financing_words)


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

    # No marcar como off-topic: saludos, presupuesto, opción, datos de lead, seguimiento financiamiento, o mensajes muy cortos
    skip_off_topic = (
        _looks_like_greeting_or_very_short(user_message)
        or _looks_like_budget_or_short_reply(user_message)
        or _looks_like_option_choice(user_message)
        or _looks_like_lead_data_or_follow_up(user_message)
        or _looks_like_financing_follow_up(user_message)
    )
    if check_off_topic and not skip_off_topic and not is_automotive_related(user_message):
        global _thread_off_topic_count
        count = _thread_off_topic_count.get(thread_id, 0) + 1
        _thread_off_topic_count[thread_id] = count
        if count >= 3:
            _thread_off_topic_count[thread_id] = 0
            yield OFF_TOPIC_GOODBYE
        else:
            msg_index = min(count - 1, len(OFF_TOPIC_MESSAGES) - 1)
            yield OFF_TOPIC_MESSAGES[msg_index]
        return

    # Si llegó aquí y no fue off-topic, reiniciar contador de off-topic para este thread
    _thread_off_topic_count[thread_id] = 0

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
