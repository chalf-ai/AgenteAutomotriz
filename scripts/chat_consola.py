#!/usr/bin/env python3
"""
Chat con el agente Jaime por consola.
Uso: python scripts/chat_consola.py
Escribe "salir" o "exit" para terminar.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _extract_answer(messages) -> str:
    for m in reversed(messages):
        if hasattr(m, "content") and m.content:
            c = m.content
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                for part in c:
                    if isinstance(part, dict) and part.get("type") == "text":
                        return part.get("text", "")
    return ""


async def main() -> int:
    from config import OPENAI_API_KEY
    from agent.builder import build_agent

    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY no está en .env")
        return 1

    print("Cargando agente Jaime (Pompeyo Carrasco Usados)...")
    agent = build_agent()
    thread_id = "consola-1"
    config = {"configurable": {"thread_id": thread_id}}

    print("\n--- Escribe tu mensaje y Enter. 'salir' o 'exit' para terminar ---\n")

    while True:
        try:
            user_input = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("salir", "exit", "quit", "q"):
            print("Hasta luego.")
            break

        print("Jaime: ", end="", flush=True)
        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": user_input}]},
                config=config,
            )
            messages = result.get("messages") or []
            answer = _extract_answer(messages)
            print(answer or "(Sin respuesta)")
        except Exception as e:
            print(f"(Error: {e})")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
