@echo off
chcp 65001 > nul
cd /d "%~dp0"
if not exist ".env" copy ".env.example" ".env" > nul
if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Python 가상환경 생성 중...
  py -3 -m venv .venv
)
echo [2/4] Python 패키지 확인 중...
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if exist "data\legal\articles.json" (
  echo 법령 데이터 준비 중...
  pushd backend
  ..\.venv\Scripts\python.exe -m app.legal.ingest --from-json > nul
  if errorlevel 1 echo 경고: 법령 데이터 준비에 실패했습니다. 근거 조문이 표시되지 않을 수 있습니다.
  popd
)
if not exist "frontend\node_modules" (
  echo [3/4] 프론트엔드 패키지 설치 중...
  pushd frontend
  call npm install
  popd
)
echo [4/4] 디딤을 시작합니다. 브라우저: http://localhost:5173
start "디딤 API" cmd /k "cd /d %~dp0 && .venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000"
start "디딤 화면" cmd /k "cd /d %~dp0frontend && npm run dev"
timeout /t 4 /nobreak > nul
start http://localhost:5173

