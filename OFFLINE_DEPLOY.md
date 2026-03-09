# 离线部署方案文档

## 📦 离线部署包说明
本方案适用于无外网或网络受限的服务器环境部署。

### 离线部署包包含内容：
1. **基础镜像包**：所有Docker镜像的tar包（约5GB）
2. **代码包**：完整的项目代码（包含前端构建产物）
3. **部署脚本**：一键安装脚本、配置模板
4. **依赖包**：Python和Node.js的离线依赖包（可选）

---

## 📋 环境要求
### 最低配置
- CPU：4核
- 内存：8G
- 硬盘：200G SSD（镜像包约5GB，数据存储至少100GB）
- 操作系统：Ubuntu 20.04+/CentOS 8+/Debian 11+
- 已预装Docker 20.10+ 和 Docker Compose v2.0+

---

## 🚀 离线部署步骤

### 第一步：准备离线部署包
#### 方式一：自行导出镜像包（在有网络的机器上执行）
```bash
# 1. 拉取所有所需镜像
docker pull postgres:16-alpine
docker pull redis:7-alpine
docker pull quay.io/coreos/etcd:v3.5.5
docker pull minio/minio:RELEASE.2023-03-20T20-16-18Z
docker pull milvusdb/milvus:v2.4.0
docker pull nginx:alpine
docker pull python:3.10-slim
docker pull node:18-alpine

# 2. 导出镜像到tar包
mkdir -p offline-images
docker save -o offline-images/postgres.tar postgres:16-alpine
docker save -o offline-images/redis.tar redis:7-alpine
docker save -o offline-images/etcd.tar quay.io/coreos/etcd:v3.5.5
docker save -o offline-images/minio.tar minio/minio:RELEASE.2023-03-20T20-16-18Z
docker save -o offline-images/milvus.tar milvusdb/milvus:v2.4.0
docker save -o offline-images/nginx.tar nginx:alpine
docker save -o offline-images/python.tar python:3.10-slim
docker save -o offline-images/node.tar node:18-alpine

# 3. 构建项目镜像
docker compose build

# 4. 导出项目自定义镜像
docker save -o offline-images/patent-backend.tar patent-exam-system-backend:latest
docker save -o offline-images/patent-frontend.tar patent-exam-system-frontend:latest

# 5. 打包整个项目
cd ..
tar zcvf patent-exam-system-offline.tar.gz patent-exam-system/
```

#### 方式二：使用预构建的离线包
直接获取已打包好的 `patent-exam-system-offline.tar.gz`（约8GB）。

---

### 第二步：上传到离线服务器
```bash
# 将离线包上传到目标服务器
scp patent-exam-system-offline.tar.gz root@your-server-ip:/opt/

# 解压
cd /opt
tar zxvf patent-exam-system-offline.tar.gz
cd patent-exam-system
```

---

### 第三步：导入Docker镜像
```bash
# 进入镜像目录
cd offline-images

# 批量导入所有镜像
for img in *.tar; do
  echo "导入镜像: $img"
  docker load -i $img
done

# 验证镜像导入成功
docker images
```
应该能看到所有镜像都已导入：
- postgres:16-alpine
- redis:7-alpine
- quay.io/coreos/etcd:v3.5.5
- minio/minio:RELEASE.2023-03-20T20-16-18Z
- milvusdb/milvus:v2.4.0
- nginx:alpine
- python:3.10-slim
- node:18-alpine
- patent-exam-system-backend:latest
- patent-exam-system-frontend:latest

---

### 第四步：配置环境变量
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件
vim .env
```

**必填配置项：**
```ini
# 数据库密码（自定义强密码）
DB_PASSWORD=your_secure_db_password

# 豆包API密钥（从字节跳动方舟平台获取）
DOUBAO_API_KEY=your-doubao-api-key

# 安全密钥（随机字符串，建议32位以上）
SECRET_KEY=your-random-secret-key-here-keep-it-safe

# 访问域名或IP（如 http://192.168.1.100 或 https://patent.example.com）
CORS_ORIGINS=http://your-server-ip
API_BASE_URL=http://your-server-ip/api
```

---

### 第五步：启动服务
```bash
# 启动所有服务（因为镜像已本地导入，无需拉取）
docker compose up -d

# 查看启动状态
docker compose ps
```
所有服务状态应该都是 `Up` 或 `Up (healthy)`。

---

### 第六步：初始化数据
```bash
# 等待所有服务启动完成（约2分钟）
# 执行数据库迁移
docker compose exec backend alembic upgrade head

# 初始化规则库和默认管理员账号
docker compose exec backend python init_db.py
```

---

### 第七步：访问系统
- 前端地址：`http://你的服务器IP` 或配置的域名
- 后台管理：`http://你的服务器IP/admin`
- 默认账号：`admin` / `admin123`（首次登录请立即修改密码）

---

## 🔧 离线部署脚本
创建一键部署脚本 `offline_deploy.sh`：
```bash
#!/bin/bash
# 专利审查系统离线部署脚本

echo "🚀 开始离线部署专利审查系统..."

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker 和 Docker Compose"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose 未安装，请先安装 Docker Compose"
    exit 1
fi

# 导入镜像
echo "📥 导入Docker镜像..."
cd offline-images
for img in *.tar; do
    echo "导入 $img..."
    docker load -i $img > /dev/null
done
cd ..

# 检查镜像是否导入成功
echo "✅ 镜像导入完成，已导入镜像："
docker images | grep -E "(postgres|redis|etcd|minio|milvus|nginx|python|node|patent)"

# 配置环境变量
echo "⚙️  配置环境变量..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件配置相关参数，配置完成后按任意键继续..."
    read -n 1 -s
fi

# 启动服务
echo "🚀 启动所有服务..."
docker compose up -d

echo "⏳ 等待服务启动..."
sleep 120

# 初始化数据
echo "📊 初始化数据库..."
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend python init_db.py

# 检查服务状态
echo "✅ 部署完成！服务状态："
docker compose ps

echo ""
echo "🌐 访问地址：http://$(hostname -I | awk '{print $1}')"
echo "🔑 默认账号：admin / admin123"
echo "⚠️  首次登录请立即修改默认密码！"
```

**使用方法：**
```bash
chmod +x offline_deploy.sh
./offline_deploy.sh
```

---

## 📦 离线包大小说明
| 组件 | 大小 | 说明 |
|------|------|------|
| 基础镜像 | ~5GB | postgres, redis, etcd, minio, milvus, nginx, python, node |
| 项目镜像 | ~2GB | backend和frontend自定义镜像 |
| 代码和配置 | ~1GB | 项目代码、静态资源、配置文件 |
| **总计** | **~8GB** | 完整离线部署包 |

---

## 🔒 离线环境安全注意事项
1. **镜像安全**：所有镜像都经过病毒扫描，确保无恶意代码
2. **数据安全**：数据库数据存储在本地数据卷，定期备份
3. **访问控制**：配置防火墙，仅开放必要端口（80/443）
4. **密码管理**：所有默认密码必须修改，使用强密码
5. **日志审计**：定期审计系统日志，排查异常访问

---

## ❓ 常见问题

### Q: 导入镜像失败怎么办？
A: 检查镜像文件是否完整，MD5校验是否匹配，确保上传过程中没有损坏。

### Q: 服务启动失败怎么办？
A: 查看日志定位问题：
```bash
docker compose logs <服务名>
```
常见问题：
- 端口被占用：修改 `docker-compose.yml` 中的端口配置
- 内存不足：升级服务器配置到至少8GB内存
- 权限问题：确保Docker有足够的权限访问数据目录

### Q: 如何升级离线版本？
A:
1. 下载新版本的离线包
2. 导入新的镜像
3. 重启服务：`docker compose up -d`
4. 执行数据库迁移：`docker compose exec backend alembic upgrade head`

### Q: 如何备份离线数据？
A:
```bash
# 备份数据库
docker compose exec postgres pg_dump -U patent_user patent_exam > backup_$(date +%Y%m%d).sql

# 备份Milvus向量数据
docker run --rm -v patent-exam-system_milvus_data:/volume -v $(pwd):/backup alpine tar czf /backup/milvus_backup_$(date +%Y%m%d).tar.gz -C /volume .
```

---

## 📞 技术支持
离线部署过程中如遇问题，请联系技术支持获取帮助。
