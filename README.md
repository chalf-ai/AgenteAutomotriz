# Agente Pompeyo Carrasco Usados

Agente de ventas (Jaime) para vehículos usados, con OpenAI y preparado para WhatsApp. Despliegue en **Railway**.

## Despliegue en Railway

1. **Push del código** (si aún no lo hiciste):
   ```bash
   git push -u origin main
   ```
   Usa la cuenta de GitHub que tenga acceso al repo `chalf-ai/AgenteAutomotriz`.

2. **Conectar el repo en Railway**
   - Entra a [railway.app](https://railway.app) y crea un proyecto.
   - "Deploy from GitHub repo" → elige `chalf-ai/AgenteAutomotriz`.
   - Railway detectará el `Procfile` y usará: `uvicorn app:app --host 0.0.0.0 --port $PORT`.

3. **Variables de entorno** (en Railway → Variables):
   - `OPENAI_API_KEY` (obligatorio)
   - `OPENAI_MODEL` (opcional, default: gpt-4o-mini)
   - **Memoria del agente (contexto por conversación):** En Railway el disco es efímero, así que la memoria en SQLite se pierde. Añade **Postgres** al proyecto (Railway → Add Plugin → PostgreSQL) y configura la variable que Railway crea: `DATABASE_URL`. El agente usará Postgres para guardar el estado por `thread_id` y así recordar la conversación entre mensajes.
   - Para WhatsApp cuando lo actives: `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_WEBHOOK_VERIFY_TOKEN`

4. **URL pública**  
   Railway te asigna una URL (ej. `https://tu-app.up.railway.app`). Úsala para:
   - Probar: `POST /chat` con `{"message": "Hola, busco auto 15 millones"}`.
   - Webhook WhatsApp: en Meta Developers configura la URL de verificación como `https://tu-app.up.railway.app/webhook`.

## Local

```bash
python -m venv .venv
source .venv/bin/activate   # o .venv\Scripts\activate en Windows
pip install -r requirements.txt
cp .env.example .env        # y rellena OPENAI_API_KEY
python scripts/update_stock.py   # carga stock
.venv/bin/python scripts/chat_consola.py   # chat por consola
# O servidor web local:
uvicorn app:app --reload --port 8000
```

## Endpoints

- `GET /health` — estado del servicio
- `POST /chat` — body `{"message": "...", "thread_id": "opcional"}` → respuesta del agente (streaming)
- `POST /api/chat` — para interfaz de chat (Lovable, etc.): ver abajo
- `GET /webhook` — verificación del webhook de WhatsApp (Meta)
- `POST /webhook` — recepción de mensajes de WhatsApp (a conectar con el agente)

### Mantener contexto en el chat (POST /api/chat)

El agente tiene **memoria por conversación**. Si la interfaz no envía el mismo `thread_id` en cada mensaje, el agente **pierde el contexto** (por ejemplo, no recuerda las opciones que acaba de listar).

**Qué hacer en el frontend (Lovable u otro):**

1. En el **primer mensaje** de una conversación, envía solo `{"message": "..."}`. La API devolverá `{"reply": "...", "thread_id": "abc-123..."}`.
2. **Guarda** ese `thread_id` (en estado de React, en un ref, en sessionStorage, etc.).
3. En **todos los mensajes siguientes** de esa misma conversación, envía:  
   `{"message": "tu mensaje", "thread_id": "abc-123..."}` (el mismo valor).
4. Opcional: también puedes enviar el id en la cabecera `X-Thread-Id` o leerlo de la cabecera `X-Thread-Id` de la respuesta.

Si no reenvías el `thread_id`, cada request se trata como una conversación nueva y el agente no verá el historial (por eso responde como si fuera la primera vez).
