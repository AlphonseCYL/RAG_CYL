# backend_cyl

最小可用后端，目前实现用户注册、密码登录、当前用户校验和创建会话。

## 目录结构

```text
backend_cyl/
  main.py                    # FastAPI 应用入口
  app/
    core/
      config.py              # JWT 与 MySQL 配置占位
      mysql_db.py            # MySQL 服务器连接、业务库连接、自动建库
      database.py            # MySQL 连接上下文与 users/sessions 表初始化
    features/
      auth/                  # 注册、登录、当前用户校验
      sessions/              # 创建会话
```

## MySQL 配置

按你的本地信息设置环境变量：

```powershell
$env:MYSQL_HOST="127.0.0.1"
$env:MYSQL_PORT="3306"
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="0000"
$env:MYSQL_DATABASE_NAME="RAG_system"
$env:MYSQL_CHARSET="utf8mb4"
$env:MYSQL_COLLATION="utf8mb4_unicode_ci"
```

后端启动时会先检查 `MYSQL_DATABASE_NAME` 指定的数据库是否存在，不存在则自动创建，然后继续初始化业务表。也可以直接修改 `app/core/config.py` 里的默认占位值。不要把真实密码提交到仓库。

## 运行

```powershell
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

接口：

- `GET /`
- `GET /health`
- `POST /register`
- `POST /login`
- `GET /me`
- `POST /create_session`

接口文档：

```text
http://127.0.0.1:8001/docs
```
