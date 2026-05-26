# backend_cyl

`backend_cyl` 是用于逐步复现主项目后端能力的 FastAPI 薄切片版本。当前保留用户认证、会话管理、当前会话文档快速解析、SSE 聊天接口和 Redis 临时文档上下文。

## 目录结构

```text
backend_cyl/
  main.py                    # FastAPI 应用入口
  docker_compose.yaml         # Redis 等本地依赖
  requirements.txt            # Python 依赖
  app/
    core/
      config.py               # JWT、MySQL、Redis 配置
      database.py             # SQLAlchemy engine、SessionLocal、init_db
    models/
      user.py                 # users ORM 模型
      session.py              # sessions ORM 模型
    router/
      user_rt.py              # /register、/login、/me
      chat_rt.py              # /create_session、/quick_parse、/chat_on_docs
      history_rt.py           # /get_sessions、/sessions/{session_id}
    features/
      auth/                   # 认证 schema、security、service
      sessions/               # 会话 service、快速解析、Redis 存取
```

## 数据存储

- MySQL 操作统一通过 SQLAlchemy 完成。
- `app/core/database.py` 会在启动时创建目标数据库和 ORM 表。
- 当前 ORM 表包括 `users` 和 `sessions`。
- 快速解析后的文档正文不写 MySQL，仍然按主项目边界写入 Redis，并设置过期时间。

## 常用运行

```powershell
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

接口文档：

```text
http://127.0.0.1:8001/docs
```
