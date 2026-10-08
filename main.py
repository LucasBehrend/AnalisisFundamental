import asyncio
import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

load_dotenv()
API_KEY = os.getenv("FINNHUB_API_KEY")
BASE = "https://finnhub.io/api/v1"
import finnhub
finnhub_client = finnhub.Client(api_key=API_KEY)
# Supuestos por defecto del DCF (el usuario puede cambiarlos desde la web)
DESCUENTO_DEF = 10.0  # %
TERMINAL_DEF = 2.5  # %
ANIOS_DEF = 10

app = FastAPI(title="Valuador de acciones")



@app.get("/api/analizar/{ticker}")
async def analizar(
    ticker: str,
    crecimiento: float | None = Query(None, ge=-50, le=100, description="% anual del FCF; vacío = automático"),
    descuento: float = Query(DESCUENTO_DEF, gt=0, le=50, description="Tasa de descuento %"),
    terminal: float = Query(TERMINAL_DEF, ge=-5, le=10, description="Crecimiento terminal %"),
    anios: int = Query(ANIOS_DEF, ge=1, le=30, description="Años de proyección"),
):
    if not API_KEY:
        raise HTTPException(500, "Falta FINNHUB_API_KEY en el archivo .env")

    if terminal >= descuento:
        raise HTTPException(400, "El crecimiento terminal debe ser menor que la tasa de descuento.")

    symbol = ticker.strip().upper()
    if not symbol.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(400, "Ticker inválido.")

    response = finnhub_client.company_basic_financials(symbol, 'all')
    breakpoint()
    return {
        "ticker": symbol,
        "empresa": profile.get("name"),
        "moneda": profile.get("currency") or "USD",
        "metodo": metodo,
        "supuestos": {
            "crecimiento": g * 100,
            "crecimiento_auto": crecimiento_auto,
            "descuento": descuento,
            "terminal": terminal,
            "anios": anios,
        },
        "precio": precio,
        "valor_intrinseco": intrinseco,
        "diferencia": diferencia,
        "diferencia_pct": diferencia_pct,
        "eps": eps,
        "peg": peg,
        "per": per,
        "ev": ev,  # millones
        "fcf": fcf,  # millones
        "ebit": ebit,  # millones
        "ev_fcf": ratio(ev, fcf),
        "ev_ebit": ratio(ev, ebit),
    }


# Sirve el frontend (debe ir después de las rutas de la API)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
