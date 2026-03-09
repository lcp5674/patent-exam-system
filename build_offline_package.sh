#!/bin/bash
# 离线部署包构建脚本
# 功能：自动拉取镜像、导出镜像、打包完整离线部署包
# 使用场景：在有网络的机器上执行，生成可在离线环境部署的完整包

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}📦 开始构建专利审查系统离线部署包...${NC}"
echo ""

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker 未安装，请先安装 Docker 和 Docker Compose${NC}"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose 未安装，请先安装 Docker Compose${NC}"
    exit 1
fi

# 确认当前目录
if [ ! -f "docker-compose.yml" ] || [ ! -f "offline_deploy.sh" ]; then
    echo -e "${RED}❌ 请在项目根目录下执行此脚本${NC}"
    exit 1
fi

# 创建镜像目录
echo -e "${YELLOW}📂 创建离线镜像目录...${NC}"
mkdir -p offline-images
echo -e "${GREEN}✅ 目录创建完成${NC}"

# 拉取基础镜像
echo ""
echo -e "${YELLOW}📥 拉取基础镜像（这可能需要一段时间，请耐心等待）...${NC}"

base_images=(
    "postgres:16-alpine"
    "redis:7-alpine"
    "quay.io/coreos/etcd:v3.5.5"
    "minio/minio:RELEASE.2023-03-20T20-16-18Z"
    "milvusdb/milvus:v2.4.0"
    "nginx:alpine"
    "python:3.10-slim"
    "node:18-alpine"
)

total_images=${#base_images[@]}
current=0

for img in "${base_images[@]}"; do
    current=$((current + 1))
    echo -e "${YELLOW}[$current/$total_images] 拉取 $img...${NC}"
    docker pull "$img"
done

echo -e "${GREEN}✅ 所有基础镜像拉取完成${NC}"

# 构建项目镜像
echo ""
echo -e "${YELLOW}🔧 构建项目自定义镜像...${NC}"
docker compose build
echo -e "${GREEN}✅ 项目镜像构建完成${NC}"

# 导出镜像
echo ""
echo -e "${YELLOW}💾 导出镜像到离线目录...${NC}"

# 导出基础镜像
for img in "${base_images[@]}"; do
    filename=$(echo "$img" | tr '/' '_' | tr ':' '_')
    echo -e "导出 $img -> offline-images/$filename.tar..."
    docker save -o "offline-images/$filename.tar" "$img"
done

# 导出项目自定义镜像
project_images=(
    "patent-exam-system-main_backend:latest"
    "patent-exam-system-main_frontend:latest"
)

for img in "${project_images[@]}"; do
    filename=$(echo "$img" | tr '/' '_' | tr ':' '_')
    echo -e "导出 $img -> offline-images/$filename.tar..."
    docker save -o "offline-images/$filename.tar" "$img"
done

echo -e "${GREEN}✅ 所有镜像导出完成${NC}"
echo -e "${YELLOW}📊 离线镜像大小统计：${NC}"
du -sh offline-images/* | sort -hr

# 验证镜像文件
echo ""
echo -e "${YELLOW}🔍 验证镜像文件完整性...${NC}"
exported_count=$(ls -1 offline-images/*.tar 2>/dev/null | wc -l)
expected_count=$((total_images + ${#project_images[@]}))

if [ "$exported_count" -eq "$expected_count" ]; then
    echo -e "${GREEN}✅ 所有镜像导出成功，共 $exported_count 个文件${NC}"
else
    echo -e "${RED}❌ 镜像导出不完整，预期 $expected_count 个，实际 $exported_count 个${NC}"
    exit 1
fi

# 清理不需要的文件（可选）
echo ""
echo -e "${YELLOW}🧹 清理临时文件...${NC}"
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -type f -delete 2>/dev/null || true
rm -rf frontend/node_modules/.cache 2>/dev/null || true
echo -e "${GREEN}✅ 清理完成${NC}"

# 打包离线包
echo ""
echo -e "${YELLOW}📦 打包完整离线部署包...${NC}"
cd ..
package_name="patent-exam-system-offline_$(date +%Y%m%d).tar.gz"
tar zcvf "$package_name" \
    --exclude='.git' \
    --exclude='.gitignore' \
    --exclude='*.log' \
    --exclude='tmp/*' \
    --exclude='backend/venv' \
    --exclude='frontend/node_modules' \
    patent-exam-system-main/

echo -e "${GREEN}✅ 离线包构建完成！${NC}"
echo ""
echo "📦 离线包名称：$package_name"
echo "📦 离线包大小：$(du -sh "$package_name" | awk '{print $1}')"
echo ""
echo -e "${YELLOW}🚀 部署说明：${NC}"
echo "1. 将 $package_name 上传到目标离线服务器"
echo "2. 解压：tar zxvf $package_name"
echo "3. 进入目录：cd patent-exam-system-main"
echo "4. 执行部署脚本：./offline_deploy.sh"
echo ""
echo "💡 提示：如果部署过程中遇到问题，请参考 OFFLINE_DEPLOY.md 文档"
