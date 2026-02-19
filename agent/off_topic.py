"""Detección de preguntas no relacionadas con automóviles."""
from __future__ import annotations

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser

from config import OPENAI_API_KEY, OPENAI_MODEL

_PROMPT = """Eres un clasificador. Responde exactamente una palabra:
- AUTOS: si la pregunta trata de automóviles, coches, vehículos, compra/venta de autos, stock, precios, marcas, modelos, características de autos.
- OTRO: si no tiene relación con automóviles (clima, deportes, política, recetas, etc.).

Responde solo: AUTOS o OTRO."""


def is_automotive_related(question: str) -> bool:
    if not question or not question.strip():
        return False
    if not OPENAI_API_KEY:
        return True
    try:
        llm = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY, temperature=0)
        chain = llm | StrOutputParser()
        out = chain.invoke(
            [
                SystemMessage(content=_PROMPT),
                HumanMessage(content=question.strip()),
            ]
        )
        return "AUTOS" in (out or "").upper()
    except Exception:
        return True
