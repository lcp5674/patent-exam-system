#!/bin/bash
# 专利审查系统离线部署脚本
# 适用场景：无外网/网络受限环境

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 开始离线部署专利审查系统...${NC}"
echo ""

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker 未安装，请先安装 Docker 和 Docker Compose${NC}"
    echo "安装参考：https://docs.docker.com/engine/install/"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose 未安装，请先安装 Docker Compose${NC}"
    echo "安装参考：https://docs.docker.com/compose/install/"
    exit 1
fi

# 检查离线镜像目录是否存在
if [ ! -d "offline-images" ]; then
    echo -e "${RED}❌ 离线镜像目录 offline-images 不存在，请确认离线包完整${NC}"
    exit 1
fi

# 导入镜像
echo -e "${YELLOW}📥 导入Docker镜像（这可能需要几分钟时间，请耐心等待）...${NC}"
cd offline-images
total_imgs=$(ls -1 *.tar 2>/dev/null | wc -l)
current=0

for img in *.tar; do
    current=$((current + 1))
    echo -n "[$current/$total_imgs] 导入 $img..."
    if docker load -i "$img" > /dev/null 2>&1; then
        echo -e " ${GREEN}完成${NC}"
    else
        echo -e " ${RED}失败${NC}"
        echo "错误：导入镜像 $img 失败，请检查文件完整性"
        exit 1
    fi
done
cd ..

echo ""
echo -e "${GREEN}✅ 镜像导入完成，已导入的镜像：${NC}"
docker images | grep -E "(postgres|redis|etcd|minio|milvus|nginx|python|node|patent)" | awk '{print "  - " $1 ":" $2}'

# 配置环境变量
echo ""
echo -e "${YELLOW}⚙️  配置环境变量...${NC}"
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo -e "${YELLOW}⚠️  请配置 .env 文件中的以下必填项：${NC}"
    echo "  1. DB_PASSWORD - 数据库密码（自定义强密码）"
    echo "  2. DOUBAO_API_KEY - 豆包API密钥（从字节跳动方舟平台获取）"
    echo "  3. SECRET_KEY - 安全密钥（随机字符串，建议32位以上）"
    echo "  4. CORS_ORIGINS - 访问域名或IP，如 http://192.168.1.100"
    echo ""
    read -p "按回车键打开 .env 文件进行编辑..."
    if command -v vim &> /dev/null; then
        vim .env
    elif command -v nano &> /dev/null; then
        nano .env
    else
        echo "未找到vim或nano编辑器，请手动编辑 .env 文件后继续"
        read -p "编辑完成后按任意键继续..."
    fi
fi

# 检查必填配置
echo ""
echo -e "${YELLOW}🔍 检查配置...${NC}"
required_vars=("DB_PASSWORD" "DOUBAO_API_KEY" "SECRET_KEY")
missing_vars=()

for var in "${required_vars[@]}"; do
    value=$(grep "^$var=" .env | cut -d'=' -f2 | xargs)
    if [ -z "$value" ] || [ "$value" == "your_"* ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo -e "${RED}❌ 以下必填配置项未设置：${NC}"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "请编辑 .env 文件配置这些项后重新运行脚本"
    exit 1
fi

echo -e "${GREEN}✅ 配置检查通过${NC}"

# 启动服务
echo ""
echo -e "${YELLOW}🚀 启动所有服务...${NC}"
docker compose up -d

echo ""
echo -e "${YELLOW}⏳ 等待服务启动（约2分钟）...${NC}"
sleep 120

# 检查服务状态
echo ""
echo -e "${YELLOW}📊 检查服务状态...${NC}"
healthy_count=0
total_count=$(docker compose ps -q | wc -l)

while IFS= read -r line; do
    name=$(echo "$line" | awk '{print $1}')
    status=$(echo "$line" | awk '{print $2}')
    if [[ "$status" == *"Up"* ]]; then
        if [[ "$status" == *"healthy"* ]]; then
            echo -e "  ✅ $name: ${GREEN}运行正常（健康检查通过）${NC}"
            healthy_count=$((healthy_count + 1))
        else
            echo -e "  ⚠️  $name: ${YELLOW}运行中（健康检查未完成）${NC}"
        fi
    else
        echo -e "  ❌ $name: ${RED}启动失败${NC}"
    fi
done < <(docker compose ps --format "{{.Names}} {{.Status}}")

echo ""
if [ "$healthy_count" -eq "$total_count" ]; then
    echo -e "${GREEN}✅ 所有服务启动成功！${NC}"
else
    echo -e "${YELLOW}⚠️  部分服务正在启动中，请稍后使用 'docker compose ps' 查看状态${NC}"
fi

# 初始化数据
echo ""
echo -e "${YELLOW}🗄️  初始化数据库...${NC}"
echo "执行数据库迁移..."
if docker compose exec -T backend alembic upgrade head; then
    echo -e "${GREEN}✅ 数据库迁移完成${NC}"
else
    echo -e "${RED}❌ 数据库迁移失败${NC}"
    exit 1
fi

echo "初始化规则库和默认账号..."
if docker compose exec -T backend python init_db.py; then
    echo -e "${GREEN}✅ 数据初始化完成${NC}"
else
    echo -e "${RED}❌ 数据初始化失败${NC}"
    exit 1
fi

# 获取服务器IP
server_ip=$(hostname -I | awk '{print $1}')
if [ -z "$server_ip" ]; then
    server_ip="你的服务器IP"
fi

echo ""
echo -e "${GREEN}🎉 离线部署完成！${NC}"
echo ""
echo "🌐 访问地址：http://$server_ip"
echo "🔑 默认账号：admin / admin123"
echo -e "${RED}⚠️  重要提醒：首次登录请立即修改默认密码！${NC}"
echo ""
echo "📋 常用命令："
echo "  查看服务状态：docker compose ps"
echo "  查看服务日志：docker compose logs -f [服务名]"
echo "  停止服务：docker compose down"
echo "  重启服务：docker compose restart"
echo ""
echo "如需技术支持，请查看项目文档或联系技术人员。"
