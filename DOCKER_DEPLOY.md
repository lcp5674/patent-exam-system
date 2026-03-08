# Docker一键部署文档

## 🚀 快速部署（5分钟完成）
使用Docker Compose一键部署整个系统，包含所有依赖组件。

### 1. 环境要求
- Docker 20.10+
- Docker Compose v2.0+
- 服务器配置：最低4核8G，推荐8核16G
- 磁盘空间：至少100G SSD

### 2. 部署步骤

#### 第一步：克隆代码
```bash
git clone <仓库地址> patent-exam-system
cd patent-exam-system
```

#### 第二步：配置环境变量
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件，修改以下参数
vim .env
```

需要修改的配置项：
```ini
# 数据库密码（必填，自定义强密码）
DB_PASSWORD=your_secure_db_password

# 豆包API密钥（必填，从字节跳动方舟平台获取）
DOUBAO_API_KEY=your-doubao-api-key

# 安全密钥（必填，随机字符串）
SECRET_KEY=your-random-secret-key-here-keep-it-safe

# 你的域名（可选，如不需要可以留空）
CORS_ORIGINS=https://patent.your-domain.com
API_BASE_URL=https://patent.your-domain.com/api
```

#### 第三步：启动服务
```bash
# 构建并启动所有服务
docker compose up -d

# 查看启动状态
docker compose ps
```

#### 第四步：初始化数据
```bash
# 等待所有服务启动完成（约2分钟）
# 执行数据库迁移和规则初始化
docker compose exec backend alembic upgrade head
docker compose exec backend python init_db.py
```

#### 第五步：访问系统
- 前端地址：`http://你的服务器IP` 或 `https://你的域名`
- 后台管理：`http://你的服务器IP/admin`
- 默认账号：`admin` / `admin123`（首次登录请立即修改密码）

## 📋 服务说明
启动后会运行以下容器：

| 容器名称 | 作用 | 端口 | 状态检查 |
|----------|------|------|----------|
| patent-postgres | PostgreSQL数据库 | 5432（内部不暴露） | ✅ 自动健康检查 |
| patent-redis | Redis缓存 | 6379（内部不暴露） | ✅ 自动健康检查 |
| patent-etcd | Milvus依赖 | 2379（内部不暴露） | ✅ 自动健康检查 |
| patent-minio | Milvus对象存储 | 9000/9001（内部不暴露） | ✅ 自动健康检查 |
| patent-milvus | 向量数据库 | 19530（内部不暴露） | ✅ 自动健康检查 |
| patent-backend | 后端API服务 | 8000（内部不暴露） | ✅ 自动健康检查 |
| patent-frontend | 前端服务 | 内部不暴露 | ✅ 自动健康检查 |
| patent-nginx | 反向代理 | 80/443（对外暴露） | ✅ 自动健康检查 |

## 🔧 常用命令

### 查看服务状态
```bash
# 查看所有服务状态
docker compose ps

# 查看日志
docker compose logs -f backend  # 查看后端日志
docker compose logs -f frontend # 查看前端日志
docker compose logs -f nginx    # 查看Nginx日志
```

### 管理服务
```bash
# 停止所有服务
docker compose down

# 重启服务
docker compose restart

# 升级版本
git pull
docker compose up -d --build
```

### 数据管理
```bash
# 数据库备份
docker compose exec postgres pg_dump -U patent_user patent_exam > backup_$(date +%Y%m%d).sql

# 数据库恢复
docker compose exec -T postgres psql -U patent_user patent_exam < backup.sql

# 查看爬取日志
docker compose exec backend tail -f /var/log/patent_crawl.log
```

## 🌐 域名和HTTPS配置

### 配置域名解析
将你的域名（如 patent.your-domain.com）解析到服务器公网IP。

### 配置HTTPS（Let's Encrypt免费证书）
```bash
# 安装certbot
apt update && apt install -y certbot python3-certbot-nginx

# 申请证书
certbot --nginx -d patent.your-domain.com

# 证书自动续期
certbot renew --dry-run
```

## 📊 监控和维护

### 系统监控
访问 `http://你的服务器IP:9090` 查看Prometheus监控指标（需要配置监控服务）。

### 爬取管理
1. 登录系统后台，进入【爬虫管理】页面
2. 配置全量爬取参数，点击"启动全量爬取"即可开始爬取历史专利
3. 增量同步默认每日凌晨2点自动执行，可在页面调整同步时间

### 性能调优
对于高并发场景，可以修改`docker-compose.yml`优化配置：
```yaml
backend:
  deploy:
    replicas: 4  # 增加后端副本数
    resources:
      limits:
        cpus: '2'
        memory: 4G
```

## 🔒 安全建议
1. **修改默认密码**：首次登录立即修改admin账号密码
2. **防火墙配置**：仅开放80、443端口，关闭其他不必要端口
3. **定期备份**：配置每日自动数据库备份
4. **访问控制**：后台管理页面配置IP白名单
5. **密钥管理**：妥善保存.env文件中的敏感信息，不要泄露

## ❓ 常见问题

### Q: 服务启动失败怎么办？
A: 查看日志定位问题：
```bash
docker compose logs <服务名>
```
常见问题：
- 端口被占用：修改`docker-compose.yml`中的端口配置
- 内存不足：升级服务器配置，或减少服务副本数
- 网络问题：检查服务器是否能访问豆包API接口

### Q: 专利爬取失败怎么办？
A: 
1. 检查网络连接是否正常
2. 确认没有被国知局IP封禁，可配置代理
3. 查看爬取日志：`/var/log/patent_crawl.log`

### Q: RAG检索没有结果怎么办？
A: 
1. 确认已经执行过专利爬取和向量化
2. 查看Milvus服务状态：`docker compose ps milvus`
3. 检查向量模型是否正常加载

### Q: 如何升级系统版本？
A:
```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker compose up -d --build

# 执行数据库迁移（如有需要）
docker compose exec backend alembic upgrade head
```

## 📞 技术支持
如遇问题，可查看项目文档或联系技术支持。
