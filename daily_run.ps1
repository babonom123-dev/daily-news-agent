# daily-news-agent : 매일 아침 자동 실행 스크립트 (PowerShell)
# Windows 작업 스케줄러가 이 파일을 호출합니다.

# UTF-8 콘솔 인코딩
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

# 작업 디렉토리 = 이 스크립트 위치
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# 로그 디렉토리·파일
$logDir = Join-Path $scriptDir "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$today = Get-Date -Format "yyyy-MM-dd"
$logFile = Join-Path $logDir "run_$today.log"

function Write-Log($msg) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$stamp] $msg" | Out-File -FilePath $logFile -Append -Encoding utf8
}

Write-Log "============================================================"
Write-Log "[START] daily-news-agent 실행 시작"
Write-Log "============================================================"

# Python 실행 헬퍼
function Run-Step($name, $script) {
    Write-Log ""
    Write-Log "[$name] $script 실행 중..."
    $output = & python $script 2>&1
    $output | Out-File -FilePath $logFile -Append -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        Write-Log "[ERROR] $script 실패 (exit code $LASTEXITCODE) — 중단"
        exit 1
    }
    Write-Log "[$name] $script 완료"
}

Run-Step "1/3" "fetch_news.py"
Run-Step "2/3" "filter_news.py"
Run-Step "3/3" "send_email.py"

Write-Log ""
Write-Log "[DONE] 메일 발송 완료 ✅"
Write-Log "============================================================"
exit 0
