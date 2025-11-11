# -*- coding: utf-8 -*-
"""数据库配置模块 - 达梦数据库适配版（同步专用）"""
import os
import logging
from typing import Generator, Optional, Dict, Any
from contextlib import contextmanager
from functools import lru_cache

import dmPython
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from dotenv import load_dotenv

# 全局初始化
load_dotenv()  # 加载环境变量
logger = logging.getLogger(__name__)
Base = declarative_base()  # 数据库模型基类（全局唯一）


class DMSyncConfig:
    """达梦数据库同步配置类：专注解析同步连接参数"""

    def __init__(self) -> None:
        # 核心连接配置
        self.host = os.getenv("DM_HOST", "118.89.93.181")
        self.port = os.getenv("DM_PORT", "5236")
        self.user = os.getenv("DM_USER", "SYSDBA")
        self.password = os.getenv("DM_PASSWORD", "Dameng123")
        self.database = os.getenv("DM_DATABASE", "DMDB")

        # 连接池配置（安全解析为整数）
        self.pool_size = self._parse_env_int("DB_POOL_SIZE", 10)
        self.max_overflow = self._parse_env_int("DB_MAX_OVERFLOW", 5)
        self.pool_recycle = self._parse_env_int("DB_POOL_RECYCLE", 3600)
        self.pool_timeout = self._parse_env_int("DB_POOL_TIMEOUT", 30)

        # 其他配置
        self.echo_sql = os.getenv("DB_ECHO_SQL", "false").lower() == "true"

    @staticmethod
    def _parse_env_int(env_key: str, default: int) -> int:
        """安全解析环境变量为整数"""
        try:
            return int(os.getenv(env_key, str(default)))
        except ValueError:
            logger.warning(f"环境变量 {env_key} 解析失败，使用默认值 {default}")
            return default

    def get_sync_url(self) -> str:
        """生成同步连接URL"""
        return f"dm://{self.user}:{self.password}@{self.host}:{self.port}/"

    def validate(self) -> bool:
        """验证配置完整性"""
        required = {
            "DM_HOST": self.host,
            "DM_USER": self.user,
            "DM_PASSWORD": self.password,
            "DM_DATABASE": self.database
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            logger.warning(f"数据库配置缺失：{missing}")
            return False
        return True


class DMSyncManager:
    """达梦数据库同步管理器：封装同步引擎与会话逻辑（单例）"""
    _instance: Optional["DMSyncManager"] = None

    def __new__(cls, config: Optional[DMSyncConfig] = None):
        if cls._instance is None:
            # 允许外部传入配置（便于测试），默认使用默认配置
            cls._instance = super().__new__(cls)
            cls._instance.config = config or DMSyncConfig()
            cls._instance.sync_engine: Optional[Engine] = None
            cls._instance.sync_session_factory: Optional[sessionmaker[Session]] = None
        return cls._instance

    def _setup_connection_hooks(self, engine: Engine) -> None:
        """设置连接事件钩子（达梦会话参数配置）"""

        @event.listens_for(engine, "connect")
        def configure_dm_session(dbapi_conn: dmPython.Connection, _: Any) -> None:
            """连接建立时配置达梦会话参数"""
            try:
                with dbapi_conn.cursor() as cursor:
                    cursor.execute("ALTER SESSION SET NLS_LANGUAGE='AMERICAN'")
                    cursor.execute("ALTER SESSION SET NLS_DATE_FORMAT='YYYY-MM-DD HH24:MI:SS'")
                logger.debug("达梦会话参数配置成功")
            except dmPython.Error as e:
                logger.warning(f"达梦会话参数配置失败：{str(e)}")

    def init_engine(self) -> Optional[Engine]:
        """初始化同步引擎（含连接池）"""
        if not self.config.validate():
            logger.error("配置验证失败，无法初始化引擎")
            return None

        try:
            self.sync_engine = create_engine(
                self.config.get_sync_url(),
                echo=self.config.echo_sql,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_recycle=self.config.pool_recycle,
                pool_timeout=self.config.pool_timeout,
                pool_pre_ping=True  # 连接有效性校验
            )
            self._setup_connection_hooks(self.sync_engine)
            self._test_connection()
            self._init_session_factory()
            logger.info("达梦同步引擎初始化成功")
            return self.sync_engine
        except SQLAlchemyError as e:
            logger.error(f"同步引擎初始化失败：{str(e)}")
            self.sync_engine = None
            return None

    def _test_connection(self) -> None:
        """测试引擎连接有效性"""
        if not self.sync_engine:
            raise RuntimeError("引擎未初始化，无法测试连接")

        try:
            with self.sync_engine.connect() as conn:
                result = conn.execute(text("SELECT 1 FROM dual"))
                if result.scalar() != 1:
                    raise RuntimeError("连接测试结果异常")
                logger.debug("数据库连接测试通过")
        except SQLAlchemyError as e:
            raise RuntimeError(f"连接测试失败：{str(e)}") from e

    def _init_session_factory(self) -> None:
        """初始化同步会话工厂"""
        if not self.sync_engine:
            raise RuntimeError("引擎未就绪，无法初始化会话工厂")

        self.sync_session_factory = sessionmaker(
            bind=self.sync_engine,
            autocommit=False,
            autoflush=False,
            class_=Session,
            expire_on_commit=False
        )

    @contextmanager
    def session_context(self) -> Generator[Session, None, None]:
        """同步会话上下文管理器（自动提交/回滚/关闭）"""
        if not self.sync_session_factory:
            raise RuntimeError("会话工厂未初始化，请先调用init_engine()")

        session: Optional[Session] = None
        try:
            session = self.sync_session_factory()
            yield session
            session.commit()
            logger.debug("事务提交成功")
        except SQLAlchemyError as e:
            if session:
                session.rollback()
            logger.error(f"事务执行失败，已回滚：{str(e)}")
            raise
        finally:
            if session:
                session.close()
                logger.debug("会话已关闭")

    def get_session_dependency(self) -> Generator[Session, None, None]:
        """FastAPI同步路由依赖注入生成器"""
        if not self.sync_session_factory:
            raise RuntimeError("会话工厂未初始化，请先调用init_engine()")

        session: Optional[Session] = None
        try:
            session = self.sync_session_factory()
            yield session
        except SQLAlchemyError as e:
            logger.error(f"会话异常：{str(e)}")
            raise
        finally:
            if session:
                session.close()

    def init_tables(self) -> None:
        """初始化数据库表结构（基于Base子类）"""
        if not self.sync_engine:
            logger.error("引擎未初始化，无法创建表结构")
            return

        try:
            Base.metadata.create_all(bind=self.sync_engine, checkfirst=True)
            logger.info("表结构初始化成功")
        except SQLAlchemyError as e:
            logger.error(f"表结构初始化失败：{str(e)}")
            raise

    def close(self) -> None:
        """关闭连接池（应用退出时调用）"""
        if self.sync_engine:
            self.sync_engine.dispose()
            self.sync_engine = None
            self.sync_session_factory = None
            logger.info("数据库连接池已关闭")
        else:
            logger.warning("连接池未初始化，无需关闭")

    def check_health(self) -> bool:
        """检查数据库健康状态"""
        if not self.sync_engine:
            logger.error("引擎未初始化，健康检查失败")
            return False

        try:
            with self.sync_engine.connect() as conn:
                return conn.execute(text("SELECT 1 FROM dual")).scalar() == 1
        except SQLAlchemyError as e:
            logger.error(f"健康检查失败：{str(e)}")
            return False

    def get_info(self) -> Dict[str, str]:
        """获取数据库连接信息（不含敏感数据）"""
        return {
            "host": self.config.host,
            "port": self.config.port,
            "user": self.config.user,
            "database": self.config.database,
            "pool_size": str(self.config.pool_size),
            "status": "connected" if self.sync_engine else "disconnected"
        }


# --------------------------
# 全局实例与对外接口
# --------------------------
@lru_cache(maxsize=1)
def get_sync_manager() -> DMSyncManager:
    """获取同步管理器单例（线程安全）"""
    return DMSyncManager()


# 初始化引擎（项目启动时调用一次）
def init_db_engine() -> Optional[Engine]:
    """初始化数据库引擎（对外简化接口）"""
    return get_sync_manager().init_engine()


# FastAPI依赖注入接口
def get_db() -> Generator[Session, None, None]:
    """同步会话依赖（用于FastAPI路由）"""
    yield from get_sync_manager().get_session_dependency()


# 上下文管理器接口（兼容手动调用）
def db_context() -> Generator[Session, None, None]:
    """同步会话上下文管理器（with语句使用）"""
    with get_sync_manager().session_context() as session:
        yield session


# 其他功能接口
def init_db_tables() -> None:
    """初始化数据库表结构"""
    get_sync_manager().init_tables()


def check_db_status() -> bool:
    """检查数据库连接状态"""
    return get_sync_manager().check_health()


def get_db_connection_info() -> Dict[str, str]:
    """获取数据库连接信息"""
    return get_sync_manager().get_info()


def shutdown_db() -> None:
    """关闭数据库连接（应用退出时调用）"""
    get_sync_manager().close()


# --------------------------
# 模块自检
# --------------------------
def _self_test() -> None:
    """模块自检函数（直接运行模块时执行）"""
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())

    print("=" * 50)
    print("达梦数据库同步模块自检")
    print("=" * 50)

    manager = get_sync_manager()
    print(f"配置信息: {manager.get_info()}")

    if init_db_engine() and check_db_status():
        print("✅ 数据库连接正常")
        try:
            init_db_tables()
            print("✅ 表结构初始化完成")
        except Exception as e:
            print(f"❌ 表结构初始化失败: {e}")
    else:
        print("❌ 数据库连接失败")

    shutdown_db()
    print("=" * 50)


if __name__ == "__main__":
    _self_test()