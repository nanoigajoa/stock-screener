#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
echo "[FastAPI] http://localhost:8000"
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
