from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import uvicorn
import traceback

app = FastAPI(title="Stock Valuation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_analyst_growth_estimate(stock: yf.Ticker, info: dict) -> float:
    """
    Obtiene la tasa de crecimiento esperada de los analistas utilizando 
    las fuentes internas de yfinance en lugar de scraping de HTML estático.
    """
    try:
        # 1. Intentar obtener 'earningsGrowth' o 'revenueGrowth' directo de info
        if info.get('revenueGrowth') is not None and info.get('revenueGrowth') != 0:
            return float(info.get('revenueGrowth'))
            
        if info.get('earningsGrowth') is not None and info.get('earningsGrowth') != 0:
            return float(info.get('earningsGrowth'))

        # 2. Consultar la tabla oficial de growth_estimates de yfinance
        growth_df = stock.growth_estimates
        if growth_df is not None and not growth_df.empty:
            # Buscar el crecimiento estimado para el próximo año +1y / Next Year
            if '+1y' in growth_df.index:
                val = growth_df.loc['+1y'].values[0]
                if val and not float('nan') == val:
                    return float(val)
            elif 'nextYear' in growth_df.index:
                val = growth_df.loc['nextYear'].values[0]
                if val and not float('nan') == val:
                    return float(val)

        # 3. Consultar la tabla de estimaciones de ingresos (revenue_estimate)
        rev_est = stock.revenue_estimate
        if rev_est is not None and not rev_est.empty and 'growth' in rev_est.columns:
            # Tomar el crecimiento estimado del año en curso / próximo año
            growth_val = rev_est['growth'].iloc[0]
            if growth_val and not float('nan') == growth_val:
                return float(growth_val)

    except Exception as e:
        print(f"[Growth Estimate Notice] No se pudo extraer la estimación: {e}")
        
    # Si no hay datos disponibles, retorna 0.05 (5% por defecto)
    return 0.05

@app.get("/api/valuate/{ticker}")
def valuate_stock(ticker: str, growth: float = 0.05, discount: float = 0.10, perp_growth: float = 0.025, manual_fcf: float = None):
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info

        if 'currentPrice' not in info and 'regularMarketPrice' not in info:
            raise HTTPException(status_code=404, detail="Ticker no encontrado en Yahoo Finance.")

        precio_actual = info.get('currentPrice', info.get('regularMarketPrice', 0))
        shares = info.get('sharesOutstanding', 0)
        per = info.get('trailingPE', 0)
        peg = info.get('pegRatio', 0)
        ev = info.get('enterpriseValue', 0)
        cash = info.get('totalCash', 0)
        debt = info.get('totalDebt', 0)

        if ev == 0 and shares > 0 and precio_actual > 0:
            ev = (shares * precio_actual) + debt - cash

        ebit = 0
        try:
            fin_table = stock.financials
            if 'EBIT' in fin_table.index:
                ebit = fin_table.loc['EBIT'].iloc[0]
        except Exception:
            pass

        # Free Cash Flow Histórico (OCF - CAPEX)
        historical_fcf = 0
        try:
            cf_table = stock.cashflow
            if not cf_table.empty:
                ocf = cf_table.loc['Operating Cash Flow'].iloc[0] if 'Operating Cash Flow' in cf_table.index else cf_table.loc['Total Cash From Operating Activities'].iloc[0]
                capex = cf_table.loc['Capital Expenditure'].iloc[0] if 'Capital Expenditure' in cf_table.index else 0
                historical_fcf = ocf + capex 
        except Exception:
            historical_fcf = info.get('freeCashflow', 0)

        # Selección del FCF Base
        # 1. Definición del FCF Base (Año 0)
        fcf_to_use = 0

        if manual_fcf is not None and manual_fcf != 0:
            # SI EL USUARIO DA UN FCF MANUAL, SE USA ESE VALOR TAL CUAL (SIN MULTIPLICAR)
            fcf_to_use = manual_fcf
        else:
            # Solo si está vacío se calcula sobre el histórico + crecimiento estimado prudente
            estimated_growth = get_analyst_growth_estimate(stock, info)
            
            # Cap de seguridad: si la tasa extraída es > 25%, la topamos en 15% para no distorsionar el modelo
            if estimated_growth > 0.25:
                estimated_growth = 0.15
                
            if historical_fcf > 0:
                fcf_to_use = historical_fcf * (1 + estimated_growth)
            else:
                fcf_to_use = historical_fcf

        # Ratios
        ev_fcf = (ev / fcf_to_use) if (ev and fcf_to_use and fcf_to_use != 0) else 0
        ev_ebit = (ev / ebit) if (ev and ebit and ebit != 0) else 0

        # DCF Model (10 Años + Perpetuidad + Ajuste Deuda/Efectivo)
        valor_intrinseco = 0
        diferencia = 0
        
        if fcf_to_use and fcf_to_use > 0 and shares > 0:
            pv_fcf_sum = 0
            current_fcf = fcf_to_use
            
            for i in range(1, 11):
                current_fcf *= (1 + growth)
                pv_fcf_sum += current_fcf / ((1 + discount) ** i)
            
            terminal_value = (current_fcf * (1 + perp_growth)) / (discount - perp_growth)
            pv_terminal_value = terminal_value / ((1 + discount) ** 10)
            
            enterprise_value_est = pv_fcf_sum + pv_terminal_value
            equity_value = enterprise_value_est + cash - debt
            
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
        print("\n--- ERROR INESPERADO ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)