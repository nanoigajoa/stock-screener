const tickerSelect = new TomSelect('#ticker-select', {
  valueField: 'symbol',
  labelField: 'symbol',
  searchField: ['symbol', 'name'],
  maxItems: 20,
  create: true,
  createOnBlur: false,
  persist: false,
  placeholder: '예: AAPL MSFT NVDA',
  load(query, callback) {
    if (!query.length) return callback();
    fetch(`/api/tickers?q=${encodeURIComponent(query)}`)
      .then(r => r.json())
      .then(data => callback(data))
      .catch(() => callback());
  },
  render: {
    option: (d, escape) =>
      `<div>
        <strong>${escape(d.symbol)}</strong>
        <span class="ts-name">${escape(d.name || '')}</span>
      </div>`,
    item: (d, escape) => `<div>${escape(d.symbol)}</div>`,
  },
});

function toggleAdvanced() {
  const panel = document.getElementById('advanced-settings');
  const arrow = document.getElementById('advanced-arrow');
  const open = panel.style.display !== 'none';
  panel.style.display = open ? 'none' : 'block';
  arrow.textContent = open ? '▼' : '▲';
}

document.getElementById('screen-form').addEventListener('submit', function (e) {
  e.preventDefault();

  const values = tickerSelect.getValue();
  const tickers = (Array.isArray(values) ? values : [values]).filter(Boolean).join(',');
  const gradeFilter = document.getElementById('grade-filter').value;
  const rsiMin = document.getElementById('rsi-min').value;
  const rsiMax = document.getElementById('rsi-max').value;
  const target1 = document.getElementById('target-1').value;
  const target2 = document.getElementById('target-2').value;
  const stopLoss = document.getElementById('stop-loss').value;

  const allChecks = ['ma_alignment', 'rsi', 'volume', 'macd', 'support', 'bollinger', 'trend'];
  const checked = Array.from(document.querySelectorAll('input[name="checks"]:checked')).map(el => el.value);
  const allSelected = checked.length === allChecks.length;

  const resultArea = document.getElementById('result-area');
  const submitBtn = document.getElementById('submit-btn');

  submitBtn.disabled = true;
  submitBtn.textContent = '분석 중...';
  resultArea.innerHTML = '<div class="polling"><p class="status-text">⏳ 스크리닝 시작...</p></div>';

  const params = new URLSearchParams();
  if (tickers) params.set('tickers', tickers);
  if (gradeFilter) params.set('grade_filter', gradeFilter);
  params.set('rsi_min', rsiMin);
  params.set('rsi_max', rsiMax);
  params.set('target_1', target1);
  params.set('target_2', target2);
  params.set('stop_loss', stopLoss);
  if (!allSelected) params.set('checks', checked.join(','));

  const evtSource = new EventSource(`/stream/screen?${params}`);

  function finish() {
    submitBtn.disabled = false;
    submitBtn.textContent = '스크리닝 시작';
  }

  evtSource.addEventListener('progress', function (e) {
    const data = JSON.parse(e.data);
    resultArea.innerHTML = `<div class="polling"><p class="status-text">⏳ ${data.stage}</p></div>`;
  });

  evtSource.addEventListener('done', function (e) {
    evtSource.close();
    finish();
    const data = JSON.parse(e.data);
    resultArea.innerHTML = data.html;
    document.getElementById('screen-filter-bar').style.display = 'flex';
    _markWatchlistBtns();
  });

  evtSource.addEventListener('error', function (e) {
    evtSource.close();
    finish();
    try {
      const data = JSON.parse(e.data);
      resultArea.innerHTML = `<div class="error-box"><p>❌ 오류: ${data.message}</p></div>`;
    } catch {
      resultArea.innerHTML = '<div class="error-box"><p>❌ 알 수 없는 오류가 발생했습니다.</p></div>';
    }
  });

  evtSource.onerror = function () {
    if (!evtSource.CLOSED) return;
    finish();
    if (resultArea.querySelector('.polling')) {
      resultArea.innerHTML = '<div class="error-box"><p>❌ 서버 연결이 끊겼습니다.</p></div>';
    }
  };
});

// ── Watchlist 브리지 ──────────────────────────────────────

let _watchlistSet = new Set();

(async function () {
  try {
    const res = await fetch('/api/watchlist');
    const data = await res.json();
    _watchlistSet = new Set(data.tickers);
  } catch {}
})();

function _markWatchlistBtns() {
  document.querySelectorAll('.watchlist-btn').forEach(btn => {
    const ticker = btn.dataset.ticker;
    if (_watchlistSet.has(ticker)) {
      btn.classList.add('wl-added');
      btn.title = '관심종목에 추가됨';
    }
  });
}

document.addEventListener('click', async function (e) {
  const btn = e.target.closest('.watchlist-btn');
  if (!btn || btn.classList.contains('wl-added')) return;
  const ticker = btn.dataset.ticker;
  try {
    await fetch(`/api/watchlist/${ticker}`, { method: 'POST' });
    _watchlistSet.add(ticker);
    btn.classList.add('wl-added');
    btn.title = '관심종목에 추가됨';
  } catch {}
});

// ── 차트 모달 ─────────────────────────────────────────────

let _lwChart = null;
let _candleSeries = null;
let _allMarkers = [];
let _currentTicker = null;

// 이벤트 위임 — 카드 "차트 분석" 버튼
document.addEventListener('click', function (e) {
  const btn = e.target.closest('.chart-btn');
  if (!btn) return;
  const card = btn.closest('.stock-card') || btn.closest('.signal-card');
  if (!card) return;
  _openModal(card);
});

function _openModal(card) {
  const ticker = card.dataset.ticker;
  const detail = card.querySelector('.card-detail');
  _currentTicker = ticker;

  document.getElementById('modal-ticker').textContent = ticker;
  document.getElementById('modal-detail').innerHTML = detail ? detail.innerHTML : '';
  
  // 회사명 추출 (추가 정보 표시용)
  const company = card.querySelector('.short-name')?.textContent || '';
  document.getElementById('modal-company').textContent = company;

  document.getElementById('chart-modal').classList.add('is-open');
  _fetchAndRenderChart(ticker);
}

function _closeModal() {
  document.getElementById('chart-modal').classList.remove('is-open');
  if (_lwChart) {
    _lwChart.remove();
    _lwChart = null;
    _candleSeries = null;
    _allMarkers = [];
    _currentTicker = null;
  }
}

async function _fetchAndRenderChart(ticker) {
  const container = document.getElementById('lw-chart-container');
  container.innerHTML = '<p style="color:var(--text3);padding:1rem;text-align:center">차트 로딩 중...</p>';

  try {
    const res = await fetch(`/api/chart-data/${ticker}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (_lwChart) _lwChart.remove();
    container.innerHTML = '';

    const chart = LightweightCharts.createChart(container, {
      width: container.clientWidth,
      height: 450,
      layout: { background: { color: '#050810' }, textColor: '#94a3b8' },
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

    if (data.ma20 && data.ma20.length) {
      const maSeries = chart.addLineSeries({
        color: 'rgba(99,179,237,0.8)', lineWidth: 1,
        priceLineVisible: false, lastValueVisible: false,
      });
      maSeries.setData(data.ma20);
    }

    _allMarkers = data.markers || [];
    _applyMarkers();

    new ResizeObserver(() => {
      if (_lwChart) _lwChart.applyOptions({ width: container.clientWidth });
    }).observe(container);

  } catch (err) {
    container.innerHTML = `<p style="color:#f87171;padding:1rem;text-align:center">차트 로드 실패: ${err.message}</p>`;
  }
}

function _applyMarkers() {
  if (!_candleSeries) return;
  const markers = _allMarkers.map(m => ({
    time:     m.time,
    position: m.type === 'buy' ? 'belowBar' : 'aboveBar',
    shape:    m.type === 'buy' ? 'arrowUp'  : 'arrowDown',
    color:    m.type === 'buy' ? '#34d399'  : '#f87171',
    text:     m.type === 'buy' ? 'B' : 'S',
    size: 1,
  }));
  _candleSeries.setMarkers(markers);
}

document.querySelectorAll('#screen-filter-bar .pill').forEach(btn => {
  btn.addEventListener('click', function () {
    const grade = this.dataset.grade;
    document.querySelectorAll('#screen-filter-bar .pill').forEach(b => b.classList.remove('is-active'));
    this.classList.add('is-active');

    document.querySelectorAll('#result-area .stock-card').forEach(card => {
      const cardGrade = card.querySelector('.gt-letter')?.textContent || '';
      card.style.display = (!grade || cardGrade === grade) ? '' : 'none';
    });
  });
});

document.getElementById('modal-close').addEventListener('click', _closeModal);
document.getElementById('chart-modal').addEventListener('click', function (e) {
  if (e.target === this) _closeModal();
});
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') _closeModal();
});
