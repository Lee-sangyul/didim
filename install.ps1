$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Set-Location $PSScriptRoot

function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

Write-Host "===================================="
Write-Host " 디딤(DIDIM) 설치 프로그램"
Write-Host "===================================="

if (-not (Test-Command "winget")) {
    Write-Host ""
    Write-Host "[오류] winget(Windows 패키지 관리자)을 찾을 수 없습니다."
    Write-Host "Microsoft Store에서 'App Installer'를 설치한 뒤 이 파일을 다시 실행해 주세요."
    Write-Host "https://apps.microsoft.com/detail/9nblggh4nns1"
    Read-Host "종료하려면 Enter를 누르세요"
    exit 1
}

if (Test-Command "py") {
    Write-Host "[1/2] Python 확인됨 (설치 건너뜀)"
} else {
    Write-Host "[1/2] Python이 없어 설치를 시작합니다... (설치 중 Windows 권한 창이 뜰 수 있습니다)"
    winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
    Update-SessionPath
}

if (Test-Command "npm") {
    Write-Host "[2/2] Node.js 확인됨 (설치 건너뜀)"
} else {
    Write-Host "[2/2] Node.js가 없어 설치를 시작합니다... (설치 중 Windows 권한 창이 뜰 수 있습니다)"
    winget install --id OpenJS.NodeJS.LTS -e --source winget --accept-package-agreements --accept-source-agreements
    Update-SessionPath
}

if (-not (Test-Command "py") -or -not (Test-Command "npm")) {
    Write-Host ""
    Write-Host "[오류] 설치 후에도 Python 또는 Node.js를 찾을 수 없습니다."
    Write-Host "설치 중 오류가 없었는지 확인하고, 이 창을 닫은 뒤 install.bat을 다시 실행해 주세요."
    Write-Host "그래도 안 되면 컴퓨터를 재시작한 뒤 다시 시도해 주세요 (PATH 환경변수 갱신 필요)."
    Read-Host "종료하려면 Enter를 누르세요"
    exit 1
}

Write-Host ""
Write-Host "[완료] 사전 준비가 끝났습니다. 프로젝트 설치와 실행을 시작합니다..."
Write-Host ""

& "$PSScriptRoot\start.ps1"
