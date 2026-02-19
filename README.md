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
- `POST /chat` — body `{"message": "...", "thread_id": "opcional"}` → respuesta del agente
- `GET /webhook` — verificación del webhook de WhatsApp (Meta)
- `POST /webhook` — recepción de mensajes de WhatsApp (a conectar con el agente)
