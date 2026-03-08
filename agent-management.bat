@echo off
REM Windows平台Agent管理脚本
REM 需要Docker Desktop运行

setlocal enabledelayedexpansion

set AGENT_NETWORK=patent-agent-net

if "%1"=="start" goto start
if "%1"=="stop" goto stop
if "%1"=="status" goto status
echo 使用方法: %0 {start^|stop^|status}
exit /b 1

:start
echo 启动Agent服务...

REM 创建网络
docker network create %AGENT_NETWORK% 2>nul

REM 启动Redis（端口6380）
docker run -d --name patent-agent-redis ^
    --network %AGENT_NETWORK% ^
    -p 6380:6379 ^
    -v patent-agent-redis-data:/data ^
    redis:7-alpine redis-server --appendonly yes

REM 启动ChromaDB（端口8001）
docker run -d --name patent-agent-chromadb ^
    --network %AGENT_NETWORK% ^
    -p 8001:8000 ^
    -v patent-agent-chroma-data:/chroma/chroma ^
    -e IS_PERSISTENT=TRUE ^
    chromadb/chroma:latest

REM 启动Flower
docker run -d --name patent-agent-flower ^
    --network %AGENT_NETWORK% ^
    -p 5556:5555 ^
    -e CELERY_BROKER_URL=redis://patent-agent-redis:6379/0 ^
    mher/flower:latest

REM 启动Celery Worker（使用相对路径）
docker run -d --name patent-agent-scheduler ^
    --network %AGENT_NETWORK% ^
    --network patent-net ^
    -v "%cd%\backend\app:/app/app" ^
    -v "%cd%\backend\data:/app/data" ^
    -e CELERY_BROKER_URL=redis://patent-agent-redis:6379/0 ^
    -e PYTHONPATH=/app ^
    patent-exam-system-backend:latest ^
    celery -A app.tasks.celery_app worker -l INFO --concurrency=4 --pool=threads

REM 启动Celery Beat
docker run -d --name patent-agent-beat ^
    --network %AGENT_NETWORK% ^
    -v "%cd%\backend\app:/app/app" ^
    -e CELERY_BROKER_URL=redis://patent-agent-redis:6379/0 ^
    -e PYTHONPATH=/app ^
    patent-exam-system-backend:latest ^
    celery -A app.tasks.celery_app beat -l INFO --scheduler redbeat.RedBeatScheduler

echo Agent服务启动完成！
echo 访问监控面板：
echo   - Flower: http://localhost:5556
echo   - Redis: localhost:6380
echo   - ChromaDB: localhost:8001

exit /b 0

:stop
echo 停止Agent服务...
docker stop patent-agent-flower
docker stop patent-agent-beat
docker stop patent-agent-scheduler
docker stop patent-agent-chromadb
docker stop patent-agent-redis
echo Agent服务已停止！
exit /b 0

:status
echo Agent服务状态：
echo ====================
docker ps --filter "name=patent-agent-*" --format "table {{.Names}}	{{.Status}}"
exit /b 0
