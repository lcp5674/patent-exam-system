@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ============================================
:: 专利审查辅助系统 - Docker 部署脚本 (Windows)
:: 支持 PostgreSQL (默认) / MySQL / SQLite
:: ============================================

set DB_TYPE=postgres
set IMAGE_TAG=latest
set COMPOSE_FILES=-f docker-compose.yml

:: 显示帮助
if "%~1"=="-h" goto :help
if "%~1"=="--help" goto :help
if "%~1"=="" goto :parse_args
echo 用法: %~nx0 [选项]
echo.
echo 选项:
echo   -h, --help              显示帮助
echo   --db TYPE              数据库类型: postgres ^(默认^), mysql, sqlite
echo   --tag TAG              镜像标签 ^(默认: latest^)
echo.
echo 示例:
echo   %~nx0                   # 使用 PostgreSQL 部署
echo   %~nx0 --db mysql        # 使用 MySQL 部署
echo   %~nx0 --db sqlite       # 使用 SQLite 部署
exit /b 0

:help
echo 用法: %~nx0 [选项]
echo.
echo 选项:
echo   -h, --help              显示帮助
echo   --db TYPE              数据库类型: postgres ^(默认^), mysql, sqlite
echo   --tag TAG              镜像标签 ^(默认: latest^)
echo.
echo 示例:
echo   %~nx0                   # 使用 PostgreSQL 部署
echo   %~nx0 --db mysql        # 使用 MySQL 部署
echo   %~nx0 --db sqlite       # 使用 SQLite 部署
exit /b 0

:parse_args
:: 解析参数
:loop
if "%~1"=="" goto :check_env
if /i "%~1"=="--db" (
    set DB_TYPE=%~2
    shift
    shift
    goto :loop
)
if /i "%~1"=="--tag" (
    set IMAGE_TAG=%~2
    shift
    shift
    goto :loop
)
shift
goto :loop

:check_env
:: 检查 Docker
echo [检查环境]
docker --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker 未安装
    exit /b 1
)

docker compose version >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker Compose 未安装
    exit /b 1
)

:: 复制环境文件
echo [准备环境配置]
if not exist ".env" (
    if exist ".env.docker" (
        copy /Y .env.docker .env
        echo [已从 .env.docker 创建 .env]
    ) else (
        echo [错误] 缺少 .env.docker 文件
        exit /b 1
    )
)

:: 根据数据库类型选择配置
if /i "%DB_TYPE%"=="postgres" (
    set COMPOSE_FILES=-f docker-compose.yml
    echo [使用 PostgreSQL 数据库]
) else if /i "%DB_TYPE%"=="mysql" (
    set COMPOSE_FILES=-f docker-compose.yml -f docker-compose.mysql.yml
    echo [使用 MySQL 数据库]
) else if /i "%DB_TYPE%"=="sqlite" (
    set COMPOSE_FILES=-f docker-compose.yml -f docker-compose.sqlite.yml
    echo [使用 SQLite 数据库]
) else (
    echo [错误] 不支持的数据库类型: %DB_TYPE%
    exit /b 1
)

:: 构建和启动
echo [构建镜像]
docker compose %COMPOSE_FILES% build

echo [启动服务]
docker compose %COMPOSE_FILES% up -d

:: 等待服务健康
echo [等待服务启动]
timeout /t 10 /nobreak >nul

:: 检查服务状态
echo [检查服务状态]
docker compose %COMPOSE_FILES% ps

echo.
echo ========================================
echo   部署完成!
echo ========================================
echo.
echo 访问地址:
echo   - 前端: http://localhost
echo   - 后端: http://localhost:8000
echo   - API 文档: http://localhost:8000/docs
echo.
echo 默认管理员账户:
echo   - 用户名: admin
echo   - 密码: admin123
echo.
echo 常用命令:
echo   查看日志: docker compose logs -f
echo   停止服务: docker compose %COMPOSE_FILES% down
echo   重启服务: docker compose %COMPOSE_FILES% restart

endlocal
