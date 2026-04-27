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
  const period = document.getElementById('period-select').value;
  const rsiMin = document.getElementById('rsi-min').value;
  const rsiMax = document.getElementById('rsi-max').value;

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
  params.set('period', period);
  params.set('rsi_min', rsiMin);
  params.set('rsi_max', rsiMax);
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
    // TradingView 위젯 스크립트 재실행
    resultArea.querySelectorAll('script').forEach(function (oldScript) {
      const newScript = document.createElement('script');
      Array.from(oldScript.attributes).forEach(attr =>
        newScript.setAttribute(attr.name, attr.value)
      );
      newScript.textContent = oldScript.textContent;
      oldScript.parentNode.replaceChild(newScript, oldScript);
    });
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
