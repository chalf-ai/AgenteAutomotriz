#!/usr/bin/env python3
"""
Prueba la conexión con OpenAI y el agente Jaime (Pompeyo Carrasco Usados).
Uso: python scripts/test_agent.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Raíz del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main() -> int:
    from config import OPENAI_API_KEY
    from agent.builder import build_agent

    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY no está configurada en .env")
        return 1

    print("Conectando con OpenAI y cargando agente (Jaime - Pompeyo Carrasco Usados)...")
    try:
        agent = build_agent()
    except Exception as e:
        print(f"ERROR al construir el agente: {e}")
        return 1

    thread_id = "test-conversacion-1"
    config = {"configurable": {"thread_id": thread_id}}

    # Primera pregunta: presupuesto
    pregunta1 = "Hola, busco un auto usado con presupuesto de 12 millones"
    print(f"\n[Tú] {pregunta1}")
    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": pregunta1}]},
            config=config,
        )
        messages = result.get("messages") or []
        for m in reversed(messages):
            if hasattr(m, "content") and m.content and getattr(m, "type", "") != "human":
                c = m.content
                if isinstance(c, str):
                    print(f"[Jaime] {c[:1500]}" + ("..." if len(c) > 1500 else ""))
                    break
                if isinstance(c, list):
                    for part in c:
                        if isinstance(part, dict) and part.get("type") == "text":
                            txt = part.get("text", "")
                            print(f"[Jaime] {txt[:1500]}" + ("..." if len(txt) > 1500 else ""))
                            break
                    break
    except Exception as e:
        print(f"ERROR al invocar agente: {e}")
        return 1

    print("\n--- Prueba de conexión OpenAI + agente: OK ---")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
