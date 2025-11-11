from datetime import datetime
from typing import Optional
import re
from pydantic import BaseModel, Field, EmailStr, validator


class UserBase(BaseModel):
    """用户基础模型（公共字段）"""
    name: str = Field(..., min_length=1, max_length=100, description="用户姓名")
    email: Optional[EmailStr] = Field(None, description="邮箱地址")
    gender: Optional[str] = Field(None, description="性别")
    phone: Optional[str] = Field(None, description="手机号码")
    company: Optional[str] = Field(None, max_length=200, description="所属公司/单位")
    user_role: str = Field(default="user", description="用户角色")
    status: str = Field(default="active", description="用户状态")

    @validator('gender')
    def validate_gender(cls, v):
        if v is not None and v not in ['male', 'female', 'other']:
            raise ValueError('性别必须为male、female或other')
        return v

    @validator('phone')
    def validate_phone(cls, v):
        if v is not None:
            pattern = r'^1(?:3\d|4[01456879]|5[0-35-9]|6[2567]|7[0-8]|8\d|9[0-35-9])\d{8}$'
            if not re.match(pattern, v):
                raise ValueError('手机号格式不正确')
        return v

    @validator('user_role')
    def validate_role(cls, v):
        if v not in ['admin', 'user']:
            raise ValueError('用户角色必须为admin或user')
        return v

    @validator('status')
    def validate_status(cls, v):
        if v not in ['active', 'inactive', 'suspended']:
            raise ValueError('用户状态必须为active、inactive或suspended')
        return v


class UserResponse(UserBase):
    """用户详情响应模型"""
    user_name: str = Field(..., min_length=3, max_length=50, description="用户账号")
    id: str = Field(..., description="用户唯一标识")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    created_by: Optional[str] = Field(None, description="创建者用户ID")
    updated_by: Optional[str] = Field(None, description="更新者用户ID")

    class Config(object):
        from_attributes = True


class UserBasicResponse(BaseModel):
    """用户基础信息响应（用于业务关联）"""
    id: str = Field(..., description="用户唯一标识")
    name: str = Field(..., description="用户姓名")
    user_name: str = Field(..., description="用户账号")
    phone: Optional[str] = Field(None, description="手机号码")
    company: Optional[str] = Field(None, description="部门/单位名称")
    email: Optional[EmailStr] = Field(None, description="邮箱地址")

    class Config(object):
        from_attributes = True


class UserRegister(BaseModel):
    """用户注册请求模型"""
    name: str = Field(..., min_length=1, max_length=100, description="用户姓名")
    user_name: str = Field(..., min_length=3, max_length=50, description="用户账号")
    password: str = Field(..., min_length=8, max_length=500, description="用户密码")
    gender: Optional[str] = Field(None, description="性别")
    phone: Optional[str] = Field(None, description="手机号码")
    company: Optional[str] = Field(None, max_length=200, description="所属公司/单位")
    email: Optional[EmailStr] = Field(None, description="邮箱地址")

    @validator('email', 'phone', 'gender', 'company', pre=True)
    def empty_str_to_none(cls, v):
        if isinstance(v, str) and v.strip() == '':
            return None
        return v

    @validator('user_name')
    def validate_user_name(cls, v):
        v = v.strip()
        if len(v) < 3 or len(v) > 50:
            raise ValueError('用户名长度必须在3-50个字符之间')
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('用户名仅支持字母、数字、下划线和中划线')
        return v

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('密码长度至少为8位')
        has_upper = bool(re.search(r'[A-Z]', v))
        has_lower = bool(re.search(r'[a-z]', v))
        has_digit = bool(re.search(r'\d', v))
        has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', v))
        if sum([has_upper, has_lower, has_digit, has_special]) < 3:
            raise ValueError('密码必须包含大写、小写、数字、特殊字符中的至少3种')
        return v


class UserLogin(BaseModel):
    """用户登录请求模型"""
    username: str = Field(..., min_length=1, max_length=255, description="用户名/邮箱/手机号")
    password: str = Field(..., min_length=1, max_length=500, description="密码")

    @validator('username')
    def validate_username(cls, v):
        v = v.strip()
        if len(v) < 1 or len(v) > 255:
            raise ValueError('用户名长度必须在1-255个字符之间')
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        phone_pattern = r'^1(?:3\d|4[01456879]|5[0-35-9]|6[2567]|7[0-8]|8\d|9[0-35-9])\d{8}$'
        username_pattern = r'^[a-zA-Z0-9_-]+$'
        if not (re.match(email_pattern, v) or re.match(phone_pattern, v) or re.match(username_pattern, v)):
            raise ValueError('用户名格式不正确（支持用户名、邮箱、手机号）')
        return v


class UserCreate(UserBase):
    """创建用户请求模型（管理员用）"""
    user_name: str = Field(..., min_length=3, max_length=50, description="用户账号")
    email: Optional[EmailStr] = Field(None, description="邮箱地址")
    password: Optional[str] = Field(None, min_length=8, max_length=500, description="用户密码")

    @validator('email', 'phone', 'gender', 'company', "password", pre=True)
    def empty_str_to_none(cls, v):
        if isinstance(v, str) and v.strip() == '':
            return None
        return v

    @validator('user_name')
    def validate_user_name(cls, v):
        v = v.strip()
        if len(v) < 3 or len(v) > 50:
            raise ValueError('用户名长度必须在3-50个字符之间')
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('用户名仅支持字母、数字、下划线和中划线')
        return v

    @validator('password')
    def validate_password(cls, v):
        if v is None:
            return v
        if len(v) < 8:
            raise ValueError('密码长度至少为8位')
        has_upper = bool(re.search(r'[A-Z]', v))
        has_lower = bool(re.search(r'[a-z]', v))
        has_digit = bool(re.search(r'\d', v))
        has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', v))
        if sum([has_upper, has_lower, has_digit, has_special]) < 3:
            raise ValueError('密码必须包含大写、小写、数字、特殊字符中的至少3种')
        return v


class UserUpdate(BaseModel):
    """更新用户请求模型"""
    name: str = Field(..., min_length=1, max_length=100, description="用户姓名")
    user_name: str = Field(..., min_length=3, max_length=50, description="用户账号")
    email: Optional[EmailStr] = Field(None, description="邮箱地址")
    gender: Optional[str] = Field(None, description="性别")
    phone: Optional[str] = Field(None, description="手机号码")
    company: Optional[str] = Field(None, max_length=200, description="所属公司/单位")
    user_role: Optional[str] = Field(None, description="用户角色")
    status: Optional[str] = Field(None, description="用户状态")


class PasswordChange(BaseModel):
    """密码修改请求模型"""
    old_password: str = Field(..., min_length=8, max_length=500, description="旧密码")
    new_password: str = Field(..., min_length=8, max_length=500, description="新密码")

    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('新密码长度至少为8位')
        has_upper = bool(re.search(r'[A-Z]', v))
        has_lower = bool(re.search(r'[a-z]', v))
        has_digit = bool(re.search(r'\d', v))
        has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', v))
        if sum([has_upper, has_lower, has_digit, has_special]) < 3:
            raise ValueError('新密码必须包含大写、小写、数字、特殊字符中的至少3种')
        return v