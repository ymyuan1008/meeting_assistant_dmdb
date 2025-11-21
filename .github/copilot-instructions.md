# Copilot / AI 开发指引（精简版）

以下说明面向在此仓库中工作的 AI 编码代理（Copilot/Code Assistant）。目标是快速上手、保持一致并生成与项目风格配套的改动。

1. 项目概览（快速记忆）

- 这是一个基于 `FastAPI` 的后端服务，主要功能：会议管理、实时语音转录、文档生成、邮件通知与消息推送。
- 入口文件：`main.py`（包含生命周期、日志与路由注册）。

2. 代码分层与常见位置

- 路由层：`router/`（每个模块通常导出 `router` 对象或模块级路由，如 `router.user_manage`）。
- 业务层：`services/`（每个文件实现一个服务类，例如 `MeetingService`, `SpeechService`）。
- 模型/DTO：`models/` 与 `schema/`（SQLAlchemy 模型 + Pydantic schema）。
- 数据库：`db/`（达梦数据库适配器、连接管理 `db/dm_conn.py`、SQL 初始化脚本在 `db/sql/`）。
- WebSocket：`websocket/`（`ConnectionManager` / `manager.py` 管理连接与广播）。
- 工具：`utils/`；第三方/集成相关示例在 `db/minio_upload.py`、`services/third_party_service.py` 等。

3. 运行与测试（必要命令）

- 安装依赖：`pip install -r requirements.txt`
- 配置环境：复制并编辑 `.env`（参见 `README.md` 与 `CLAUDE.md` 中的示例 env 条目）
- 启动服务（开发）：`python main.py`（默认在 `http://localhost:8000`，Swagger 在 `/docs`）
- 运行测试：`pytest`；针对异步测试可使用：`pytest -k "async" --asyncio-mode=auto`

4. 数据库与迁移说明（仓库约定）

- 本项目没有独立 migration 工具（如 Alembic）配置；数据库初始化依赖项目中的 SQL 脚本：`db/sql/`。
- DB 适配器与连接：`db/databases.py`（`DMDatabaseAdapter`）与 `db/dm_conn.py`（`get_db`, `get_async_db`, `Base`）。修改模型时请注意手动同步/运行初始化 SQL。

5. 常见开发约定与模式（必须遵守）

- 路由：新增 API 时在 `router/` 新建模块并导出 `router`，在 `main.py` 中 `app.include_router(...)` 注册。
- 服务实例化：`main.py` 在模块顶层创建服务单例（如 `meeting_service = MeetingService()`），编码时谨慎修改全局状态。
- 认证：JWT + RSA 密码加密（公钥接口：`GET /api/auth/public-key`），刷新 token 使用轮换 + 黑名单机制（见 `services/auth_service.py`）。
- 日志：使用 `loguru`（配置在 `main.py`），不要绕过此约定写未经结构化的日志。

6. 集成点与外部依赖

- 达梦数据库（DM），环境变量控制连接；在 CI/本地开发时注意模拟或提供测试数据库。
- MinIO 对象存储：参考 `db/minio_upload.py`。
- FFmpeg（用于音频处理）需在运行环境中可用。

7. 代码风格与 PR 建议（针对 AI 代理）

- 小而明确的改动：按功能拆分 PR；不要一次性修改大量文件。
- 测试优先：修改路由 / 服务 时尽量添加或更新对应测试（`tests/` 目录）。
- 保持依赖最小改动：新增库需在 `requirements.txt` 中声明。

8. 例子（快速参考）

- 注册路由示例：在 `router/third_party_token.py` 中导出 `router`，并在 `main.py` 中通过 `app.include_router(third_party_token_router)` 注册。
- 获取 DB 会话：使用依赖注入 `Depends(get_db)` 或 `get_async_db`（查看 `db/dm_conn.py`）

9. 调试与生命周期

- `main.py` 使用 `lifespan` asynccontextmanager 管理启动/关闭逻辑；把全局初始化逻辑放在这里（例如外部连接预热）。

10. 参考文件（优先阅读）

- `README.md`（项目总体、运行示例）
- `CLAUDE.md`（已有对开发者/AI 的说明，可直接复用里面的环境与命令）
- `main.py`, `router/`, `services/`, `db/dm_conn.py`, `websocket/manager.py`

如果有需要，我可以把这份文档再缩短为 10-12 行的“快速提示卡片”，或根据你的反馈补充示例代码片段与 PR 模板。请告诉我哪些部分需要更详细的示例或合并策略。
