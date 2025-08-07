@echo off
if "%1" == "h" goto begin
 

mshta vbscript:createobject("wscript.shell").run("""%~nx0"" h",0)(window.close)&&exit
 

:begin
rem 设置编码为 UTF-8
CHCP 65001

rem 回到项目根目录（父目录）
cd /d "%~dp0..\"
call conda activate llm
rem 检查是否激活成功
if %ERRORLEVEL% neq 0 (
    echo Conda 环境激活失败，请检查环境名称和路径！
    exit /b 1
)

rem 获取当前工作目录并输出
echo Current directory: %CD%

rem 设置 PYTHONPATH 环境变量
set PYTHONPATH=%CD%

rem 运行 Python 脚本
python aduib_ai/app.py
