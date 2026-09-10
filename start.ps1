$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Set-Location $PSScriptRoot

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[1/4] Python 가상환경 생성 중..."
    py -3 -m venv .venv
}

Write-Host "[2/4] Python 패키지 확인 중..."
& ".venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"

if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "[3/4] 프론트엔드 패키지 설치 중..."
    Push-Location "frontend"
    npm install
    Pop-Location
}

Write-Host "[4/4] 디딤을 시작합니다. 브라우저: http://localhost:5173"

Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoExit", "-Command",
    "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; `$host.UI.RawUI.WindowTitle='디딤 API'; Set-Location '$PSScriptRoot'; .venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000"
)

Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoExit", "-Command",
    "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; `$host.UI.RawUI.WindowTitle='디딤 화면'; Set-Location '$PSScriptRoot\frontend'; npm run dev"
)

Start-Sleep -Seconds 4
Start-Process "http://localhost:5173"
