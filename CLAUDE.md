# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个基于 FastAPI 的智能会议助手系统，使用达梦数据库作为数据存储，提供会议管理、实时语音转录、文档生成和邮件通知功能。

## 开发环境设置

### 必要环境
- Python 3.12+
- DM 8.0+ (达梦数据库)
- FFmpeg（音频处理）

### 安装和运行
```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置数据库连接等信息

# 运行应用
python main.py
```

应用将在 `http://localhost:8000` 启动，API文档可在 `http://localhost:8000/docs` 查看。

### 测试
```bash
# 运行测试
pytest

# 运行异步测试
pytest -k "async" --asyncio-mode=auto
```

## 核心架构

### 分层架构
- **models/** - 数据库模型层，基于SQLAlchemy ORM
- **services/** - 业务逻辑层，包含核心业务服务
- **router/** - API路由层，FastAPI路由定义
- **schema/** - 数据传输对象(DTO)，Pydantic模型
- **db/** - 数据库访问层，达梦数据库适配器
- **websocket/** - WebSocket通信层
- **utils/** - 工具类和辅助函数

### 关键服务
- `AuthService` - JWT认证服务，支持令牌轮换和黑名单机制
- `UserService` - 用户管理服务
- `MeetingService` - 会议管理服务
- `SpeechService` - 语音转录服务
- `DocumentService` - 文档生成服务
- `EmailService` - 邮件发送服务

### 数据库配置
项目使用达梦数据库(DM)作为主要数据存储，通过自定义适配器 `DMDatabaseAdapter` 处理连接和SQL语句。数据库配置通过环境变量进行：

```env
DATABASE_HOST=localhost
DATABASE_PORT=5236
DATABASE_USER=SYSDBA
DATABASE_PASSWORD=Dameng123
```

### 认证系统
- 基于JWT的认证机制，支持access_token和refresh_token
- RSA密码加密传输（`/api/auth/public-key`获取公钥）
- 令牌轮换机制，刷新时旧refresh_token进入黑名单
- 支持用户名、邮箱、手机号三种登录方式

### WebSocket管理
`ConnectionManager` 类管理WebSocket连接，支持：
- 客户端连接管理
- 房间间分组广播
- 实时转录结果广播

## 主要功能模块

### 用户管理
- 用户注册（支持匿名注册为一般用户）
- 用户登录/登出
- 用户信息管理
- 管理员用户管理功能

### 会议管理
- 会议CRUD操作
- 多角色参会人员管理
- 会议签到管理
- 会议内容管理

### 实时功能
- 语音转录（支持多种音频格式）
- WebSocket实时通信
- 转录结果实时广播

### 文档和邮件
- 自动生成会议通知、会议纪要
- 支持Word和PDF格式导出
- 自动邮件通知功能

## 开发注意事项

### 密码加密
系统支持RSA密码加密传输，客户端需要：
1. 请求 `/api/auth/public-key` 获取RSA公钥
2. 使用公钥加密密码后发送到服务器
3. 登录和注册接口自动处理加密密码

### 第三方集成
- 支持第三方令牌生成API (`/api/v1/third-party/token`)
- MinIO对象存储集成
- 外部服务集成管理

### 环境变量配置
关键配置项：
- JWT配置：`JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_MINUTES`
- 数据库配置：`DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_USER`, `DATABASE_PASSWORD`
- API配置：`API_HOST`, `API_PORT`, `DEBUG`
- 邮件配置：`SMTP_SERVER`, `SMTP_PORT`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`

### 日志配置
使用loguru进行日志管理，支持：
- 控制台输出（DEBUG级别）
- 文件输出（INFO和ERROR级别）
- 结构化日志格式

### 安全特性
- CORS中间件配置
- SSL/TLS支持（通过环境变量配置证书路径）
- 密码RSA加密传输
- JWT令牌黑名单机制
- 用户角色权限控制

## 项目结构说明

```
├── main.py                 # 应用入口，FastAPI应用配置
├── models/                 # 数据库模型层
├── services/               # 业务逻辑层
├── router/                 # API路由层
├── schema/                 # Pydantic数据模型
├── db/                     # 数据库访问层（达梦数据库适配器）
├── websocket/              # WebSocket通信管理
├── utils/                  # 工具类和辅助函数
├── tests/                  # 测试文件
├── static/                 # 静态文件
└── requirements.txt        # Python依赖包
```

## 常用开发命令

```bash
# 启动开发服务器
python main.py

# 运行测试
pytest
pytest tests/test_third_party_token_api.py

# 检查代码健康度（如果有linting配置）
# 项目当前未配置linting工具，建议添加flake8或black

# 数据库相关操作通过应用API进行，无独立的migration脚本
```