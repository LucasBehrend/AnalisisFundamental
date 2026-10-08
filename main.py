import os
import requests
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn

load_dotenv()

# Requiere agregar FINNHUB_API_KEY en tu archivo .env
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip("'\" ")

app = FastAPI(title="Stock Valuation API (Finnhub Free Tier)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def fetch_finnhub(endpoint: str, **kwargs):
    """Función auxiliar para conectarse a Finnhub y manejar la API Key en los parámetros."""
    base_url = "https://finnhub.io/api/v1"
    params = {"token": FINNHUB_API_KEY, **kwargs}
    
    try:
        response = requests.get(f"{base_url}{endpoint}", params=params, timeout=10)
        
        if response.status_code == 429:
            print(f"[Finnhub Límite] Demasiadas peticiones (Max 30 por segundo en Free).")
            return None
        if response.status_code == 403:
            print(f"[Finnhub Bloqueo] Endpoint requiere plan premium o API Key inválida.")
            return None
            
        data = response.json()
        
        if isinstance(data, dict) and "error" in data:
            print(f"[Finnhub Error] {data['error']}")
            return None
            
        return data
    except Exception as err:
        print(f"[Finnhub Exception] {endpoint} -> {err}")
        return None

@app.get("/api/valuate/{ticker}")
def valuate_stock(ticker: str, growth: float = 0.05, discount: float = 0.10, perp_growth: float = 0.025, manual_fcf: float = None):
    if not FINNHUB_API_KEY:
        raise HTTPException(status_code=500, detail="FINNHUB_API_KEY no configurada en el archivo .env")

    ticker = ticker.upper()

    try:
        # 1. Cotización en Vivo (Precio Actual)
        quote = fetch_finnhub("/quote", symbol=ticker)
        if not quote or 'c' not in quote or quote['c'] == 0:
            raise HTTPException(status_code=404, detail="Ticker no encontrado o sin precio en Finnhub.")
        precio_actual = quote['c']

        # 2. Perfil de la Empresa (Acciones en Circulación)
        profile = fetch_finnhub("/stock/profile2", symbol=ticker)
        # Finnhub reporta 'shareOutstanding' en millones de unidades.
        shares_millions = profile.get("shareOutstanding", 0) if profile else 0
        shares = shares_millions * 1_000_000

        if shares == 0:
            raise HTTPException(status_code=400, detail="No se pudieron obtener las acciones en circulación.")

        # 3. Métricas Financieras Básicas (TTM - Trailing Twelve Months)
        # El plan gratuito expone ratios base, pero no estimaciones futuras.
        metrics_res = fetch_finnhub("/stock/metric", symbol=ticker, metric="all")
        metrics = metrics_res.get("metric", {}) if metrics_res else {}

        per = metrics.get("peTTM", 0)
        # Finnhub Free a veces no provee PEG. Fallback a 0.
        peg = metrics.get("pegTTM", 0)

        # 4. Cálculos de Flujo de Caja y Deuda Neta
        # Finnhub entrega el FCF por acción (Free Cash Flow Per Share). Lo multiplicamos por las acciones.
        fcf_per_share = metrics.get("freeCashFlowPerShareTTM", 0)
        historical_fcf = fcf_per_share * shares

        # Finnhub entrega la 'Deuda Neta' (Deuda Total - Efectivo) en millones.
        net_debt_millions = metrics.get("netDebtAnnual", 0)
        net_debt = net_debt_millions * 1_000_000

        # EBIT (Si está disponible por acción)
        ebit_per_share = metrics.get("ebitPerShareTTM", 0)
        ebit = ebit_per_share * shares

        # 5. Enterprise Value
        market_cap = precio_actual * shares
        ev = market_cap + net_debt

        # Ratios suplementarios
        ev_fcf = (ev / historical_fcf) if historical_fcf and historical_fcf != 0 else 0
        ev_ebit = (ev / ebit) if ebit and ebit != 0 else 0

        # 6. Selección de FCF Base para el Modelo DCF
        # Como Finnhub Free NO incluye 'Analyst Estimates' (Crecimiento proyectado), 
        # dependemos estrictamente del histórico TTM o del input manual del usuario.
        fcf_to_use = 0
        if manual_fcf is not None and manual_fcf != 0:
            fcf_to_use = manual_fcf
        else:
            fcf_to_use = historical_fcf

        # 7. Modelo DCF (10 Años + Perpetuidad)
        valor_intrinseco = 0
        diferencia = 0
        
        if fcf_to_use and fcf_to_use > 0:
            pv_fcf_sum = 0
            current_fcf = fcf_to_use
            
            for i in range(1, 11):
                current_fcf *= (1 + growth)
                pv_fcf_sum += current_fcf / ((1 + discount) ** i)
            
            # Valor Terminal
            terminal_value = (current_fcf * (1 + perp_growth)) / (discount - perp_growth)
            pv_terminal_value = terminal_value / ((1 + discount) ** 10)
            
            # Enterprise Value Estimado
            enterprise_value_est = pv_fcf_sum + pv_terminal_value
            
            # Equity Value = Enterprise Value Estimado - Deuda Neta
            # (Restar la Deuda Neta matemáticamente elimina la deuda y suma la caja).
            equity_value = enterprise_value_est - net_debt
            
            valor_intrinseco = equity_value / shares
            
            if precio_actual:
                diferencia = (valor_intrinseco - precio_actual) / precio_actual

        return {
            "price": precio_actual or 0,
            "intrinsic": valor_intrinseco or 0,
            "diff": diferencia or 0,
            "peg": peg or 0,
            "per": per or 0,
            "ev": ev or 0,
            "fcf": fcf_to_use or 0,
            "ebit": ebit or 0,
            "ev_fcf": ev_fcf or 0,
            "ev_ebit": ev_ebit or 0
        }

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        print("\n--- ERROR INESPERADO (FINNHUB) ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)