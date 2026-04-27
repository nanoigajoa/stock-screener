"""
의원거래 데이터 수동 갱신 스크립트.
실행: python scripts/download_congress_data.py

소스가 모두 막힌 경우:
  data/congress_trades.json 파일을 직접 교체하면 됨.
  (JSON 배열 형태, 각 항목에 ticker / type / transaction_date 필드 필요)
"""
import sys, json, time, requests
from pathlib import Path

OUT = Path(__file__).parent.parent / "data" / "congress_trades.json"

SOURCES = [
    ("House Stock Watcher", "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"),
    ("Senate Stock Watcher", "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"),
]

trades = []
for name, url in SOURCES:
    print(f"[{name}] 시도 중...", end=" ", flush=True)
    t0 = time.perf_counter()
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "StockScope/1.0"})
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            trades.extend(data)
            print(f"✅ {len(data)}건 ({time.perf_counter()-t0:.1f}s)")
    except Exception as e:
        print(f"❌ 실패: {e}")

if trades:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(trades, ensure_ascii=False), encoding="utf-8")
    print(f"\n저장 완료: {OUT} ({len(trades)}건)")
else:
    print("\n모든 소스 실패. 데이터 갱신 불가.")
    sys.exit(1)
