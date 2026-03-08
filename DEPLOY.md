# 专利审查系统部署文档

## 🚀 系统架构
```
用户 → Nginx → 前端服务 → 后端API → [规则引擎, AI服务, RAG系统]
                                          ↓
                               [PostgreSQL, Redis, Milvus]
```

## 📋 环境要求
### 最低配置
- CPU：4核
- 内存：8G
- 硬盘：100G SSD
- 操作系统：Ubuntu 22.04 / CentOS 8+

### 推荐配置（生产环境）
- CPU：8核16线程
- 内存：16G
- 硬盘：500G SSD
- 带宽：10M以上

## 🔧 快速部署

### 1. 系统依赖安装
```bash
# 更新系统
apt update && apt upgrade -y

# 安装基础依赖
apt install -y python3.10 python3-pip python3-venv \
               postgresql postgresql-contrib \
               redis-server \
               nginx \
               docker.io docker-compose-plugin \
               git cron

# 启动服务
systemctl enable postgresql redis nginx
systemctl start postgresql redis nginx
```

### 2. 数据库配置
```bash
# 创建数据库用户
sudo -u postgres psql -c "CREATE USER patent_user WITH PASSWORD 'your_password';"

# 创建数据库
sudo -u postgres psql -c "CREATE DATABASE patent_exam OWNER patent_user;"

# 授权
sudo -u postgres psql -d patent_exam -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO patent_user;"
sudo -u postgres psql -d patent_exam -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO patent_user;"
```

### 3. Milvus向量数据库安装
```bash
# 创建milvus目录
mkdir -p /opt/milvus && cd /opt/milvus

# 下载docker-compose配置
wget https://github.com/milvus-io/milvus/releases/download/v2.4.0/milvus-standalone-docker-compose.yml -O docker-compose.yml

# 启动milvus
docker compose up -d

# 验证安装
docker compose ps
```

### 4. 后端部署
```bash
# 克隆代码
git clone <仓库地址> /opt/patent-exam-system
cd /opt/patent-exam-system/backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑.env文件，配置数据库、Redis、Milvus、AI密钥等信息

# 数据库迁移
alembic upgrade head

# 初始化规则库
python init_db.py

# 启动后端服务（使用systemd）
cat > /etc/systemd/system/patent-backend.service << EOF
[Unit]
Description=Patent Exam Backend
After=network.target postgresql.service redis.service milvus.service

[Service]
User=root
WorkingDirectory=/opt/patent-exam-system/backend
Environment="PATH=/opt/patent-exam-system/backend/venv/bin"
ExecStart=/opt/patent-exam-system/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
systemctl daemon-reload
systemctl enable patent-backend
systemctl start patent-backend
```

### 5. 前端部署
```bash
cd /opt/patent-exam-system/frontend

# 安装依赖
npm install

# 生产构建
npm run build

# 配置Nginx
cat > /etc/nginx/sites-available/patent-frontend << EOF
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /opt/patent-exam-system/frontend/dist;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }

    # API代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # 超时配置
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        root /opt/patent-exam-system/frontend/dist;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# 启用站点
ln -s /etc/nginx/sites-available/patent-frontend /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 6. 爬虫定时任务配置
```bash
# 配置定时任务（系统会自动配置，也可手动设置）
crontab -e
# 添加以下行（每日凌晨2点同步专利）
0 2 * * * /opt/patent-exam-system/backend/venv/bin/python /opt/patent-exam-system/backend/crawler/daily_sync.py >> /var/log/patent_crawl.log 2>&1

# 创建日志文件
touch /var/log/patent_crawl.log
chown root:root /var/log/patent_crawl.log
```

## ⚙️ 系统配置

### 环境变量说明（.env文件）
```ini
# 数据库配置
DATABASE_URL=postgresql+asyncpg://patent_user:your_password@localhost:5432/patent_exam

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# Milvus配置
MILVUS_HOST=localhost
MILVUS_PORT=19530

# AI模型配置
DEFAULT_AI_PROVIDER=doubao
DOUBAO_API_KEY=your-doubao-api-key
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_DEFAULT_MODEL=doubao-seed-code

# 向量模型配置
VECTOR_MODEL_PATH=BAAI/bge-m3
VECTOR_DIMENSION=1024

# 安全配置
DEBUG=False
SECRET_KEY=your-secret-key-change-in-production
CORS_ORIGINS=https://your-domain.com

# 性能配置
MAX_WORKERS=4
UPLOAD_MAX_SIZE=100MB
RATE_LIMIT=100/minute
```

## 🚀 启动全量爬取
1. 登录系统后台，进入【爬虫管理】页面
2. 配置全量爬取参数：
   - 开始年份：2020
   - 结束年份：2026
   - 技术领域：全选或按需选择
   - 自动向量化：开启
3. 点击【启动全量爬取】，系统会自动开始爬取历史专利数据
4. 可在页面实时查看爬取进度和统计信息

## 📊 监控与维护

### 日志查看
```bash
# 后端日志
journalctl -u patent-backend -f

# Nginx日志
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# 爬取日志
tail -f /var/log/patent_crawl.log

# Milvus日志
cd /opt/milvus && docker compose logs -f
```

### 常用命令
```bash
# 重启服务
systemctl restart patent-backend
nginx -s reload

# 查看服务状态
systemctl status patent-backend postgresql redis

# 数据库备份
sudo -u postgres pg_dump patent_exam > /backup/patent_exam_$(date +%Y%m%d).sql

# 清理临时文件
find /tmp -name "patent_*" -type f -mtime +7 -delete
```

## 🔒 安全配置建议
1. **防火墙配置**：仅开放80、443端口，关闭其他不必要端口
2. **HTTPS配置**：使用Let's Encrypt配置SSL证书，启用HTTPS
3. **数据库安全**：修改默认密码，限制数据库访问IP
4. **定期备份**：配置每日数据库自动备份，备份文件异地存储
5. **访问控制**：后台管理页面配置IP白名单限制
6. **日志审计**：定期审计系统日志，排查异常访问

## ❓ 常见问题排查

### 1. 后端服务启动失败
- 检查.env文件配置是否正确
- 检查数据库、Redis、Milvus服务是否正常运行
- 查看日志：`journalctl -u patent-backend -n 100`

### 2. RAG检索无结果
- 检查Milvus服务是否正常运行：`docker compose ps`
- 检查是否已执行专利爬取和向量化
- 查看Milvus日志排查问题

### 3. AI调用失败
- 检查API密钥是否正确配置
- 检查网络是否能访问AI服务接口
- 查看密钥是否有调用额度

### 4. 爬虫任务失败
- 检查网络连接是否正常
- 查看爬取日志：`tail -f /var/log/patent_crawl.log`
- 检查是否被国知局IP封禁，可配置代理

## 📈 性能优化建议
1. **高并发场景**：
   - 增加后端工作进程数：`--workers 8`
   - 升级服务器配置到16核32G
   - 配置Redis缓存，减少重复计算
   - 使用CDN加速前端静态资源

2. **大数据量场景**：
   - Milvus升级为集群版
   - PostgreSQL配置读写分离
   - 增加SSD存储空间
   - 定期清理无用数据，优化数据库索引

3. **AI加速**：
   - 配置AI服务缓存，减少重复调用
   - 批量处理AI请求，提升吞吐量
   - 可以配置多个AI服务商，实现负载均衡和故障切换

## 🤝 技术支持
如遇问题，请查看项目README.md或联系技术支持。
