# Valuador de Acciones - Documentación Técnica

## Descripción General
Esta aplicación es una herramienta profesional de valuación de empresas en el mercado de valores. Utiliza el modelo de **Flujos de Caja Descontados (DCF - Discounted Cash Flow)** en su variante *Unlevered* (de la Empresa al Accionista) para calcular el valor intrínseco de una acción. Se integra con la API de Finnhub para extraer reportes financieros oficiales (10-K/10-Q) presentados ante la SEC, asegurando paridad matemática con los modelos utilizados por analistas financieros.

## Arquitectura y Tecnologías
* **Backend:** Python con FastAPI.
* **Frontend:** HTML, JavaScript puro y TailwindCSS (arquitectura de Dashboard en 4 columnas).
* **Proveedor de Datos:** Finnhub API (Webhooks y Endpoints REST).
* **Formato de Valores:** Estandarización de sufijos financieros (M = Millones, B = Billones/Miles de Millones, T = Trillones).

## Metodología de Valuación (DCF)

El núcleo de la aplicación proyecta la generación de efectivo futura de la empresa y la trae a valor presente para determinar si la acción está sobrevalorada o infravalorada en el mercado.

1. **Cálculo del Año Base (FCF):** Se obtiene restando los Gastos de Capital (CapEx) del Flujo de Caja Operativo (Operating Cash Flow).
2. **Proyección de Flujos:** Se aplica una tasa de crecimiento anual (Growth Rate) sobre el FCF base durante un período definido (ej. 5 a 10 años).
3. **Descuento a Valor Presente (PV):** Cada flujo futuro se descuenta utilizando una tasa de descuento (WACC/Discount Rate).
4. **Valor Terminal (Gordon Growth Model):** Se asume un crecimiento perpetuo conservador (Terminal Rate) a partir del último año proyectado para calcular el valor residual de la empresa.
5. **Ajuste de Deuda Neta:** 
   * $Enterprise Value del DCF = Suma de Flujos Descontados + Valor Terminal Descontado$
   * $Equity Value = Enterprise Value del DCF - Deuda Neta$
6. **Valor Intrínseco por Acción:** Se divide el *Equity Value* por la cantidad total de acciones en circulación (Shares Outstanding).

## Endpoints de la API

### `GET /api/analizar/{ticker}`
Obtiene los datos financieros de la empresa, proyecta el modelo DCF y devuelve el análisis de valuación comparativo.

**Parámetros (Query):**
* `growth` (float): Tasa de crecimiento anual estimada para el FCF (%).
* `discount` (float): Tasa de descuento o WACC (%).
* `terminal` (float): Tasa de crecimiento perpetuo a largo plazo (%). Debe ser menor a `discount`.
* `years` (int): Cantidad de años a proyectar antes de calcular el valor terminal.

**Respuesta Exitosa (JSON):**
```json
{
  "ticker": "AAPL",
  "precio": 175.50,
  "valor_intrinseco": 182.20,
  "diferencia": 6.70,
  "diferencia_pct": 3.81,
  "eps": 6.12,
  "peg": 1.4,
  "per": 28.6,
  "roic": 32.5,
  "ev": 2850000000000,
  "fcf": 105000000000,
  "ebit": 114000000000,
  "ev_fcf": 27.1,
  "ev_ebit": 25.0
}