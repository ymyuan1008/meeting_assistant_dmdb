# JWT鉴权装饰器和用户信息获取说明文档

## 1. 概述

本系统采用JWT（JSON Web Token）进行用户身份认证和权限控制。通过自定义的认证服务和装饰器，实现了灵活的权限控制机制，支持多种用户角色和权限级别的访问控制。

## 2. 系统架构

### 2.1 核心组件

- **AuthService**: JWT认证服务类，负责令牌的生成、验证、刷新和撤销
- **AuthDependencies**: 认证依赖模块，提供各种认证装饰器
- **UserService**: 用户服务类，负责用户信息的查询和验证
- **User**: 用户模型类，定义用户数据结构

### 2.2 认证流程

1. 用户通过登录接口进行身份验证
2. 系统生成access_token和refresh_token
3. 客户端在后续请求中携带access_token
4. 服务端通过装饰器验证令牌有效性
5. 根据用户角色进行权限控制

## 3. 支持的认证装饰器

### 3.1 require_auth

**功能**: 要求用户已登录认证

**使用场景**: 需要用户登录才能访问的接口

**使用方法**:
```python
from services.auth_dependencies import require_auth
from services.service_models import User

@router.get("/api/protected")
async def protected_route(current_user: User = Depends(require_auth)):
    # current_user 包含当前登录用户的信息
    return {"message": f"Hello, {current_user.name}"}
```

**权限说明**: 
- 任何已登录且状态为active的用户都可以访问
- 未登录或令牌无效将返回401错误
- 用户状态非active将返回403错误

### 3.2 require_admin

**功能**: 要求管理员权限

**使用场景**: 仅管理员可以访问的管理接口

**使用方法**:
```python
from services.auth_dependencies import require_admin
from services.service_models import User

@router.delete("/api/users/{user_id}")
async def delete_user(user_id: int, current_user: User = Depends(require_admin)):
    # 只有管理员可以删除用户
    # current_user 包含当前管理员用户的信息
    return {"message": "User deleted"}
```

**权限说明**:
- 仅user_role为"admin"的用户可以访问
- 非管理员用户将返回403错误

### 3.3 require_roles

**功能**: 要求特定角色之一

**使用场景**: 需要特定角色才能访问的接口

**使用方法**:
```python
from services.auth_dependencies import require_roles
from services.service_models import User

# 仅允许admin和user角色访问
@router.get("/api/semi-protected")
async def semi_protected_route(current_user: User = Depends(require_roles(["admin", "user"]))):
    return {"message": f"Access granted to {current_user.user_role}"}
```

**权限说明**:
- 用户角色必须在指定的角色列表中
- 不符合角色要求将返回403错误

## 4. 用户信息获取

### 4.1 通过装饰器参数获取

在使用认证装饰器的路由处理函数中，可以通过函数参数直接获取当前用户信息：

```python
from services.auth_dependencies import require_auth
from services.service_models import User

@router.get("/api/profile")
async def get_profile(current_user: User = Depends(require_auth)):
    # current_user 是一个User对象，包含完整的用户信息
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "user_role": current_user.user_role,
        "status": current_user.status,
        # ... 其他用户字段
    }
```

### 4.2 User对象字段说明

通过认证装饰器获取的User对象包含以下字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | 用户唯一标识 |
| name | str | 用户姓名 |
| user_name | str | 用户账号 |
| gender | str | 性别 |
| phone | str | 手机号码 |
| email | str | 邮箱地址 |
| company | str | 所属单位 |
| user_role | str | 用户角色 ("admin" 或 "user") |
| status | str | 用户状态 ("active", "inactive", "suspended") |
| password_hash | str | 密码哈希值 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |
| created_by | int | 创建者ID |
| updated_by | int | 更新者ID |

## 5. 令牌管理

### 5.1 令牌类型

系统支持两种类型的JWT令牌：

1. **access_token**: 用于API访问认证，有效期较短（默认240分钟/4小时）
2. **refresh_token**: 用于刷新access_token，有效期较长（默认30天）

### 5.2 令牌刷新

通过`/api/auth/refresh`接口使用refresh_token刷新令牌：

```bash
POST /api/auth/refresh
Authorization: Bearer <refresh_token>
```

响应将包含新的access_token和refresh_token，旧的refresh_token将被撤销。

### 5.3 令牌撤销

通过`/api/auth/logout`接口撤销当前令牌：

```bash
POST /api/auth/logout
Authorization: Bearer <access_token>
```

## 6. 错误处理

### 6.1 认证错误

- **401 Unauthorized**: 令牌无效、过期或缺失
- **403 Forbidden**: 用户权限不足或状态异常

### 6.2 错误响应格式

```json
{
  "code": "unauthorized",
  "message": "无效或过期的Token"
}
```

## 7. 环境变量配置

JWT相关的环境变量配置：

```env
# JWT Configuration
JWT_SECRET=apkMJPa1m693UbMu1PvA1xPi7oExmXoDYqOaCHafMEM
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=240
REFRESH_TOKEN_EXPIRE_MINUTES=43200
JWT_ISSUER=meeting-assistant
JWT_AUDIENCE=meeting-assistant-clients
```

## 8. 使用示例

### 8.1 基础用户信息接口

```python
from fastapi import APIRouter, Depends
from services.auth_dependencies import require_auth
from services.service_models import User

router = APIRouter()

@router.get("/api/user/info")
async def get_user_info(current_user: User = Depends(require_auth)):
    """获取当前用户信息"""
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.user_role
    }
```

### 8.2 管理员接口

```python
from fastapi import APIRouter, Depends
from services.auth_dependencies import require_admin
from services.service_models import User

router = APIRouter()

@router.get("/api/admin/users")
async def list_all_users(current_user: User = Depends(require_admin)):
    """管理员获取所有用户列表"""
    # 只有管理员可以访问此接口
    return {"message": "Admin access granted"}
```

### 8.3 多角色接口

```python
from fastapi import APIRouter, Depends
from services.auth_dependencies import require_roles
from services.service_models import User

router = APIRouter()

@router.get("/api/reports")
async def get_reports(current_user: User = Depends(require_roles(["admin", "manager"]))):
    """仅管理员和经理可以访问报告"""
    return {"message": f"Access granted to {current_user.user_role}"}
```

## 9. 最佳实践

### 9.1 选择合适的装饰器

- 公共接口：不使用任何认证装饰器
- 用户接口：使用`require_auth`
- 管理接口：使用`require_admin`
- 特定角色接口：使用`require_roles`

### 9.2 安全建议

1. 始终验证用户状态（active/inactive/suspended）
2. 在敏感操作前再次验证用户权限
3. 避免在客户端存储敏感用户信息
4. 定期刷新令牌以提高安全性

### 9.3 性能优化

1. 合理设置令牌过期时间
2. 使用令牌黑名单机制防止令牌滥用
3. 在高并发场景下考虑使用Redis存储令牌黑名单