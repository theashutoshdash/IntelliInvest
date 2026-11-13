(function () {
  const byId = (id) => document.getElementById(id);
  const appShell = byId('appShell');
  const sidebar = byId('sidebar');
  const scrim = byId('sidebarScrim');

  document.addEventListener('DOMContentLoaded', () => {
    const dateNode = byId('localDate');
    if (dateNode) {
      dateNode.textContent = new Intl.DateTimeFormat('en-IN', {
        weekday: 'short', day: '2-digit', month: 'short', year: 'numeric'
      }).format(new Date());
    }

    const menu = byId('mobileMenu');
    const collapse = byId('sidebarCollapse');
    const closeMobileSidebar = () => {
      sidebar?.classList.remove('open');
      scrim?.classList.remove('active');
    };
    if (appShell && localStorage.getItem('ii-sidebar-collapsed') === '1' && window.innerWidth > 860) {
      appShell.classList.add('sidebar-collapsed');
    }
    collapse?.addEventListener('click', () => {
      appShell?.classList.toggle('sidebar-collapsed');
      localStorage.setItem('ii-sidebar-collapsed', appShell?.classList.contains('sidebar-collapsed') ? '1' : '0');
    });
    menu?.addEventListener('click', () => {
      sidebar?.classList.toggle('open');
      scrim?.classList.toggle('active');
    });
    scrim?.addEventListener('click', closeMobileSidebar);
    document.addEventListener('click', (event) => {
      if (window.innerWidth <= 860 && sidebar?.classList.contains('open') &&
          !sidebar.contains(event.target) && !menu?.contains(event.target)) closeMobileSidebar();
    });

    document.querySelectorAll('.flash-close').forEach((button) => {
      button.addEventListener('click', () => button.closest('.flash')?.remove());
    });

    // Live quote ribbon: snapshots refresh periodically; upstream data may be delayed.
    const ticker = byId('marketTicker');
    const status = byId('marketStatus');
    const nextSession = byId('marketNextSession');
    let eventAt = null;
    let eventLabel = 'Next session';
    const renderTicker = (quotes) => {
      if (!ticker) return;
      const track = document.createElement('div');
      track.className = 'ticker-track';
      (quotes || []).forEach((quote) => {
        const item = document.createElement('span');
        item.className = 'ticker-quote';
        item.title = [quote.source, quote.as_of, quote.stale ? 'Last completed close' : 'Quote snapshot'].filter(Boolean).join(' · ');
        const name = document.createElement('span');
        name.textContent = quote.name || quote.symbol;
        const price = document.createElement('strong');
        price.textContent = quote.price_display || '—';
        const change = document.createElement('span');
        const pct = Number(quote.change_pct);
        change.className = Number.isFinite(pct) ? (pct >= 0 ? 'up' : 'down') : '';
        change.textContent = Number.isFinite(pct) ? `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%` : '—';
        item.append(name, price, change);
        track.append(item);
      });
      if (track.children.length) {
        const clone = track.cloneNode(true);
        clone.setAttribute('aria-hidden', 'true');
        ticker.replaceChildren(track, clone);
      } else {
        ticker.textContent = 'Market data unavailable';
      }
    };
    const updateCountdown = () => {
      if (!nextSession || !eventAt) return;
      const remaining = Math.max(0, Math.floor((eventAt.getTime() - Date.now()) / 1000));
      const hours = String(Math.floor(remaining / 3600)).padStart(2, '0');
      const minutes = String(Math.floor((remaining % 3600) / 60)).padStart(2, '0');
      const seconds = String(remaining % 60).padStart(2, '0');
      nextSession.textContent = `${eventLabel} · ${hours}:${minutes}:${seconds}`;
    };
    let marketRefreshTimer = null;
    const refreshMarket = async () => {
      try {
        const response = await fetch('/api/market-overview', { headers: { 'Accept': 'application/json' }, cache: 'no-store' });
        if (!response.ok) throw new Error('Market service unavailable');
        const payload = await response.json();
        renderTicker(payload.quotes || []);
        if (payload.clock && status) {
          const clock = payload.clock;
          status.classList.toggle('is-open', clock.status === 'OPEN');
          status.classList.toggle('is-preopen', clock.status === 'PRE-OPEN');
          const label = clock.status === 'OPEN' ? 'MARKET OPEN' : clock.status === 'PRE-OPEN' ? 'PRE-OPEN' : 'MARKET CLOSED';
          status.innerHTML = `<i></i> ${label}`;
          eventAt = new Date(clock.event_at);
          eventLabel = clock.event_label || 'Next session';
          updateCountdown();
          // Refresh more frequently during the trading session, less often after hours.
          const delay = (clock.status === 'OPEN' || clock.status === 'PRE-OPEN') ? 30000 : 180000;
          if (marketRefreshTimer) window.clearTimeout(marketRefreshTimer);
          marketRefreshTimer = window.setTimeout(refreshMarket, delay);
        }
      } catch (_error) {
        if (ticker) ticker.textContent = 'Market feed unavailable';
        if (status) status.textContent = 'MARKET DATA';
        if (nextSession) nextSession.textContent = 'Retrying shortly';
        if (marketRefreshTimer) window.clearTimeout(marketRefreshTimer);
        marketRefreshTimer = window.setTimeout(refreshMarket, 90000);
      }
    };
    if (ticker || status) {
      refreshMarket();
      window.setInterval(updateCountdown, 1000);
    }

    // Interactive NIFTY chart: line, bar and candlestick; period changes fetch new OHLCV.
    const indexNode = byId('indexChart');
    const chartType = byId('chartType');
    const chartPeriod = byId('chartPeriod');
    const chartSymbol = byId('chartSymbol');
    const chartTitle = byId('chartTitle');
    const chartAsOf = byId('chartAsOf');
    let activeIndexSeries = window.iiIndexChart || null;
    const plotIndex = (series) => {
      if (!indexNode || !series || typeof Plotly === 'undefined') return;
      activeIndexSeries = series;
      const type = chartType?.value || 'line';
      const seriesName = series.name || 'Market index';
      let trace;
      if (type === 'candlestick') {
        trace = { type: 'candlestick', x: series.dates, open: series.open, high: series.high,
          low: series.low, close: series.close, increasing: { line: { color: '#6f9e86' } },
          decreasing: { line: { color: '#b77772' } }, name: seriesName };
      } else if (type === 'bar') {
        trace = { type: 'bar', x: series.dates, y: series.close, marker: { color: '#8ebcaf' }, name: 'Close' };
      } else if (type === 'area') {
        trace = { type: 'scatter', mode: 'lines', x: series.dates, y: series.close,
          line: { color: '#8ebcaf', width: 2 }, fill: 'tozeroy', fillcolor: 'rgba(142,188,175,.16)', name: 'Close' };
      } else {
        trace = { type: 'scatter', mode: 'lines', x: series.dates, y: series.close,
          line: { color: '#8ebcaf', width: 2 }, name: 'Close' };
      }
      const isLight = document.body.dataset.theme === 'light';
      const layout = {
        autosize: true, height: 300, margin: { l: 52, r: 18, t: 12, b: 38 },
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        font: { family: 'DM Sans, sans-serif', color: isLight ? '#65736b' : '#91a39a', size: 10 },
        xaxis: { type: 'date', showgrid: false, rangeslider: { visible: false }, linecolor: 'rgba(130,150,140,.13)' },
        yaxis: { showgrid: true, gridcolor: 'rgba(130,150,140,.11)', zeroline: false, side: 'right' },
        showlegend: false, dragmode: 'pan'
      };
      Plotly.react(indexNode, [trace], layout, { responsive: true, displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'] });
      if (chartTitle) chartTitle.textContent = seriesName;
      if (chartAsOf) chartAsOf.textContent = `Last observation · ${series.as_of || '—'}`;
    };
    const loadIndexSeries = async () => {
      if (!indexNode) return;
      const period = chartPeriod?.value || '1y';
      const symbol = chartSymbol?.value || 'NIFTY50';
      try {
        const url = `${window.iiIndexEndpoint || '/api/index-chart'}?period=${encodeURIComponent(period)}&symbol=${encodeURIComponent(symbol)}`;
        const response = await fetch(url, { headers: { 'Accept': 'application/json' }, cache: 'no-store' });
        if (!response.ok) throw new Error('Chart data unavailable');
        plotIndex(await response.json());
      } catch (_error) {
        if (chartAsOf) chartAsOf.textContent = 'Market history unavailable';
      }
    };
    if (indexNode && typeof Plotly !== 'undefined') {
      plotIndex(activeIndexSeries);
      chartType?.addEventListener('change', () => plotIndex(activeIndexSeries));
      chartPeriod?.addEventListener('change', loadIndexSeries);
      chartSymbol?.addEventListener('change', loadIndexSeries);
    }

    // Watchlist prices refresh without reloading the page.
    const watchlistRoot = byId('watchlistLive');
    if (watchlistRoot) {
      const view = watchlistRoot.dataset.view || '';
      const refreshWatchlist = async () => {
        try {
          const response = await fetch(`/api/watchlist?view=${encodeURIComponent(view)}`, { cache: 'no-store' });
          if (!response.ok) return;
          const quotes = await response.json();
          quotes.forEach((quote) => {
            const row = watchlistRoot.querySelector(`[data-symbol="${CSS.escape(quote.symbol)}"]`);
            if (!row) return;
            const priceCell = row.querySelector('[data-quote-price]');
            const changeCell = row.querySelector('[data-quote-change]');
            const asOfCell = row.querySelector('[data-quote-asof]');
            if (priceCell) priceCell.textContent = quote.available && quote.price != null ? `₹${Number(quote.price).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : '—';
            if (changeCell) {
              const value = Number(quote.change_pct);
              changeCell.textContent = quote.available && Number.isFinite(value) ? `${value >= 0 ? '+' : ''}${value.toFixed(2)}%` : '—';
              changeCell.classList.toggle('positive', Number.isFinite(value) && value >= 0);
              changeCell.classList.toggle('negative', Number.isFinite(value) && value < 0);
            }
            if (asOfCell) asOfCell.textContent = quote.as_of || '—';
          });
        } catch (_error) { /* Preserve the last rendered snapshot. */ }
      };
      refreshWatchlist();
      window.setInterval(refreshWatchlist, 45000);
    }

    if (typeof Chart === 'undefined') return;
    Chart.defaults.color = document.body.dataset.theme === 'light' ? '#68756e' : '#82928a';
    Chart.defaults.font.family = "'DM Sans', sans-serif";
    Chart.defaults.font.size = 10;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.boxWidth = 7;
    Chart.defaults.plugins.legend.labels.padding = 16;

    const forecastCanvas = byId('forecastChart');
    if (forecastCanvas && window.iiForecastChart) {
      new Chart(forecastCanvas, {
        type: 'line',
        data: { labels: window.iiForecastChart.labels, datasets: [
          { label: 'Actual 5-session return', data: window.iiForecastChart.actual, borderColor: '#8ebcaf', borderWidth: 1.5, pointRadius: 0, tension: .15 },
          { label: 'Model estimate', data: window.iiForecastChart.predicted, borderColor: '#c7ae85', borderDash: [4, 4], borderWidth: 1.2, pointRadius: 0, tension: .15 }
        ] },
        options: { responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: 'top', align: 'end' }, tooltip: { intersect: false, mode: 'index' } },
          scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 8, maxRotation: 0 } },
            y: { title: { display: true, text: 'Return (%)' }, grid: { color: 'rgba(130,150,140,.11)' }, border: { display: false } } },
          interaction: { intersect: false, mode: 'index' } }
      });
    }
  });
})();
