"""Configuración central del proyecto."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Rutas base
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# OpenAI (obligatorio para el agente)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# WhatsApp Business (Meta Cloud API) - los clientes hablan por WhatsApp
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
WHATSAPP_WEBHOOK_VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "")

# Stock (por defecto el archivo real "stock copy.csv")
STOCK_FILE = os.getenv("STOCK_FILE") or str(DATA_DIR / "stock copy.csv")
STOCK_DB_PATH = os.getenv("STOCK_DB_PATH") or str(DATA_DIR / "stock.db")
FAQ_CACHE_PATH = os.getenv("FAQ_CACHE_PATH") or str(DATA_DIR / "faq_cache.db")
LEADS_DB_PATH = os.getenv("LEADS_DB_PATH") or str(DATA_DIR / "leads.db")
CHECKPOINT_DB_PATH = os.getenv("CHECKPOINT_DB_PATH") or str(DATA_DIR / "checkpoints.db")
# En Railway: usa Postgres para memoria (el disco es efímero). Variable típica: DATABASE_URL
CHECKPOINT_POSTGRES_URI = os.getenv("CHECKPOINT_POSTGRES_URI") or os.getenv("DATABASE_URL") or ""

# Financiamiento: tasa mensual 3,8% (no revelar al cliente). Cuota se muestra redondeada a la milésima.
FINANCIAMIENTO_TASA_MENSUAL = float(os.getenv("FINANCIAMIENTO_TASA_MENSUAL", "0.038"))
FINANCIAMIENTO_PIE_MIN = 0.30   # 30%
FINANCIAMIENTO_PIE_MAX = 0.50   # 50%
FINANCIAMIENTO_PLAZOS = (24, 36, 48)

DATA_DIR.mkdir(parents=True, exist_ok=True)
