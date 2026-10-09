const form = document.getElementById("form");
const tickerInput = document.getElementById("ticker");
const btn = document.getElementById("btn");
const statusEl = document.getElementById("status");
const resultado = document.getElementById("resultado");

const NA = "N/D";

const money = (v, cur = "USD") =>
  v == null ? NA : new Intl.NumberFormat("es-AR", { style: "currency", currency: cur }).format(v);

// Nueva función para números grandes (B = Billions, M = Millions)
const formatCompact = (v, cur = "USD") => {
  if (v == null) return NA;
  const abs = Math.abs(v);
  let div = 1, suf = "";

  if (abs >= 1e12) {
    div = 1e12;
    suf = " T"; // Trillions
  } else if (abs >= 1e9) {
    div = 1e9;
    suf = " B"; // Billions
  } else if (abs >= 1e6) {
    div = 1e6;
    suf = " M"; // Millions
  }

  const n = new Intl.NumberFormat("es-AR", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0
  }).format(v / div);
  
  return `US$ ${n}${suf}`;
};

const num = (v) => v == null ? NA : new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(v);
const mult = (v) => (v == null ? NA : `${num(v)}x`);
const pct = (v) => (v == null ? NA : `${num(v)}%`);

function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.classList.toggle("error", isError);
}

function render(d) {
  const cur = "USD";
  const set = (id, value) => (document.getElementById(id).value = value);

  document.getElementById("empresa").textContent = d.ticker;

  set("precio", money(d.precio, cur));
  set("valor_intrinseco", money(d.valor_intrinseco, cur));

  // 1. Manejo de las dos cajas de diferencia
  const diff = d.diferencia;
  const diffPct = d.diferencia_pct;

  set("diferencia", diff == null ? NA : `${diff > 0 ? "+" : ""}${money(diff, cur)}`);
  set("diferencia_pct", diffPct == null ? NA : `${diffPct > 0 ? "+" : ""}${num(diffPct)}%`);
  
  // Colorear caja de diferencia en dólares
  const fDiff = document.getElementById("f-diferencia");
  fDiff.classList.toggle("pos", diff != null && diff > 0);
  fDiff.classList.toggle("neg", diff != null && diff < 0);

  // Colorear caja de diferencia porcentual
  const fDiffPct = document.getElementById("f-diferencia-pct");
  fDiffPct.classList.toggle("pos", diffPct != null && diffPct > 0);
  fDiffPct.classList.toggle("neg", diffPct != null && diffPct < 0);

  // ... (eps, per, peg, roic se mantienen igual) ...
  set("eps", money(d.eps, cur));
  set("per", mult(d.per));
  set("peg", num(d.peg));
  set("roic", pct(d.roic));
  
  // 2. FCF formateado igual que EV y EBIT
  set("ev", formatCompact(d.ev, cur));
  set("ebit", formatCompact(d.ebit, cur));
  set("fcf", formatCompact(d.fcf, cur)); // Al usar formatCompact, si envías el FCF total en dólares, se mostrará con 'M' o 'B'.
  
  set("ev_fcf", mult(d.ev_fcf));
  set("ev_ebit", mult(d.ev_ebit));

  resultado.hidden = false;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const ticker = tickerInput.value.trim();
  if (!ticker) return;

  btn.disabled = true;
  resultado.hidden = true;
  setStatus("Consultando datos...");

  try {
    const params = new URLSearchParams();
    for (const id of ["growth", "discount", "terminal", "years"]) {
      const v = document.getElementById(id).value.trim();
      if (v !== "") params.set(id, v);
    }
    
    const res = await fetch(`/api/analizar/${encodeURIComponent(ticker)}?${params}`);
    const data = await res.json();
    
    if (!res.ok) {
      const msg = Array.isArray(data.detail)
        ? "Revisá los supuestos: hay un valor fuera de rango o incompleto."
        : data.detail;
      throw new Error(msg || "Error inesperado.");
    }
    
    render(data);
    setStatus("");
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    btn.disabled = false;
  }
});