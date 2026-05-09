@echo off
chcp 65001 >nul
echo ==============================================
echo          多智能体客服系统 - 一键启动
echo ==============================================
echo.
echo 访问地址：http://127.0.0.1:8000/docs
echo 关闭窗口即可停止服务
echo.
echo ==============================================
echo.

:: 🔥 单进程运行，彻底解决多进程报错
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1

pause