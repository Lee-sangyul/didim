#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
# 법령 근거 조문 DB 준비 (data/legal/articles.json -> data/legal/legal.db). 실패해도 시작은 계속한다.
[ -f data/legal/articles.json ] && ( (cd backend && ../.venv/bin/python -m app.legal.ingest --from-json > /dev/null) || echo "경고: 법령 데이터 준비에 실패했습니다. 근거 조문이 표시되지 않을 수 있습니다." )
[ -d frontend/node_modules ] || (cd frontend && npm install)
trap 'kill 0' EXIT
.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --port 8000 &
(cd frontend && npm run dev) &
echo "디딤: http://localhost:5173"
wait

