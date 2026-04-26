# Phase 2 — Notifications

**Goal:** S급 종목 텔레그램/카카오 알림 발송

---

## Tasks

- [ ] `notifier/telegram.py`
  - S급 종목 결과를 텔레그램 메시지로 포맷
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 환경변수 사용
  - 메시지 형식: ticker / 현재가 / 등급 / 목표가 / 손절선

- [ ] KakaoTalk 알림 (`notifier/telegram.py` 내 또는 별도 파일)
  - `KAKAO_ACCESS_TOKEN` 환경변수 설정 시 활성화
  - 빈 토큰이면 자동 skip

- [ ] `.env` 파일 지원
  - `python-dotenv` 패키지 추가
  - `config.py`에서 `.env` 자동 로드
  - `.env.example` 파일 생성 (토큰 키 목록, 값은 비워둠)

- [ ] `main.py` 알림 연동
  - 등급 분류 후 `KAKAO_ALERT_GRADES` 기준으로 알림 발송
  - `--no-notify` 옵션 추가 (디버그용)

## Required Skills
- HTTP POST (requests), 텔레그램 Bot API

## Deliverables
- `notifier/telegram.py`
- `.env.example`
- `requirements.txt` 업데이트 (`python-dotenv` 추가)

## Definition of Done
- [ ] S급 종목 발생 시 텔레그램 메시지 수신
- [ ] `TELEGRAM_BOT_TOKEN` 미설정 시 알림 없이 정상 실행
- [ ] `.env` 파일로 토큰 관리 (코드 내 하드코딩 없음)
