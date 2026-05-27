@echo off
REM ============================================================
REM  daily-news-agent — 매일 아침 자동 실행 배치
REM  Windows 작업 스케줄러가 이 파일을 호출합니다.
REM ============================================================

REM 한글 콘솔 인코딩
chcp 65001 > nul
set PYTHONIOENCODING=utf-8

REM 작업 디렉토리 = 이 배치 파일 위치
cd /d "%~dp0"

REM 로그 파일 (날짜별)
set LOG_DIR=%~dp0logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set LOG_FILE=%LOG_DIR%\run_%date:~0,4%-%date:~5,2%-%date:~8,2%.log

REM ============================================================
echo. >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo  [START] %date% %time% >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

REM --- 1단계: RSS 수집 ---
echo. >> "%LOG_FILE%"
echo [1/3] fetch_news.py 실행 중... >> "%LOG_FILE%"
python fetch_news.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [ERROR] fetch_news.py 실패 — 중단 >> "%LOG_FILE%"
    exit /b 1
)

REM --- 2단계: Haiku 필터링 ---
echo. >> "%LOG_FILE%"
echo [2/3] filter_news.py 실행 중... >> "%LOG_FILE%"
python filter_news.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [ERROR] filter_news.py 실패 — 중단 >> "%LOG_FILE%"
    exit /b 1
)

REM --- 3단계: Gmail 발송 ---
echo. >> "%LOG_FILE%"
echo [3/3] send_email.py 실행 중... >> "%LOG_FILE%"
python send_email.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [ERROR] send_email.py 실패 >> "%LOG_FILE%"
    exit /b 1
)

REM ============================================================
echo. >> "%LOG_FILE%"
echo [DONE] %date% %time% — 메일 발송 완료 >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
exit /b 0
