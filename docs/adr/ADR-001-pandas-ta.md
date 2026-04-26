# ADR-001: pandas-ta 사용

**Status:** Accepted  
**Date:** 2026-04-23

## Decision
기술적 지표 계산에 `pandas-ta` 라이브러리를 사용한다.

## Rationale
7개 지표(MA, RSI, MACD, Bollinger Bands, Volume MA)를 단일 라이브러리로 처리해 코드 복잡도를 낮춘다. `ta-lib`은 C 컴파일이 필요해 환경 설정이 복잡하므로 제외.

## Consequences
- pandas-ta API 변경 시 indicators.py 수정 필요
- 필요 시 직접 계산 로직으로 교체 가능 (인터페이스는 동일 유지)
