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


def calculate_dcf(
    current_fcf: float,
    expected_growth: float,
    terminal_growth: float,
    wacc: float,
    years: int = 5
) -> float:
    r = wacc / 100
    g = expected_growth / 100 
    g_term = terminal_growth / 100

    if g_term >= r:
        raise ValueError("La tasa de crecimiento terminal debe ser menor que la tasa de descuento (WACC).")

    pv_fcf_sum = 0.0
    fcf = current_fcf

    for t in range(1, int(years) + 1):
        fcf *= (1 + g)
        pv_fcf_sum += fcf / ((1 + r) ** t)

    # FCF del año N+1
    fcf_terminal = fcf * (1 + g_term)
    
    # Modelo de Crecimiento de Gordon
    terminal_value = fcf_terminal / (r - g_term)
    pv_terminal_value = terminal_value / ((1 + r) ** years)

    return round(pv_fcf_sum + pv_terminal_value, 2)
    
@app.get("/api/analizar/{ticker}")
async def analizar(
    ticker: str,
    growth: float = Query(..., ge=-50, le=100, description="% anual del FCF"),
    discount: float = Query(10.0, gt=0, le=50, description="Tasa de descuento %"),
    terminal: float = Query(2.5, ge=-5, le=10, description="Crecimiento terminal %"),
    years: int = Query(10, ge=1, le=30, description="Años de proyección"),
):
    if not API_KEY:
        raise HTTPException(500, "Falta FINNHUB_API_KEY en el archivo .env")

    if terminal >= discount:
        raise HTTPException(400, "El crecimiento terminal debe ser menor que la tasa de descuento.")

    symbol = ticker.strip().upper()
    if not symbol.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(400, "Ticker inválido.")

    # --- 1. Llamadas a la API base ---
    basic_financials = finnhub_client.company_basic_financials(symbol, 'all')
    profile = finnhub_client.company_profile2(symbol=symbol)
    quote = finnhub_client.quote(symbol)
    
    # --- 2. Métricas Básicas y Acciones ---
    price = quote["c"]
    shares_total = profile.get("shareOutstanding", 0) * 1_000_000

    # Extraer métricas históricas de basic_financials
    ebit_series = basic_financials.get("series", {}).get("annual", {}).get("ebitPerShare", [])
    ebit_per_share = ebit_series[0]['v'] if ebit_series else 0
    ebit_total = ebit_per_share * shares_total
    
    eps_series = basic_financials.get("series", {}).get("annual", {}).get("eps", [])
    eps = eps_series[0]['v'] if eps_series else 0
    
    roic_series = basic_financials.get("series", {}).get("annual", {}).get("roic", [])
    roic = roic_series[0]['v'] * 100 if roic_series else 0
    
    pe_series = basic_financials.get("series", {}).get("annual", {}).get("pe", [])
    per = round(pe_series[0]['v'], 2) if pe_series else 0
    peg = round(basic_financials.get("metric", {}).get("pegTTM", 0), 2)
    
    # EV para pantalla y múltiplos
    ev_total = basic_financials.get("metric", {}).get("enterpriseValue", 0) * 1_000_000

    # --- 3. Extracción Segura de Reportes (Flujo de Caja) ---
    reports_data = finnhub_client.financials_reported(symbol=symbol, freq='annual').get('data', [{}])
    report = reports_data[0].get('report', {}) if reports_data else {}
    
    cf_list = report.get('cf', [])  # Estado de flujos de efectivo

    def find_val(data_list, concepts):
        return next((item['value'] for item in data_list if item.get('concept') in concepts), 0)

    # 3.A Extraer Flujo de Caja Libre (FCF)
    op_cf = find_val(cf_list, [
        'us-gaap_NetCashProvidedByUsedInOperatingActivities',
        'us-gaap_NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'
    ])
    capex = find_val(cf_list, [
        'us-gaap_PaymentsToAcquireProductiveAssets',
        'us-gaap_PaymentsToAcquirePropertyPlantAndEquipment',
        'us-gaap_PaymentsToAcquireCapitalAssets'
    ])
    fcf_total = (op_cf - abs(capex)) if op_cf else 0

    # --- 4. Fallback de FCF si no hay reporte de SEC ---
    if not fcf_total:
        fcf_per_share_metric = basic_financials.get("metric", {}).get("cashFlowPerShareTTM", 0)
        fcf_total = fcf_per_share_metric * shares_total

    # --- 5. Cálculo de Deuda Neta e Valor Intrínseco ---
    mkt_cap = price * shares_total

    # Calculamos la Deuda Neta como la diferencia entre Enterprise Value y Market Cap
    if ev_total > mkt_cap:
        net_debt_total = ev_total - mkt_cap
    else:
        net_debt_total = 0

    fcf_per_share = fcf_total / shares_total if shares_total else 0
    net_debt_per_share = net_debt_total / shares_total if shares_total else 0

    # Descontamos la Deuda Neta por acción al resultado del DCF
    dcf_ev_per_share = calculate_dcf(fcf_per_share, growth, terminal, discount, years)
    intrinsic_value = round(dcf_ev_per_share - net_debt_per_share, 2)
    
    difference_nom = round(intrinsic_value - price, 2)
    difference_pct = round((difference_nom / price) * 100, 2) if price else 0

    # --- 6. Cálculo de Múltiplos ---
    ev_fcf = ev_total / fcf_total if fcf_total else 0
    ev_ebit = ev_total / ebit_total if ebit_total else 0

    # --- 7. Respuesta ---
    return {
        "ticker": symbol,
        "precio": price,
        "valor_intrinseco": intrinsic_value,
        "diferencia": difference_nom,
        "diferencia_pct": difference_pct,
        "eps": eps,
        "peg": peg,
        "per": per,
        "roic": roic,
        "ev": ev_total,
        "fcf": fcf_total,
        "ebit": ebit_total,
        "ev_fcf": round(ev_fcf, 2),
        "ev_ebit": round(ev_ebit, 2),
    }
# Sirve el frontend (debe ir después de las rutas de la API)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
