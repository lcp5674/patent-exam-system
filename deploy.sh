#!/bin/bash
# ============================================
# 专利审查辅助系统 - Docker 部署脚本
# 支持 PostgreSQL (默认) / MySQL / SQLite
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 默认配置
DB_TYPE="postgres"
IMAGE_TAG="latest"
COMPOSE_FILES="-f docker-compose.yml"

# 显示帮助
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help              显示帮助"
    echo "  --db TYPE              数据库类型: postgres (默认), mysql, sqlite"
    echo "  --tag TAG              镜像标签 (默认: latest)"
    echo ""
    echo "示例:"
    echo "  $0                     # 使用 PostgreSQL 部署"
    echo "  $0 --db mysql          # 使用 MySQL 部署"
    echo "  $0 --db sqlite         # 使用 SQLite 部署"
    echo "  $0 --db postgres --tag v1.0.0"
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        --db)
            DB_TYPE="$2"
            shift 2
            ;;
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        *)
            echo "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

# 检查 Docker 和 Docker Compose
echo -e "${YELLOW}检查环境...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker 未安装${NC}"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}错误: Docker Compose 未安装${NC}"
    exit 1
fi

# 复制环境文件
echo -e "${YELLOW}准备环境配置...${NC}"
if [ ! -f .env ]; then
    if [ -f .env.docker ]; then
        cp .env.docker .env
        echo -e "${GREEN}已从 .env.docker 创建 .env${NC}"
    else
        echo -e "${RED}错误: 缺少 .env.docker 文件${NC}"
        exit 1
    fi
fi

# 根据数据库类型选择配置
case $DB_TYPE in
    postgres)
        COMPOSE_FILES="-f docker-compose.yml"
        echo -e "${GREEN}使用 PostgreSQL 数据库${NC}"
        ;;
    mysql)
        COMPOSE_FILES="-f docker-compose.yml -f docker-compose.mysql.yml"
        echo -e "${GREEN}使用 MySQL 数据库${NC}"
        ;;
    sqlite)
        COMPOSE_FILES="-f docker-compose.yml -f docker-compose.sqlite.yml"
        echo -e "${GREEN}使用 SQLite 数据库${NC}"
        ;;
    *)
        echo -e "${RED}错误: 不支持的数据库类型: $DB_TYPE${NC}"
        exit 1
        ;;
esac

# 构建和启动
echo -e "${YELLOW}构建镜像...${NC}"
docker compose $COMPOSE_FILES build

echo -e "${YELLOW}启动服务...${NC}"
docker compose $COMPOSE_FILES up -d

# 等待服务健康
echo -e "${YELLOW}等待服务启动...${NC}"
sleep 10

# 检查服务状态
echo -e "${YELLOW}检查服务状态...${NC}"
docker compose $COMPOSE_FILES ps

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  部署完成!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "访问地址:"
echo "  - 前端: http://localhost"
echo "  - 后端: http://localhost:8000"
echo "  - API 文档: http://localhost:8000/docs"
echo ""
echo "默认管理员账户:"
echo "  - 用户名: admin"
echo "  - 密码: admin123"
echo ""
echo "常用命令:"
echo "  查看日志: docker compose logs -f"
echo "  停止服务: docker compose $COMPOSE_FILES down"
echo "  重启服务: docker compose $COMPOSE_FILES restart"
