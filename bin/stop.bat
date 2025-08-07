@echo off
rem 设置编码为 UTF-8
CHCP 65001

rem 查找占用端口8009的进程PID
for /f "tokens=5" %%i in ('netstat -ano ^| findstr :8009') do set PID=%%i

if "%PID%"=="" (
    echo 没有找到占用端口8009的进程
    pause
    exit
)

echo 找到以下进程占用端口8009:
echo PID: %PID%
taskkill /PID:%PID% /F /T
echo 进程已终止

pause