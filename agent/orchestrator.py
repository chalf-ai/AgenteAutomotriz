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

# Off-topic: si parece financiamiento (ej. "5m en 36") → aclaración para no cortar el hilo; si no (ej. "valor uf") → genérico
OFF_TOPIC_GENERIC = "Soy un asesor de ventas de automóviles. Solo puedo ayudarte con temas de autos: búsqueda, precios, marcas, modelos, financiamiento, etc. ¿En qué puedo ayudarte con tu próximo auto?"
OFF_TOPIC_CLARIFY = (
    "No entendí bien. ¿Podrías aclarar si te refieres al presupuesto del auto, al pie que darías o a la cuota mensual? Así te ayudo con el financiamiento.",
    "No estoy seguro de entender. ¿Hablas del precio del vehículo, del pie o de la cuota que podrías pagar? Con eso te doy opciones más claras.",
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


def _expresses_millions(text: str) -> bool:
    """Concepto: ¿el texto expresa un monto en millones (Chile)? 12mm, 12m, 12 palos, 12 millones, 12.000.000, etc."""
    t = text.strip().lower()
    if not t or len(t) > 80:
        return False
    # "12 millones", "20 millón", "15 millones de pesos"
    if "millon" in t:
        return True
    # "12 palos", "15 palos" (coloquial Chile)
    if "palos" in t:
        clean = t.replace(".", "").replace(",", "").replace(" ", "")
        # quitar "palos" y ver si queda número (1-5 dígitos = millones)
        without = clean.replace("palos", "").strip()
        if without.isdigit() and 1 <= len(without) <= 5:
            return True
    # "12mm", "12 mm", "12m", "12 m", "15m"
    clean = t.replace(" ", "")
    if clean.endswith("mm") and len(clean) <= 10:
        if clean[:-2].replace(".", "").replace(",", "").isdigit():
            return True
    if (clean.endswith("m") or t.endswith(" m")) and len(t) <= 15:
        num_part = clean.rstrip("m").replace(".", "").replace(",", "")
        if num_part.isdigit() and 1 <= len(num_part) <= 5:
            return True
    # Solo número: "12", "15", "12000000", "12.000.000"
    digits_only = t.replace(".", "").replace(",", "").replace(" ", "")
    if digits_only.isdigit():
        if len(digits_only) <= 5:  # 12 = 12 millones
            return True
        if 6 <= len(digits_only) <= 10 and int(digits_only) >= 1_000_000:
            return True
    return False


def _looks_like_budget_or_short_reply(text: str) -> bool:
    """Mensajes que expresan presupuesto (cualquier forma de millones: 12mm, 12m, 12 palos, 12 millones) o respuesta corta numérica → no off-topic."""
    t = text.strip().lower()
    if not t or len(t) > 80:
        return False
    if _expresses_millions(text):
        return True
    # Número corto sin contexto (ej. "12" como posible presupuesto)
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


def _looks_like_monto_mas_plazo(text: str) -> bool:
    """Concepto: 'X en 24/36/48' donde X es un monto (pie). Ej: '5m en 36', '8 millones en 24', '12 palos en 48', '8000000 en 24'."""
    t = text.strip().lower()
    if " en " not in t or len(t) > 50:
        return False
    parts = t.split(" en ", 1)
    if len(parts) != 2 or parts[1].strip() not in ("24", "36", "48"):
        return False
    left = parts[0].strip().lower()
    left = left.replace("millones", "").replace("millón", "").replace("millon", "").replace("palos", "").strip()
    left_clean = left.replace(".", "").replace(",", "").replace(" ", "")
    if left_clean.endswith("m"):
        left_clean = left_clean[:-1]
    if not left_clean.isdigit():
        return False
    return 1 <= len(left_clean) <= 10


def _looks_like_plazo_only(text: str) -> bool:
    """Frases cortas que solo preguntan por plazo: 'a 36', 'a 48', 'y a 24?', 'en 36 cuotas?' → no off-topic."""
    t = text.strip().lower()
    if not t or len(t) > 35:
        return False
    # Solo números de plazo con contexto mínimo: "a 36", "a 48", "y a 24?", "en 36", "en 48 cuotas?"
    clean = t.replace("?", " ").replace(".", " ").replace("!", " ")
    if "24" in clean or "36" in clean or "48" in clean:
        rest = clean.replace("24", "").replace("36", "").replace("48", "")
        rest = rest.replace("a", "").replace("en", "").replace("cuotas", "").replace("cuota", "").replace("y", "").replace(" ", "")
        if len(rest) <= 2:  # casi solo conectores
            return True
    return False


def _looks_like_financing_follow_up(text: str) -> bool:
    """Cualquier seguimiento de financiamiento: palabras clave, plazo solo, o patrón monto + en + plazo."""
    t = text.strip().lower()
    if not t or len(t) > 80:
        return False
    if _looks_like_plazo_only(text):
        return True
    financing_words = (
        "cuota", "cara", "barata", "alta", "baja", "financiar", "financiamiento",
        "pie", "plazo", "plazos", "mensual", "pagando", "pagar ",
    )
    if any(w in t for w in financing_words):
        return True
    # Cualquier "X en 24/36/48" donde X parezca monto (pie)
    if _looks_like_monto_mas_plazo(text):
        return True
    return False


def _looks_like_financing_fragment(text: str) -> bool:
    """Parece un fragmento de financiamiento (monto en millones, números, 'en 36') → aclaración en vez de genérico."""
    t = text.strip().lower()
    if not t or len(t) > 50:
        return False
    if " en " in t and any(p in t for p in ("24", "36", "48")):
        return True
    # Cualquier forma de expresar millones (12m, 12 palos, 12 millones, 12mm)
    if _expresses_millions(text):
        return True
    # Solo números que podrían ser pie o cuota (ej. 5000000, 300000)
    clean = t.replace(".", "").replace(",", "").replace(" ", "").replace("m", "")
    if clean.isdigit() and 5 <= len(clean) <= 10:
        return True
    return False


def _off_topic_clarification(user_message: str) -> str | None:
    """Si el mensaje parece pie+plazo (ej. '5m en 36', '8 millones en 24'), devuelve aclaración con esos números."""
    t = user_message.strip().lower()
    if " en " in t:
        parts = t.split(" en ", 1)
        if len(parts) == 2:
            plazo = parts[1].strip()
            if plazo in ("24", "36", "48"):
                left = parts[0].strip()
                # "8 millones", "10 palos", "5m" → extraer número
                left_norm = left.replace("millones", "").replace("millón", "").replace("millon", "").replace("palos", "").strip()
                num_part = left_norm.replace(".", "").replace(",", "").replace(" ", "").lower()
                if num_part.endswith("m"):
                    num_part = num_part[:-1]
                if num_part.isdigit():
                    n = int(num_part)
                    # 6+ dígitos = monto en pesos (ej. 8000000 → 8 millones)
                    if len(num_part) >= 6 and n >= 1_000_000:
                        mill = int(n / 1_000_000)
                        return f"¿Te refieres a {mill} millones de pie en {plazo} cuotas?"
                    # 1-5 dígitos = millones (8, 10, 5m, 8 millones)
                    if 1 <= n <= 99999:
                        return f"¿Te refieres a {n} millones de pie en {plazo} cuotas?"
    # Solo número grande (posible pie)
    clean = t.replace(".", "").replace(",", "").replace(" ", "")
    if clean.isdigit() and 6 <= len(clean) <= 10:
        val = int(clean)
        if val >= 1_000_000:
            mill = val / 1_000_000
            return f"¿Te refieres a {int(mill)} millones de pie?"
    return None


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
            # Si parece fragmento de financiamiento (ej. "5m en 36") → aclaración; si no (ej. "valor uf") → genérico
            if _looks_like_financing_fragment(user_message):
                clarification = _off_topic_clarification(user_message)
                if clarification:
                    yield clarification
                else:
                    msg_index = min(count - 1, len(OFF_TOPIC_CLARIFY) - 1)
                    yield OFF_TOPIC_CLARIFY[msg_index]
            else:
                yield OFF_TOPIC_GENERIC
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
