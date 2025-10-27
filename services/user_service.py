# 标准库
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Tuple
import re
import pytz

# 第三方库
from sqlalchemy.orm import Session
from sqlalchemy import or_
from loguru import logger
import bcrypt

# 自定义模块
from services.service_models import User, UserRole, UserStatus, Meeting
from schemas import UserCreate, UserUpdate


class UserService(object):
    """用户业务逻辑层
    参考 MeetingService 的代码结构与风格，提供用户的增删改查与安全相关操作。
    所有方法使用 async 定义以保持一致的异步接口风格，内部使用同步 Session 操作。
    """

    async def create_user(self, db: Session, user_data: UserCreate, created_by: Optional[str] = None) -> User:
        """创建新用户（包含密码加密与唯一性检查）
        - 使用 bcrypt 对密码进行加密存储
        - 唯一性校验对齐初始化脚本：仅校验 user_name
        """
        try:
            # 唯一性检查（仅用户名）
            exists = db.query(User).filter(User.user_name == user_data.user_name).first()
            if exists:
                raise ValueError("user_name 已被占用")

            # 加密密码（支持未提供密码时使用默认密码）
            plain_password = user_data.password or "Test@1234"
            hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

            # 创建用户
            user = User(
                id = str(uuid.uuid4()),
                name=user_data.name,
                user_name=user_data.user_name,
                gender=user_data.gender,
                phone=user_data.phone,
                email=user_data.email,
                company=user_data.company,
                user_role=user_data.user_role or UserRole.USER.value,
                status=user_data.status or UserStatus.ACTIVE.value,
                password_hash=hashed,
                created_by=created_by
            )

            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"成功创建用户: {user.id} ({user.email})")
            return user
        except ValueError as ve:
            logger.warning(f"创建用户参数错误: {ve}")
            db.rollback()
            raise ve
        except Exception as e:
            logger.error(f"创建用户失败: {e}")
            db.rollback()
            raise e

    async def get_users_basic(
        self,
        db: Session,
        page: int = 1,
        page_size: int = 20,
        name_keyword: Optional[str] = None,
        company_keyword: Optional[str] = None,
        order_by: str = "name",
        order: str = "asc",
    ) -> tuple[list[User], int]:
        """获取用户基础信息列表（公共接口专用）

        专门用于公共接口，支持按用户名和部门进行模糊查询。
        仅返回活跃状态的用户，用于业务场景如创建会议时选择指定用户。
        Args:
            db: 数据库会话
            page: 页码，从1开始
            page_size: 每页数量，默认20
            name_keyword: 用户姓名关键词（模糊匹配）
            company_keyword: 部门/单位关键词（模糊匹配）
            order_by: 排序字段，默认按姓名排序
            order: 排序方向，asc/desc，默认升序

        Returns:
            Tuple[List[User], int]: (用户列表, 总数)
        """
        try:
            # 基础查询：仅查询活跃状态的用户
            query = db.query(User).filter(User.status == UserStatus.ACTIVE.value)

            # 按用户姓名模糊匹配
            if name_keyword:
                query = query.filter(User.name.like(f"%{name_keyword}%"))

            # 按部门/单位模糊匹配
            if company_keyword:
                query = query.filter(User.company.like(f"%{company_keyword}%"))

            # 计算总数
            total = query.count()

            # 排序
            sort_col = getattr(User, order_by, User.name)
            if order.lower() == "desc":
                query = query.order_by(sort_col.desc())
            else:
                query = query.order_by(sort_col.asc())

            # 分页
            page = max(1, page)
            page_size = max(1, page_size)
            items = query.offset((page - 1) * page_size).limit(page_size).all()
            return items, total
        except Exception as e:
            logger.error(f"公共用户列表查询失败: {e}")
            raise e

    async def get_users(
        self,
        db: Session,
        page: int = 1,
        page_size: int = 20,
        user_role: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        name_keyword: Optional[str] = None,
        user_name_keyword: Optional[str] = None,
        email_keyword: Optional[str] = None,
        company_keyword: Optional[str] = None,
        order_by: str = "created_at",
        order: str = "desc",
    ) -> tuple[list[User], int]:
        """获取用户列表（支持分页与筛选）
        返回 (items, total) 二元组
        """
        try:
            query = db.query(User)

            if user_role:
                query = query.filter(User.user_role == user_role)
            if status:
                query = query.filter(User.status == status)

            # 原有的通用关键词匹配（保持向后兼容）
            if keyword:
                like = f"%{keyword}%"
                query = query.filter(
                    or_(
                        User.name.like(like),
                        User.email.like(like),
                        User.company.like(like),
                        User.user_name.like(like),
                    )
                )
            # 独立字段的模糊匹配（AND 关系）
            if name_keyword:
                query = query.filter(User.name.like(f"%{name_keyword}%"))
            if user_name_keyword:
                query = query.filter(User.user_name.like(f"%{user_name_keyword}%"))
            if email_keyword:
                query = query.filter(User.email.like(f"%{email_keyword}%"))
            if company_keyword:
                query = query.filter(User.company.like(f"%{company_keyword}%"))

            total = query.count()

            # 排序
            sort_col = getattr(User, order_by, User.created_at)
            query = query.order_by(sort_col.desc() if order.lower() == "desc" else sort_col.asc())

            # 分页
            page = max(1, page)
            page_size = max(1, page_size)
            items = query.offset((page - 1) * page_size).limit(page_size).all()
            return items, total
        except Exception as e:
            logger.error(f"查询用户列表失败: {e}")
            raise e

    async def get_user_by_id(self, db: Session, user_id: str, active_only: bool = True) -> Optional[User]:
        """根据ID获取用户
        - active_only=True：仅返回活跃用户（用于非管理员或公共查询场景）
        - active_only=False：返回任意状态用户（用于管理员场景）
        """
        try:
            # 同步会话使用 ORM query；不进行 await
            query = db.query(User).filter(
                User.id == user_id
            )
            if active_only:
                query = query.filter(User.status == UserStatus.ACTIVE.value)
            return query.first()
        except Exception as e:
            logger.error(f"查询用户失败(id={user_id}): {e}")
            raise e

    async def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        user = db.query(User).filter(User.email == email).first()
        try:
            return user
        except Exception as e:
            logger.error(f"查询用户失败(email={email}): {e}")
            raise e

    def get_user_by_username(self, db: Session, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        user = db.query(User).filter(User.user_name == username).first()
        try:
            return user
        except Exception as e:
            logger.error(f"查询用户失败(username={username}): {e}")
            raise e

    async def get_user_by_phone(self, db: Session, phone: str) -> Optional[User]:
        """根据手机号获取用户"""
        user = db.query(User).filter(User.phone == phone).first()
        try:
            return user
        except Exception as e:
            logger.error(f"查询用户失败(phone={phone}): {e}")
            raise e

    async def get_user_by_login_identifier(self, db: Session, identifier: str) -> Optional[User]:
        """
        根据登录标识符获取用户
        支持用户名、邮箱、手机号三种方式
        """
        import re
        try:
            # 检查是否为邮箱格式
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            # 检查是否为手机号格式
            phone_pattern = r'^1(?:3\d|4[01456879]|5[0-35-9]|6[2567]|7[0-8]|8\d|9[0-35-9])\d{8}$'
            if re.match(email_pattern, identifier):
                # 邮箱登录
                return self.get_user_by_email(db, identifier)
            elif re.match(phone_pattern, identifier):
                # 手机号登录
                return self.get_user_by_phone(db, identifier)
            else:
                # 用户名登录
                return self.get_user_by_username(db, identifier)

        except Exception as e:
            logger.error(f"根据登录标识符查询用户失败(identifier={identifier}): {e}")
            raise e

    async def update_user(self,
                          db: Session,
                          user_id: str,
                          update_data: UserUpdate,
                          updated_by: Optional[str] = None,
                          operator_role: Optional[str] = None,
                          operator_id: Optional[str] = None) -> Optional[User]:
        """更新用户信息（包含唯一性检查与权限控制）
        - 仅更新请求中显式提供的字段（即使值为 None 也会应用），以支持将可选字段置空
        - 权限控制：非管理员只能更新自己的信息，且不能修改角色或状态
        - 操作日志：记录变更字段及操作者
        """
        try:
            # 权限控制：如果提供了操作者信息，进行校验
            if operator_role and operator_role != UserRole.ADMIN.value:
                if not operator_id or str(operator_id) != str(user_id):
                    raise PermissionError("非管理员用户只能修改自己的信息")
            
            # 将字符串ID转换为整数以匹配 BigInteger 主键类型
            try:
                user_id_int = int(user_id)
            except (TypeError, ValueError):
                user_id_int = None
            user = db.query(User).filter(User.id == (user_id_int if user_id_int is not None else user_id)).first()
            if not user:
                return None

            # 仅对请求中显式提供的字段进行处理
            provided = update_data.model_dump(exclude_unset=True)

            # 非管理员禁止修改角色与状态
            if operator_role and operator_role != UserRole.ADMIN.value:
                for forbidden in ("user_role", "status"):
                    if forbidden in provided:
                        raise PermissionError("非管理员用户只能修改自己的信息")

            # 如果更新 user_name，需要检查唯一性（对齐初始化脚本）
            def check_unique(field_name: str, new_value: Optional[str]) -> None:
                if new_value is None:
                    return
                exists = db.query(User).filter(
                    getattr(User, field_name) == new_value,
                    User.id != (user_id_int if user_id_int is not None else user_id)
                ).first()
                if exists:
                    raise ValueError(f"{field_name} 已被占用")

            # 应用更新（包含可能的置空），并记录变更
            changes: dict[str, tuple[Any, Any]] = {}
            for field, new_value in provided.items():
                if field == "user_name":
                    check_unique("user_name", new_value)
                old_value = getattr(user, field, None)
                if old_value != new_value:
                    changes[field] = (old_value, new_value)
                setattr(user, field, new_value)

            if updated_by is not None:
                user.updated_by = updated_by
            user.updated_at = datetime.now(pytz.timezone('Asia/Shanghai'))
            db.commit()
            db.refresh(user)

            # 操作日志：记录操作者与变更明细
            try:
                logger.info(f"用户更新: operator_id={updated_by} target_id={user_id} changes={changes}")
            except Exception:
                pass

            return user
        except PermissionError as pe:
            logger.warning(f"更新用户权限拒绝(id={user_id}): {pe}")
            db.rollback()
            raise pe
        except ValueError as ve:
            logger.warning(f"更新用户信息参数错误(id={user_id}): {ve}")
            db.rollback()
            raise ve
        except Exception as e:
            logger.error(f"更新用户信息失败(id={user_id}): {e}")
            db.rollback()
            raise e

    def delete_user(self,
                          db: Session,
                          user_id: str,
                          operator_id: Optional[str] = None,
                          hard: bool = False) -> bool:
        """删除用户
        - 默认软删除：将用户状态置为 inactive
        - 硬删除(hard=True)：物理删除用户，并清理与用户相关的外键引用（置空）
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not hard:
                # 软删除：仅状态置为inactive
                user.status = UserStatus.INACTIVE.value
                if operator_id:
                    user.updated_by = operator_id
                user.updated_at = datetime.now(pytz.timezone('Asia/Shanghai'))
                db.commit()
                logger.info(f"已软删除用户: {user_id}")
                return True
            else:
                # 硬删除：清理引用并物理删除
                # 1) 清理会议记录中的 created_by / updated_by 引用（会议表中为 BigInteger）
                if user_id is not None:
                    db.query(Meeting).filter(Meeting.created_by == user_id).update({Meeting.created_by: None})
                    db.query(Meeting).filter(Meeting.updated_by == user_id).update({Meeting.updated_by: None})

                # 2) 清理其他用户记录中的 created_by / updated_by 自引用（用户表中为 String）
                db.query(User).filter(User.created_by == str(user_id)).update({User.created_by: None})
                db.query(User).filter(User.updated_by == str(user_id)).update({User.updated_by: None})

                # 3) 删除用户本身
                db.delete(user)
                db.commit()
            logger.info(f"已硬删除用户并清理引用: {user_id}")
            return True
        except Exception as e:
            logger.error(f"删除用户失败(id={user_id}, hard={hard}): {e}")
            db.rollback()
            raise e

    def verify_password(self, user: User, plain_password: str) -> bool:
        """验证用户密码（bcrypt）"""
        try:
            if not user.password_hash:
                return False
            return bcrypt.checkpw(plain_password.encode("utf-8"), user.password_hash.encode("utf-8"))
        except Exception as e:
            logger.error(f"验证密码失败(user={user.id}): {e}")
            return False

    async def change_user_status(self,
                                 db: Session,
                                 user_id: str,
                                 status: str,
                                 operator_id: Optional[str] = None) -> bool:
        """修改用户状态：active / inactive / suspended"""
        try:
            if status not in [UserStatus.ACTIVE.value, UserStatus.INACTIVE.value, UserStatus.SUSPENDED.value]:
                raise ValueError("非法的用户状态")
            # 将字符串ID转换为整数以匹配 BigInteger 主键类型
            try:
                user_id_int = int(user_id)
            except (TypeError, ValueError):
                user_id_int = None
            user = db.query(User).filter(User.id == (user_id_int if user_id_int is not None else user_id)).first()
            if not user:
                return False
            user.status = status
            if operator_id:
                user.updated_by = operator_id
            user.updated_at = datetime.now(pytz.timezone('Asia/Shanghai'))
            db.commit()
            logger.info(f"用户状态修改成功: {user_id} -> {status}")
            return True
        except ValueError as ve:
            logger.warning(f"修改用户状态参数错误(id={user_id}): {ve}")
            db.rollback()
            raise ve
        except Exception as e:
            logger.error(f"修改用户状态失败(id={user_id}): {e}")
            db.rollback()
            raise e

    async def reset_password(self,
                             db: Session,
                             user_id: str,
                             operator_id: Optional[str] = None,
                             default_password: str = "Test@1234") -> bool:
        """重置用户密码为默认值（bcrypt加密），返回是否成功"""
        try:
            # 将字符串ID转换为整数以匹配 BigInteger 主键类型
            try:
                user_id_int = int(user_id)
            except (TypeError, ValueError):
                user_id_int = None
            user = db.query(User).filter(User.id == (user_id_int if user_id_int is not None else user_id)).first()
            if not user:
                return False
            # 生成新的密码哈希
            hashed = bcrypt.hashpw(default_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            user.password_hash = hashed
            if operator_id:
                user.updated_by = operator_id
            user.updated_at = datetime.now(pytz.timezone('Asia/Shanghai'))
            db.commit()
            logger.info(f"用户密码已重置: user_id={user_id}")
            return True
        except Exception as e:
            logger.error(f"重置用户密码失败(id={user_id}): {e}")
            db.rollback()
            raise e

    async def change_password(self,
                              db: Session,
                              user_id: str,
                              old_password: str,
                              new_password: str,
                              operator_id: Optional[str] = None) -> bool:
        """修改用户密码（需提供旧密码，避免旧密码复用）
        规则：
        - 校验用户存在与状态
        - 验证旧密码正确
        - 新密码不得与旧密码相同（防止复用）
        - 使用bcrypt加密存储
        - 原子提交，失败回滚
        """
        try:
            try:
                user_id_int = int(user_id)
            except (TypeError, ValueError):
                user_id_int = None
            user = db.query(User).filter(User.id == (user_id_int if user_id_int is not None else user_id)).first()
            if not user:
                return False
            if str(user.status) != UserStatus.ACTIVE.value:
                raise PermissionError("用户状态不允许修改密码")

            # 验证旧密码
            if not self.verify_password(user, plain_password=old_password):
                raise PermissionError("旧密码不正确")
            # 防止复用旧密码
            if self.verify_password(user, plain_password=new_password):
                raise ValueError("新密码不能与旧密码相同")

            # 加密并更新
            hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            user.password_hash = hashed
            if operator_id:
                user.updated_by = operator_id
            user.updated_at = datetime.now(pytz.timezone('Asia/Shanghai'))
            db.commit()
            logger.info(f"用户修改密码成功: user_id={user_id}")
            return True
        except PermissionError as pe:
            logger.warning(f"修改密码权限拒绝(id={user_id}): {pe}")
            db.rollback()
            raise pe
        except ValueError as ve:
            logger.warning(f"修改密码参数错误(id={user_id}): {ve}")
            db.rollback()
            raise ve
        except Exception as e:
            logger.error(f"修改密码失败(id={user_id}): {e}")
            db.rollback()
            raise e