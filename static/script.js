const form = document.getElementById("form");
const tickerInput = document.getElementById("ticker");
const btn = document.getElementById("btn");
const statusEl = document.getElementById("status");
const resultado = document.getElementById("resultado");
const crecimientoInput = document.getElementById("crecimiento");

const NA = "N/D";

const money = (v, cur = "USD") =>
  v == null
    ? NA
    : new Intl.NumberFormat("es-AR", { style: "currency", currency: cur }).format(v);

// Finnhub entrega EV, FCF y EBIT en millones
function bigMoney(millions, cur = "USD") {
  if (millions == null) return NA;
  const abs = Math.abs(millions);
  const [div, suf] =
    abs >= 1e6 ? [1e6, " B"] : abs >= 1e3 ? [1e3, " MM"] : [1, " M"];
  const n = new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(millions / div);
  return `${n}${suf} ${cur}`;
}

const num = (v) =>
  v == null ? NA : new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(v);
const mult = (v) => (v == null ? NA : `${num(v)}x`);

function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.classList.toggle("error", isError);
}

function render(d) {
  const cur = d.moneda;
  const set = (id, value) => (document.getElementById(id).value = value);

  document.getElementById("empresa").textContent = d.empresa
    ? `${d.empresa} (${d.ticker})`
    : d.ticker;

  set("precio", money(d.precio, cur));
  set("valor_intrinseco", money(d.valor_intrinseco, cur));

  const diff = d.diferencia;
  set(
    "diferencia",
    diff == null
      ? NA
      : `${diff > 0 ? "+" : ""}${money(diff, cur)} (${diff > 0 ? "+" : ""}${num(d.diferencia_pct)}%)`
  );
  const f = document.getElementById("f-diferencia");
  f.classList.toggle("pos", diff != null && diff > 0);
  f.classList.toggle("neg", diff != null && diff < 0);

  set("eps", money(d.eps, cur));
  set("per", mult(d.per));
  set("peg", num(d.peg));
  set("ev", bigMoney(d.ev, cur));
  set("fcf", bigMoney(d.fcf, cur));
  set("ebit", bigMoney(d.ebit, cur));
  set("ev_fcf", mult(d.ev_fcf));
  set("ev_ebit", mult(d.ev_ebit));

  // Si el crecimiento fue automático, mostrar qué valor se usó
  const sp = d.supuestos;
  crecimientoInput.placeholder = sp.crecimiento_auto ? `Auto (${num(sp.crecimiento)}%)` : "Auto";

  const nota = document.getElementById("metodo");
  nota.textContent =
    d.metodo === "DCF"
      ? `Valor intrínseco calculado con DCF a ${sp.anios} años (crecimiento ${num(sp.crecimiento)}%${sp.crecimiento_auto ? ", automático" : ""}, descuento ${num(sp.descuento)}%, crecimiento terminal ${num(sp.terminal)}%). N/D indica que Finnhub no tiene el dato o que el valor no es calculable (por ejemplo, un denominador negativo).`
      : d.metodo === "Graham"
      ? "Sin FCF positivo, el valor intrínseco se calculó con la fórmula de Graham (EPS × (8,5 + 2 × crecimiento)). N/D indica que Finnhub no tiene el dato o que el valor no es calculable."
      : "No hay datos suficientes para estimar el valor intrínseco de este ticker.";

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
    for (const id of ["crecimiento", "descuento", "terminal", "anios"]) {
      const v = document.getElementById(id).value.trim();
      if (v !== "") params.set(id, v);
    }
    const res = await fetch(`/api/analizar/${encodeURIComponent(ticker)}?${params}`);
    const data = await res.json();
    if (!res.ok) {
      // FastAPI devuelve detail como lista en errores de validación
      const msg = Array.isArray(data.detail)
        ? "Revisá los supuestos: hay un valor fuera de rango."
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
