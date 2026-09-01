# 部署指南

## 环境要求

- Docker 与 Docker Compose v2
- Node.js 20+（仅本机构建前端时需要）
- PostgreSQL 16（本地开发可交由 compose 启动）

## 本地开发

1. 启动数据库：`docker compose up -d postgres`
2. 配置环境变量：复制 `.env.example` 为 `.env`，填入数据库与 LLM Key。
3. 启动后端：`cd backend && pip install -r requirements.txt && uvicorn main:app --port 8000`
4. 启动前端：`cd web && npm ci && npm run dev`

## Docker 一键启动

```bash
cp .env.example .env
# 修改 .env 中的密钥与 Key
docker compose up -d --build
```

访问 http://localhost（Nginx 80 端口）即可。

## 生产部署（云服务器）

### 1. 本机构建前端产物

服务器资源有限时，不在服务器上执行 `next build`，改为本地预构建后上传：

```bash
cd web
npm ci
npm run build
tar -czf frontend_next.tar.gz -C web .next/standalone .next/static public
```

### 2. 上传并部署

```bash
scp frontend_next.tar.gz root@<服务器IP>:/root/
ssh root@<服务器IP>
cd /root/ai_interview/web && tar -xzf /root/frontend_next.tar.gz
cd /root/ai_interview && docker compose build frontend backend
docker compose up -d
```

### 3. 配置域名与 HTTPS

- 在域名 DNS 添加 A 记录，指向服务器公网 IP。
- 放行安全组 80/443。
- Nginx 按 `server_name` 将 `interview.域名` 与 `travel.域名` 分流到两个项目。
- 使用 certbot webroot 模式签发证书：

```bash
docker run --rm -v /root/ai_interview/certbot/www:/var/www/certbot -v /root/ai_interview/certbot/conf:/etc/letsencrypt \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  -d interview.你的域名 -d travel.你的域名
```

- 将证书路径写入 Nginx 配置并重载。
- 配置 cron 每日自动续期并 reload Nginx。

## 环境变量说明

| 变量 | 说明 |
|---|---|
| DATABASE_URL | PostgreSQL 连接串 |
| JWT_SECRET | 令牌签名密钥，生产必须修改 |
| TOKEN_TTL_SECONDS | 令牌有效期，默认 1800 |
| CODE_TTL_MINUTES | 验证码有效期，默认 5 |
| OPENAI_API_KEY / BASE_URL / SMART_MODEL / FAST_MODEL | 文字模型配置 |
| ASR_API_KEY / BASE_URL / MODEL | 语音转写配置 |
| VOICE_API_KEY / BASE_URL / MODEL | 语音对话配置 |
| NEXT_PUBLIC_API_URL | 生产留空（同源），开发填 http://localhost:8000 |

## 常见问题

- SSE 卡顿：确认 Nginx 已关闭 proxy_buffering。
- PDF 报告打不开：确认 Nginx 将 /static/ 转发到后端。
- 语音面试无法使用：确认 HTTPS 与麦克风权限，ASR/VOICE 模型必须使用千问系列。