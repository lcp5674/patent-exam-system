#!/bin/bash
set -e

# Agent管理脚本
# 使用说明：
#   ./agent-management.sh start   # 启动Agent服务
#   ./agent-management.sh stop    # 停止Agent服务
#   ./agent-management.sh status  # 查看Agent状态

AGENT_NETWORK="patent-agent-net"

start_agents() {
    echo "启动Agent服务..."
    
    # 创建Agent专用网络
    docker network create ${AGENT_NETWORK} 2>/dev/null || true
    
    # 启动Redis（如果不存在）
    if ! docker ps | grep -q patent-agent-redis; then
        echo "启动 Redis..."
        docker run -d --name patent-agent-redis \
            --network ${AGENT_NETWORK} \
            -p 6380:6379 \
            -v patent-agent-redis-data:/data \
            redis:7-alpine redis-server --appendonly yes
    fi
    
    # 启动ChromaDB（如果不存在）
    if ! docker ps | grep -q patent-agent-chromadb; then
        echo "启动 ChromaDB..."
        docker run -d --name patent-agent-chromadb \
            --network ${AGENT_NETWORK} \
            -p 8001:8000 \
            -v patent-agent-chroma-data:/chroma/chroma \
            -e IS_PERSISTENT=TRUE \
            chromadb/chroma:latest
    fi
    
    # 启动Flower（Celery监控）
    if ! docker ps | grep -q patent-agent-flower; then
        echo "启动 Flower..."
        docker run -d --name patent-agent-flower \
            --network ${AGENT_NETWORK} \
            -p 5556:5555 \
            -e CELERY_BROKER_URL=redis://patent-agent-redis:6379/0 \
            -e CELERY_RESULT_BACKEND=redis://patent-agent-redis:6379/0 \
            mher/flower:latest
    fi
    
    # 启动Celery Worker
    if ! docker ps | grep -q patent-agent-scheduler; then
        echo "启动 Celery Worker..."
        docker run -d --name patent-agent-scheduler \
            --network ${AGENT_NETWORK} \
            --network patent-net \
            -v /f/知识产权图书/专利提示词/patent-exam-system/backend/app:/app/app \
            -v /f/知识产权图书/专利提示词/patent-exam-system/backend/data:/app/data \
            -e CELERY_BROKER_URL=redis://patent-agent-redis:6379/0 \
            -e PYTHONPATH=/app \
            patent-exam-system-backend:latest \
            celery -A app.tasks.celery_app worker -l INFO --concurrency=4 --pool=threads
    fi
    
    # 启动Celery Beat
    if ! docker ps | grep -q patent-agent-beat; then
        echo "启动 Celery Beat..."
        docker run -d --name patent-agent-beat \
            --network ${AGENT_NETWORK} \
            -v /f/知识产权图书/专利提示词/patent-exam-system/backend/app:/app/app \
            -e CELERY_BROKER_URL=redis://patent-agent-redis:6379/0 \
            -e PYTHONPATH=/app \
            patent-exam-system-backend:latest \
            celery -A app.tasks.celery_app beat -l INFO --scheduler redbeat.RedBeatScheduler
    fi
    
    echo "Agent服务启动完成！"
    echo "访问监控面板："
    echo "  - Flower: http://localhost:5556"
    echo "  - Redis: localhost:6380"
    echo "  - ChromaDB: localhost:8001"
}

stop_agents() {
    echo "停止Agent服务..."
    
    # 停止容器（不删除数据）
    docker stop patent-agent-flower 2>/dev/null || true
    docker stop patent-agent-beat 2>/dev/null || true
    docker stop patent-agent-scheduler 2>/dev/null || true
    docker stop patent-agent-chromadb 2>/dev/null || true
    docker stop patent-agent-redis 2>/dev/null || true
    
    echo "Agent服务已停止！"
}

status_agents() {
    echo "Agent服务状态："
    echo "===================="
    docker ps --filter "name=patent-agent-*" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo ""
    echo "数据卷状态："
    docker volume ls --filter "name=patent-agent-*"
}

logs_agents() {
    container=$1
    if [ -z "$container" ]; then
        echo "请指定容器名（patent-agent-redis | patent-agent-chromadb | patent-agent-scheduler | patent-agent-beat | patent-agent-flower）"
        exit 1
    fi
    docker logs -f $container
}

case "$1" in
    start)
        start_agents
        ;;
    stop)
        stop_agents
        ;;
    status)
        status_agents
        ;;
    logs)
        logs_agents $2
        ;;
    *)
        echo "使用方法: $0 {start|stop|status|logs}"
        exit 1
        ;;
esac
