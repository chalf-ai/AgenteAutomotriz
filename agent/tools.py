"""Herramientas del agente: consulta de stock y registro de leads."""
from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

from config import STOCK_DB_PATH
from stock.repository import StockRepository
from agent import leads as leads_module

_repo: StockRepository | None = None


def _get_repo() -> StockRepository:
    global _repo
    if _repo is None:
        _repo = StockRepository(STOCK_DB_PATH)
        _repo.init_schema()
    return _repo


@tool
def search_stock(
    precio_min: Optional[float] = None,
    precio_max: Optional[float] = None,
    año_min: Optional[int] = None,
    año_max: Optional[int] = None,
    km_max: Optional[float] = None,
    marca: Optional[str] = None,
    modelo: Optional[str] = None,
    limit: int = 5,
) -> str:
    """Busca vehículos usados. precio_min y precio_max van en PESOS CHILENOS (número completo): ej. 12 millones = 12000000, 20 millones = 20000000. Siempre usa limit=5 y pasa el presupuesto en pesos (no en millones). Usar cuando el cliente mencione presupuesto o qué autos busca."""
    repo = _get_repo()
    results = repo.search(
        precio_min=precio_min,
        precio_max=precio_max,
        año_min=año_min,
        año_max=año_max,
        km_max=km_max,
        marca=marca,
        modelo=modelo,
        limit=limit,
    )
    if not results:
        return "No hay vehículos que coincidan con esos criterios."
    lines = []
    for i, v in enumerate(results, 1):
        marca_m = v.get("marca") or "N/A"
        modelo_m = v.get("modelo") or "N/A"
        version_s = (v.get("version") or "").strip()
        if version_s:
            version_s = f" - {version_s}"
        año = v.get("año") or "N/A"
        precio = v.get("precio")
        precio_s = f"${precio:,.0f}" if precio is not None else "N/A"
        km = v.get("kilometraje")
        km_s = f"{km:,.0f} km" if km is not None else "N/A"
        ubicacion = ""
        if v.get("sucursal") or v.get("comuna"):
            ubicacion = f" | Ubicación: {v.get('sucursal', '')} ({v.get('comuna', '')})".strip().rstrip("()")
        link_s = f" | Link: https://{v.get('link')}" if v.get("link") and not str(v.get("link", "")).startswith("http") else (f" | Link: {v.get('link')}" if v.get("link") else "")
        lines.append(f"{i}. {marca_m} {modelo_m}{version_s} ({año}) - {precio_s} - {km_s}{ubicacion}{link_s}")
    return "Opciones encontradas:\n" + "\n".join(lines)


@tool
def get_stock_summary() -> str:
    """Resumen del stock: cantidad total y rangos de precios y años. Usar cuando pregunten cuántos autos hay o qué precios manejamos."""
    repo = _get_repo()
    s = repo.get_summary()
    if s["total"] == 0:
        return "El stock está vacío."
    parts = [f"Total de vehículos: {s['total']}"]
    if s.get("precio_min") is not None:
        parts.append(f"Precios: ${s['precio_min']:,.0f} - ${s['precio_max']:,.0f}")
    if s.get("año_min") is not None:
        parts.append(f"Años: {s['año_min']} - {s['año_max']}")
    return "\n".join(parts)


@tool
def register_lead(
    nombre: str,
    rut: str = "",
    correo: str = "",
    patente_vehiculo_vpp: str = "",
    kilometraje_vehiculo_vpp: str = "",
    notas: str = "",
) -> str:
    """Registra los datos del cliente para que un ejecutivo lo contacte. Usar cuando tengan nombre y (correo o RUT) y quieran agendar, comprar, o ser contactados. Si es por autos nuevos, accesorios u otro tema (no usados), poner en notas: 'Autos nuevos', 'Accesorios', etc. Si tiene vehículo en parte de pago (VPP), incluir patente y kilometraje."""
    result = leads_module.register_lead(
        nombre=nombre,
        rut=rut,
        correo=correo,
        patente_vehiculo_vpp=patente_vehiculo_vpp,
        kilometraje_vehiculo_vpp=kilometraje_vehiculo_vpp,
        notas=notas,
    )
    if result["ok"]:
        return "Lead registrado. Di al cliente: Sus datos han sido enviados a un ejecutivo de Pompeyo Carrasco Usados, quien lo contactará a la brevedad para coordinar su visita o prueba de manejo."
    return f"Error al registrar: {result['message']}. Pide al cliente que verifique los datos."
