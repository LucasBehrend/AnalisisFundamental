document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('calcBtn');
    const input = document.getElementById('tickerInput');
    const statusMsg = document.getElementById('statusMessage');

    // Formatters correctos nativos de JS
    const currencyFmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
    const compactFmt = new Intl.NumberFormat('en-US', { notation: "compact", compactDisplay: "short", maximumFractionDigits: 1 });
    const numberFmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
    const percentFmt = new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 2 });

    function showStatus(msg, colorClass) {
        statusMsg.textContent = msg;
        statusMsg.className = `text-sm h-5 transition-colors duration-300 ${colorClass}`;
    }

    function resetGrid() {
        const elements = ['val-price', 'val-intrinsic', 'val-diff', 'val-peg', 'val-per', 'val-ev', 'val-fcf', 'val-ebit', 'val-evfcf', 'val-evebit'];
        elements.forEach(id => {
            const el = document.getElementById(id);
            el.textContent = '---';
            if (id === 'val-diff') el.className = 'metric-value';
        });
    }

    function updateGrid(data) {
        document.getElementById('val-price').textContent = data.price ? currencyFmt.format(data.price) : 'N/A';
        document.getElementById('val-intrinsic').textContent = data.intrinsic ? currencyFmt.format(data.intrinsic) : 'N/A';
        
        const diffEl = document.getElementById('val-diff');
        if (data.diff) {
            diffEl.textContent = percentFmt.format(data.diff);
            // Colorear verde si está infravalorada, rojo si está sobrevalorada
            diffEl.className = data.diff > 0 ? 'metric-value text-emerald-400' : 'metric-value text-red-400';
        } else {
            diffEl.textContent = 'N/A';
        }

        document.getElementById('val-peg').textContent = data.peg ? numberFmt.format(data.peg) : 'N/A';
        document.getElementById('val-per').textContent = data.per ? numberFmt.format(data.per) : 'N/A';
        document.getElementById('val-ev').textContent = data.ev ? '$' + compactFmt.format(data.ev) : 'N/A';
        document.getElementById('val-fcf').textContent = data.fcf ? '$' + compactFmt.format(data.fcf) : 'N/A';
        document.getElementById('val-ebit').textContent = data.ebit ? '$' + compactFmt.format(data.ebit) : 'N/A';
        document.getElementById('val-evfcf').textContent = data.ev_fcf ? numberFmt.format(data.ev_fcf) + 'x' : 'N/A';
        document.getElementById('val-evebit').textContent = data.ev_ebit ? numberFmt.format(data.ev_ebit) + 'x' : 'N/A';
    }

    btn.addEventListener('click', async () => {
        const ticker = input.value.trim();
        if (!ticker) {
            showStatus('Por favor, ingresa un ticker.', 'text-red-400');
            return;
        }

        // Obtener valores manuales y convertirlos a decimales
        const growth = parseFloat(document.getElementById('growthInput').value) / 100 || 0.05;
        const discount = parseFloat(document.getElementById('discountInput').value) / 100 || 0.10;
        const terminal = parseFloat(document.getElementById('terminalInput').value) || 15;

        showStatus('Consultando datos y calculando...', 'text-yellow-400');
        resetGrid();

        try {
            // Se pasan las estimaciones manuales por URL (Query Params)
            const url = `http://localhost:8000/api/valuate/${ticker}?growth=${growth}&discount=${discount}&terminal=${terminal}`;
            const response = await fetch(url);
            
            if (!response.ok) throw new Error('Error al buscar el ticker o sin datos.');
            
            const data = await response.json();
            updateGrid(data);
            showStatus('Cálculo completado exitosamente.', 'text-emerald-400');

        } catch (error) {
            showStatus(error.message, 'text-red-400');
        }
    });

    // Permitir Enter
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') btn.click();
    });
});