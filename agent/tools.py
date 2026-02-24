"""Herramientas del agente: consulta de stock, cálculo de cuota y registro de leads."""
from __future__ import annotations

import math
from typing import Optional

from langchain_core.tools import tool

from config import (
    STOCK_DB_PATH,
    FINANCIAMIENTO_TASA_MENSUAL,
    FINANCIAMIENTO_PIE_MIN,
    FINANCIAMIENTO_PIE_MAX,
    FINANCIAMIENTO_PLAZOS,
)
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
    segmento: Optional[str] = None,
    transmision: Optional[str] = None,
    combustible: Optional[str] = None,
    exclude_marca: Optional[str] = None,
    exclude_modelo: Optional[str] = None,
    exclude_combustible: Optional[str] = None,
    limit: int = 5,
    order_by_precio: str = "asc",
) -> str:
    """Busca vehículos usados en el stock real. precio_min y precio_max en PESOS (ej. 20000000). order_by_precio: "asc" o "desc". Para presupuesto (hasta 20/30/40M) usa order_by_precio=desc.
    Filtros por tipo de vehículo (usar cuando el cliente pida):
    - segmento: CityCar, Suv, Sedan, Camioneta, Furgon. Pickup o camioneta -> segmento="Camioneta" (NO Furgon; Furgon = van tipo Berlingo/Partner).
    - transmision: Automatico (AT, DCT, automático) o Mecanico (MT, mecánico)
    - combustible: Diesel, Gasolina, Hibrido, Electrico (ej. "diesel", "híbrido" -> combustible)
    Excluir: "que no sea Nissan" -> exclude_marca="Nissan". "que no sea Navara" -> exclude_modelo="Navara". "no quiero eléctrico" / "no me gustan los eléctricos" -> exclude_combustible="Electrico". "no diesel" -> exclude_combustible="Diesel". Mantén el resto de filtros (segmento, combustible si lo pide, etc.).
    IMPORTANTE: Solo puedes mostrar vehículos y links que devuelva esta herramienta; NUNCA inventes. Si devuelve vacío: no cierres con 'no hay'; aclara pie vs presupuesto, ofrece los más económicos (misma búsqueda con precio_max más alto o sin tope, order_by_precio=asc) o si piden un modelo que no está, ofrece alternativas del mismo tipo."""
    repo = _get_repo()
    results = repo.search(
        precio_min=precio_min,
        precio_max=precio_max,
        año_min=año_min,
        año_max=año_max,
        km_max=km_max,
        marca=marca,
        modelo=modelo,
        segmento=segmento,
        transmision=transmision,
        combustible=combustible,
        exclude_marca=exclude_marca,
        exclude_modelo=exclude_modelo,
        exclude_combustible=exclude_combustible,
        limit=limit,
        order_by_precio=order_by_precio or "asc",
    )
    if not results:
        return (
            "No hay vehículos que coincidan con esos criterios. "
            "INSTRUCCIÓN: No asumas que el monto del cliente era presupuesto; lo más probable es que sea PIE. (1) Confirma: '¿Esos X millones son para el pie o es tu presupuesto para el auto?' (2) Si era presupuesto y no hay nada hasta ese tope: llama de nuevo a search_stock con los MISMOS filtros (segmento, combustible) pero SIN precio_max (o precio_max=25000000) y order_by_precio='asc', limit=5; luego di al cliente que lo que tienen parte desde aproximadamente X millones y pregúntale si quiere que le muestre los más económicos. (3) Si era pie: busca con precio_min=2×pie y muestra opciones con calculate_cuota."
        )
    lines = []
    for i, v in enumerate(results, 1):
        marca_m = v.get("marca") or "N/A"
        modelo_m = v.get("modelo") or "N/A"
        version_val = (v.get("version") or "").strip()
        # Versión siempre visible: evita que el agente la omita o ponga N/A
        version_s = f" | Versión: {version_val}" if version_val else ""
        año = v.get("año") or "N/A"
        precio = v.get("precio")
        precio_s = f"${precio:,.0f}" if precio is not None else "N/A"
        km = v.get("kilometraje")
        km_s = f"{km:,.0f} km" if km is not None else "N/A"
        ubicacion = ""
        if v.get("sucursal") or v.get("comuna"):
            ubicacion = f" | Ubicación: {v.get('sucursal', '')} ({v.get('comuna', '')})".strip().rstrip("()")
        link_raw = (v.get("link") or "").strip()
        if link_raw and not link_raw.startswith("http"):
            link_raw = f"https://{link_raw}"
        # Línea principal: Marca Modelo (Año) - Precio - Km [+ Versión: ...] [+ Ubicación]
        linea = f"{i}. {marca_m} {modelo_m} ({año}) - {precio_s} - {km_s}{version_s}{ubicacion}"
        if link_raw:
            lines.append(linea)
            lines.append(link_raw)
        else:
            lines.append(linea)
    return "Opciones encontradas:\n" + "\n".join(lines)


def _valor_cuota(monto_financiar: float, num_cuotas: int) -> float:
    """Cuota mensual con tasa mensual. Resultado redondeado a la milésima (ej. 318915 → 318000)."""
    r = FINANCIAMIENTO_TASA_MENSUAL
    n = num_cuotas
    if r <= 0 or n <= 0:
        return 0.0
    factor = (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    cuota = monto_financiar * factor
    return float(math.floor(cuota / 1000) * 1000)


def _factor_cuota(num_cuotas: int) -> float:
    """Factor para cuota: cuota = monto_financiar * factor. Para inverso: monto_max = cuota_deseada / factor."""
    r = FINANCIAMIENTO_TASA_MENSUAL
    n = num_cuotas
    if r <= 0 or n <= 0:
        return 0.0
    return (r * (1 + r) ** n) / ((1 + r) ** n - 1)


@tool
def calculate_cuota(
    precio_lista: float,
    pie: float,
    plazo: int = 36,
) -> str:
    """Calcula el valor cuota mensual para un vehículo. precio_lista y pie en pesos. plazo: 24, 36 o 48 cuotas. El PIE se ajusta: mínimo 30% del precio, máximo 50% (si el cliente da más del 50%, se simula con 50% y el resto queda para él). La cuota se muestra redondeada a la milésima (ej. 318000). Usar cuando el cliente pregunte por financiamiento o diga cuánto puede pagar al mes y cuánto de pie."""
    if precio_lista <= 0:
        return "El precio debe ser mayor a 0."
    if plazo not in FINANCIAMIENTO_PLAZOS:
        plazo = 36
    pie_min = precio_lista * FINANCIAMIENTO_PIE_MIN
    pie_max = precio_lista * FINANCIAMIENTO_PIE_MAX
    pie_efectivo = max(pie_min, min(pie_max, pie))
    monto_financiar = precio_lista - pie_efectivo
    if monto_financiar <= 0:
        return "El monto a financiar debe ser positivo. Ajusta el pie (entre 30% y 50% del precio)."
    cuota = _valor_cuota(monto_financiar, plazo)
    pie_pct = (pie_efectivo / precio_lista) * 100
    return (
        f"Precio: ${precio_lista:,.0f}. Pie usado en simulación: ${pie_efectivo:,.0f} ({pie_pct:.0f}%). "
        f"Monto a financiar: ${monto_financiar:,.0f}. A {plazo} cuotas, valor cuota: ${cuota:,.0f}/mes."
    )


@tool
def estimate_precio_max_for_cuota(
    pie: float,
    cuota_deseada: float,
    plazo: int = 36,
) -> str:
    """Dado el PIE del cliente (en pesos) y la cuota mensual que quiere pagar (ej. 300000), devuelve el precio máximo de vehículo que podría pagar (pie + financiamiento) para que la cuota no supere ese monto. Usar cuando el cliente diga "tengo X de pie y puedo pagar Y al mes": con el precio_max devuelto, llama search_stock(precio_max=este_valor, order_by_precio=desc) y luego calculate_cuota para cada resultado."""
    if pie < 0 or cuota_deseada <= 0:
        return "Pie y cuota deseada deben ser positivos."
    if plazo not in FINANCIAMIENTO_PLAZOS:
        plazo = 36
    factor = _factor_cuota(plazo)
    if factor <= 0:
        return "No se pudo calcular."
    monto_financiar_max = cuota_deseada / factor
    precio_max = pie + monto_financiar_max
    return (
        f"Con pie ${pie:,.0f} y cuota deseada ${cuota_deseada:,.0f}/mes a {plazo} cuotas, "
        f"el precio máximo de vehículo es aproximadamente ${precio_max:,.0f}. "
        f"Usa search_stock(precio_max={int(precio_max)}, order_by_precio=desc, limit=5) y luego calculate_cuota para cada vehículo."
    )


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
