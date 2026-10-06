from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import uvicorn

app = FastAPI(title="Stock Valuation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/valuate/{ticker}")
def valuate_stock(ticker: str, growth: float = 0.05, discount: float = 0.10, terminal: float = 15.0):
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info

        if 'currentPrice' not in info and 'regularMarketPrice' not in info:
            raise HTTPException(status_code=404, detail="Ticker no encontrado.")

        # Extracción
        precio_actual = info.get('currentPrice', info.get('regularMarketPrice'))
        per = info.get('trailingPE', 0)
        peg = info.get('pegRatio', 0)
        ev = info.get('enterpriseValue', 0)
        fcf = info.get('freeCashflow', 0)
        
        ebit = 0
        try:
            financials = stock.financials
            if 'EBIT' in financials.index:
                ebit = financials.loc['EBIT'].iloc[0]
        except Exception:
            pass

        # Ratios
        ev_fcf = (ev / fcf) if fcf and fcf != 0 else 0
        ev_ebit = (ev / ebit) if ebit and ebit != 0 else 0

        # DCF Model
        valor_intrinseco = 0
        diferencia = 0
        
        if fcf and fcf > 0 and 'sharesOutstanding' in info:
            shares = info.get('sharesOutstanding')
            fcf_per_share = fcf / shares
            
            iv = 0
            current_fcf = fcf_per_share
            # 5 year projection
            for i in range(1, 6):
                current_fcf *= (1 + growth)
                iv += current_fcf / ((1 + discount) ** i)
            
            # Terminal Value
            terminal_value = (current_fcf * terminal) / ((1 + discount) ** 5)
            iv += terminal_value
            valor_intrinseco = iv
            
            if precio_actual:
                diferencia = (valor_intrinseco - precio_actual) / precio_actual

        return {
            "price": precio_actual or 0,
            "intrinsic": valor_intrinseco or 0,
            "diff": diferencia or 0,
            "peg": peg or 0,
            "per": per or 0,
            "ev": ev or 0,
            "fcf": fcf or 0,
            "ebit": ebit or 0,
            "ev_fcf": ev_fcf or 0,
            "ev_ebit": ev_ebit or 0
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)