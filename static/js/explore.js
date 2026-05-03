const tickerSearch = new TomSelect('#ticker-search', {
  valueField: 'symbol',
  labelField: 'symbol',
  searchField: ['symbol', 'name'],
  maxItems: 5,
  create: true,
  load(query, callback) {
    if (!query.length) return callback();
    fetch(`/api/tickers?q=${encodeURIComponent(query)}`)
      .then(r => r.json())
      .then(data => callback(data))
      .catch(() => callback());
  },
  render: {
    option: (d, escape) => `<div><strong>${escape(d.symbol)}</strong> <span style="font-size:0.8em;color:#718096">${escape(d.name||'')}</span></div>`,
    item: (d, escape) => `<div>${escape(d.symbol)}</div>`,
  }
});

let _evtSource = null;

function _startStream(tickers = []) {
  const area = document.getElementById('explore-result-area');
  if (_evtSource) _evtSource.close();

  const params = new URLSearchParams();
  if (tickers.length) params.set('tickers', tickers.join(','));

  area.innerHTML = '<div class="polling"><p class="status-text">⏳ 실시간 기회 분석 중...</p></div>';

  _evtSource = new EventSource(`/stream/explore?${params}`);

  _evtSource.addEventListener('progress', e => {
    const data = JSON.parse(e.data);
    area.innerHTML = `<div class="polling"><p class="status-text">⏳ ${data.stage}</p></div>`;
  });

  _evtSource.addEventListener('done', e => {
    _evtSource.close();
    const data = JSON.parse(e.data);
    area.innerHTML = data.html;
  });

  _evtSource.addEventListener('error', e => {
    _evtSource.close();
    area.innerHTML = '<div class="error-box"><p>❌ 분석 중 오류가 발생했습니다. 잠시 후 다시 시도하세요.</p></div>';
  });
}

document.getElementById('explore-form').addEventListener('submit', e => {
  e.preventDefault();
  const values = tickerSearch.getValue();
  const tickers = (Array.isArray(values) ? values : [values]).filter(Boolean);
  _startStream(tickers);
});

// ── 차트 모달 (통합 버전) ──────────────────────────────────

let _lwChart = null;
let _candleSeries = null;
let _allMarkers = [];

document.addEventListener('click', e => {
  const btn = e.target.closest('.chart-btn');
  if (!btn) return;
  const card = btn.closest('.explore-card');
  if (card) _openModal(card);
});

function _openModal(card) {
  const ticker = card.dataset.ticker;
  const detail = card.querySelector('.card-detail');
  const company = card.querySelector('.short-name')?.textContent || '';

  document.getElementById('modal-ticker').textContent = ticker;
  document.getElementById('modal-company').textContent = company;
  document.getElementById('modal-detail').innerHTML = detail ? detail.innerHTML : '';

  document.getElementById('chart-modal').classList.add('is-open');
  _fetchAndRenderChart(ticker);
}

function _closeModal() {
  document.getElementById('chart-modal').classList.remove('is-open');
  if (_lwChart) {
    _lwChart.remove();
    _lwChart = null;
  }
}

async function _fetchAndRenderChart(ticker) {
  const container = document.getElementById('lw-chart-container');
  container.innerHTML = '<p style="color:var(--text3);padding:1rem;text-align:center">차트 로딩 중...</p>';
  try {
    const res = await fetch(`/api/chart-data/${ticker}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    container.innerHTML = '';
    const chart = LightweightCharts.createChart(container, {
      width: container.clientWidth, height: 450,
      layout: { background: { color: '#0f1117' }, textColor: '#94a3b8' },
      grid: { vertLines: { color: 'rgba(255,255,255,0.03)' }, horzLines: { color: 'rgba(255,255,255,0.03)' } },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.07)' },
      timeScale: { borderColor: 'rgba(255,255,255,0.07)', timeVisible: true },
    });
    _lwChart = chart;

    const volSeries = chart.addHistogramSeries({
      priceScaleId: 'volume', priceFormat: { type: 'volume' },
      scaleMargins: { top: 0.85, bottom: 0 },
    });
    volSeries.setData(data.ohlcv.map(b => ({
      time: b.time, value: b.volume,
      color: b.close >= b.open ? 'rgba(52,211,153,0.15)' : 'rgba(244,63,94,0.15)',
    })));

    const candle = chart.addCandlestickSeries({
      upColor: '#10b981', downColor: '#f43f5e',
      borderUpColor: '#10b981', borderDownColor: '#f43f5e',
      wickUpColor: '#10b981', wickDownColor: '#f43f5e',
    });
    candle.setData(data.ohlcv);
    _candleSeries = candle;

    if (data.ma20) {
      const maSeries = chart.addLineSeries({ color: '#63b3ed', lineWidth: 1, priceLineVisible: false });
      maSeries.setData(data.ma20);
    }

    if (data.markers) {
      const markers = data.markers.map(m => ({
        time: m.time, position: m.type==='buy'?'belowBar':'aboveBar',
        shape: m.type==='buy'?'arrowUp':'arrowDown', color: m.type==='buy'?'#10b981':'#f43f5e',
        text: m.type==='buy'?'B':'S', size: 1
      }));
      candle.setMarkers(markers);
    }

    new ResizeObserver(() => { if (_lwChart) _lwChart.applyOptions({ width: container.clientWidth }); }).observe(container);

  } catch (err) {
    container.innerHTML = `<p style="color:#f43f5e;padding:1rem;text-align:center">데이터 오류: ${err.message}</p>`;
  }
}

document.getElementById('modal-close').addEventListener('click', _closeModal);
document.getElementById('chart-modal').addEventListener('click', e => { if (e.target === e.currentTarget) _closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') _closeModal(); });

// ── 페이지 로드 시 가이드만 표시 (자동 분석 비활성화) ─────────────────

document.querySelector('.suggest-btn').addEventListener('click', e => {
  const tickers = e.target.dataset.tickers ? e.target.dataset.tickers.split(',') : [];
  tickerSearch.clear();
  _startStream(tickers);
});
