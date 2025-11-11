# -*- coding: utf-8 -*-
"""数据库配置模块 - 达梦数据库适配版（类封装版）"""
import os
import logging
from typing import Generator, Optional, Dict
from contextlib import contextmanager

import dmPython
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from dotenv import load_dotenv

# 全局初始化：加载环境变量、配置日志、基础模型类
load_dotenv()
logger = logging.getLogger(__name__)
Base = declarative_base()  # 所有数据库模型的基类，全局唯一


class DMDatabaseManager:
    """达梦数据库管理器（单例模式）：封装配置、引擎、会话管理全流程"""
    _instance: Optional["DMDatabaseManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 初始化默认属性
            cls._instance.sync_engine: Optional[Engine] = None
            cls._instance.sync_session_factory: Optional[sessionmaker] = None
            # 加载配置
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        """加载数据库配置（从环境变量或默认值）"""
        # 核心连接配置
        self.host = os.getenv("DM_HOST", "118.89.93.181")
        self.port = os.getenv("DM_PORT", "5236")
        self.user = os.getenv("DM_USER", "SYSDBA")
        self.password = os.getenv("DM_PASSWORD", "Dameng123")
        self.database = os.getenv("DM_DATABASE", "DMDB")
        # 连接池配置
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "5"))
        self.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
        self.pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        # 其他配置
        self.echo_sql = os.getenv("DB_ECHO_SQL", "false").lower() == "true"

    def validate_config(self) -> bool:
        """验证配置完整性（必填项是否缺失）"""
        required_configs = [self.host, self.user, self.password, self.database]
        if not all(required_configs):
            missing_keys = [key for key, val in {
                "DM_HOST": self.host,
                "DM_USER": self.user,
                "DM_PASSWORD": self.password,
                "DM_DATABASE": self.database
            }.items() if not val]
            logger.warning(f"数据库配置缺失：{missing_keys}")
            return False
        return True

    def _setup_connection_pool(self, engine: Engine) -> None:
        """设置连接池事件监听（达梦会话参数配置）"""

        @event.listens_for(engine, "connect")
        def set_dm_session_params(dbapi_connection, _):
            """连接建立时自动配置达梦会话参数"""
            try:
                cursor = dbapi_connection.cursor()
                # 达梦特定参数：字符集、日期格式优化
                cursor.execute("ALTER SESSION SET NLS_LANGUAGE='AMERICAN'")
                cursor.execute("ALTER SESSION SET NLS_DATE_FORMAT='YYYY-MM-DD HH24:MI:SS'")
                cursor.close()
                logger.debug("达梦数据库会话参数配置成功")
            except Exception as e:
                logger.warning(f"达梦会话参数配置失败：{str(e)}")

    def create_sync_engine(self) -> Optional[Engine]:
        """创建达梦同步数据库引擎（含连接池配置）"""
        # 先验证配置
        if not self.validate_config():
            logger.error("配置验证失败，无法创建引擎")
            return None

        try:
            # 构建达梦连接URL（dm://用户名:密码@主机:端口/）
            sync_url = f"dm://{self.user}:{self.password}@{self.host}:{self.port}/"
            # 创建引擎
            self.sync_engine = create_engine(
                sync_url,
                echo=self.echo_sql,
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                pool_recycle=self.pool_recycle,
                pool_pre_ping=True  # 连接前校验有效性，避免无效连接
            )
            # 配置连接池事件
            self._setup_connection_pool(self.sync_engine)
            # 测试连接可用性
            self._test_connection()
            # 初始化会话工厂
            self._init_session_factory()
            logger.info("达梦同步数据库引擎创建成功")
            return self.sync_engine
        except Exception as e:
            logger.error(f"达梦引擎创建失败：{str(e)}")
            self.sync_engine = None
            return None

    def _test_connection(self) -> None:
        """测试数据库连接（验证引擎可用性）"""
        if not self.sync_engine:
            raise RuntimeError("引擎未初始化，无法测试连接")

        with self.sync_engine.connect() as conn:
            # 执行简单查询（达梦系统表：查询用户名）
            result = conn.execute(text("SELECT username FROM dba_users WHERE rownum = 1"))
            first_user = result.scalar()
            logger.debug(f"数据库连接测试成功，示例用户：{first_user}")

    def _init_session_factory(self) -> None:
        """初始化同步会话工厂（生成数据库会话实例）"""
        if not self.sync_engine:
            raise RuntimeError("引擎未就绪，无法初始化会话工厂")

        self.sync_session_factory = sessionmaker(
            bind=self.sync_engine,
            autocommit=False,
            autoflush=False,
            class_=Session,
            expire_on_commit=False  # 避免commit后属性访问失效
        )

    @contextmanager
    def get_db_context(self) -> Generator[Session, None, None]:
        """上下文管理器：获取数据库会话（自动提交/回滚/关闭）"""
        if not self.sync_session_factory:
            raise RuntimeError("会话工厂未初始化，请先创建引擎")

        db = self.sync_session_factory()
        try:
            yield db
            db.commit()
            logger.debug("数据库事务提交成功")
        except Exception as e:
            db.rollback()
            logger.error(f"数据库操作失败，已回滚：{str(e)}")
            raise  # 重新抛出异常，让调用方处理
        finally:
            db.close()
            logger.debug("数据库会话已关闭")

    def get_db_dependency(self) -> Generator[Session, None, None]:
        """FastAPI依赖注入专用：获取数据库会话（简化路由层调用）"""
        if not self.sync_session_factory:
            raise RuntimeError("会话工厂未初始化，无法提供依赖")

        db = self.sync_session_factory()
        try:
            yield db
        except Exception as e:
            logger.error(f"会话异常：{str(e)}")
            raise
        finally:
            db.close()

    def init_db_tables(self) -> None:
        """初始化数据库表结构（根据Base子类自动创建表）"""
        if not self.sync_engine:
            logger.error("引擎未就绪，无法初始化表结构")
            return

        try:
            Base.metadata.create_all(bind=self.sync_engine)
            logger.info("数据库表结构初始化成功")
        except Exception as e:
            logger.error(f"表结构初始化失败：{str(e)}")
            raise

    def close_connection_pool(self) -> None:
        """关闭数据库连接池（应用退出时调用）"""
        if self.sync_engine:
            self.sync_engine.dispose()
            self.sync_engine = None
            self.sync_session_factory = None
            logger.info("数据库连接池已关闭")
        else:
            logger.warning("连接池未初始化，无需关闭")

    def check_health(self) -> bool:
        """检查数据库健康状态（返回True表示正常）"""
        if not self.sync_engine:
            logger.error("引擎未初始化，健康检查失败")
            return False

        try:
            with self.sync_engine.connect() as conn:
                # 执行轻量查询验证连接
                result = conn.execute(text("SELECT 1 FROM dual"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"健康检查失败：{str(e)}")
            return False

    def get_db_info(self) -> Dict[str, str]:
        """获取数据库连接信息（隐藏敏感密码，用于监控/日志）"""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "database": self.database,
            "pool_size": str(self.pool_size),
            "status": "connected" if self.sync_engine else "disconnected"
        }

    @contextmanager
    def app_lifecycle_manager(self) -> Generator[Engine, None, None]:
        """应用生命周期管理器：自动初始化引擎+关闭连接池"""
        try:
            logger.info("应用启动：初始化达梦数据库连接")
            engine = self.create_sync_engine()
            if not engine:
                raise RuntimeError("数据库引擎初始化失败，应用无法启动")
            yield engine
        finally:
            logger.info("应用关闭：清理数据库连接")
            self.close_connection_pool()


# --------------------------
# 全局实例与对外接口（简化调用）
# --------------------------
# 单例管理器实例（全局唯一，避免重复创建引擎）
dm_db_manager = DMDatabaseManager()


# 对外暴露的核心函数（与原代码用法兼容，降低迁移成本）
def get_db() -> Generator[Session, None, None]:
    """原contextmanager风格接口：兼容旧代码"""
    with dm_db_manager.get_db_context() as db:
        yield db


def get_db_session() -> Generator[Session, None, None]:
    """原FastAPI依赖接口：兼容旧路由代码"""
    yield from dm_db_manager.get_db_dependency()


def init_db() -> None:
    """原表初始化接口：兼容旧代码"""
    dm_db_manager.init_db_tables()


def check_db_health() -> bool:
    """原健康检查接口：兼容旧代码"""
    return dm_db_manager.check_health()


def get_db_info() -> Dict[str, str]:
    """原信息查询接口：兼容旧代码"""
    return dm_db_manager.get_db_info()
