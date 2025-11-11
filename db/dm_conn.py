# -*- coding: utf-8 -*-
"""数据库配置模块 - 达梦数据库适配版"""
import os
import logging
from typing import Generator, Optional
from contextlib import contextmanager

import dmPython
from sqlalchemy import create_engine, event
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv


# 配置日志
logger = logging.getLogger(__name__)
# 加载环境变量
load_dotenv()


class DMDBConfig:
    """达梦数据库配置类"""

    # 数据库连接配置
    HOST = os.getenv("DM_HOST", "118.89.93.181")
    PORT = os.getenv("DM_PORT", "5236")
    USER = os.getenv("DM_USER", "SYSDBA")
    PASSWORD = os.getenv("DM_PASSWORD", "Dameng123")
    DATABASE = os.getenv("DM_DATABASE", "DMDB")

    # 连接池配置
    POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
    MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "5"))
    POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))

    # 其他配置
    ECHO_SQL = os.getenv("DB_ECHO_SQL", "false").lower() == "true"

    @classmethod
    def get_sync_url(cls) -> str:
        """获取同步连接URL"""
        return (
            f"dm://{cls.USER}:{cls.PASSWORD}@{cls.HOST}:{cls.PORT}/"
        )

    @classmethod
    def validate_config(cls) -> bool:
        """验证配置是否完整"""
        required_vars = [cls.HOST, cls.USER, cls.PASSWORD, cls.DATABASE]
        if not all(required_vars):
            missing = [var for var in ['DM_HOST', 'DM_USER', 'DM_PASSWORD']
                       if not os.getenv(var)]
            logger.warning(f"数据库配置缺失: {missing}")
            return False
        return True


def setup_connection_pool(engine: Engine) -> None:
    """设置连接池事件监听"""

    @event.listens_for(engine, "connect")
    def set_dm_session(dbapi_connection, connection_record):
        """设置达梦数据库会话参数"""
        try:
            # 设置达梦数据库特定的会话参数
            cursor = dbapi_connection.cursor()
            # 设置字符集和优化参数
            cursor.execute("ALTER SESSION SET NLS_LANGUAGE='AMERICAN'")
            cursor.execute("ALTER SESSION SET NLS_DATE_FORMAT='YYYY-MM-DD HH24:MI:SS'")
            cursor.close()
            logger.debug("达梦数据库会话参数设置成功")
        except Exception as e:
            logger.warning(f"设置达梦会话参数失败: {e}")


def create_dm_engine() -> Optional[Engine]:
    """创建达梦数据库引擎"""
    if not DMDBConfig.validate_config():
        logger.error("数据库配置验证失败")
        return None

    try:
        # 构建数据库URL
        #database_url = DMDBConfig.get_sync_url()
        DATABASE_URL = "dm://SYSDBA:Dameng123@118.89.93.181:5236"

        sync_engine = create_engine(
            DATABASE_URL,
            echo=True,  # 开启 SQL 日志，可能会输出更多连接细节
            pool_size=10,
            max_overflow=5,
            pool_recycle=3600,
            pool_pre_ping=True
        )
        # 设置连接池事件
        setup_connection_pool(sync_engine)

        # 测试连接
        with sync_engine.connect() as conn:
            result = conn.execute(text("select username from dba_users"))
            print(result.scalar())

        logger.info("达梦数据库引擎创建成功")
        return sync_engine
    except Exception as e:
        print(f"连接失败：{e}")


# --------------------------
# 数据库引擎初始化
# --------------------------
sync_engine = create_dm_engine()

# --------------------------
# 同步会话工厂配置
# --------------------------
SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
    expire_on_commit=False  # 避免commit后属性访问问题
)

# --------------------------
# 基础模型类
# --------------------------
Base = declarative_base()

# --------------------------
# 数据库会话管理
# --------------------------
@contextmanager
def get_db() -> Generator[Session, None, None]:
    """数据库会话上下文管理器

    Usage:
        with get_db() as db:
            # 使用db进行数据库操作
            result = db.query(User).all()
    """
    if sync_engine is None:
        raise RuntimeError("数据库引擎未正确初始化，请检查数据库配置")

    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
        logger.debug("数据库事务提交成功")
    except Exception as e:
        db.rollback()
        logger.error(f"数据库操作失败，已回滚事务: {e}")
        raise
    finally:
        db.close()


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI依赖注入兼容版本

    Usage in FastAPI:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db_session)):
            return db.query(User).all()
    """
    if sync_engine is None:
        raise RuntimeError("数据库引擎未正确初始化")

    db = SyncSessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"数据库会话异常: {e}")
        raise
    finally:
        db.close()


# --------------------------
# 数据库工具函数
# --------------------------
def init_db() -> None:
    """初始化数据库表结构"""
    if sync_engine is None:
        logger.error("无法初始化数据库：引擎未创建")
        return

    try:
        Base.metadata.create_all(bind=sync_engine)
        logger.info("数据库表结构初始化成功")
    except Exception as e:
        logger.error(f"数据库表结构初始化失败: {e}")
        raise


def close_db_connection() -> None:
    """关闭数据库连接池"""
    global sync_engine
    if sync_engine:
        sync_engine.dispose()
        sync_engine = None
        logger.info("数据库连接池已关闭")


def check_db_health() -> bool:
    """检查数据库连接健康状态"""
    if sync_engine is None:
        logger.error("数据库引擎未初始化")
        return False

    try:
        with sync_engine.connect() as conn:
            result = conn.execute(text("select 1 from dba_users"))
            health_status = result.scalar() == 1
            if health_status:
                logger.debug("数据库健康检查通过")
            else:
                logger.warning("数据库健康检查未通过")
            return health_status
    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")
        return False


def get_db_info() -> dict:
    """获取数据库连接信息（隐藏密码）"""
    return {
        "host": DMDBConfig.HOST,
        "port": DMDBConfig.PORT,
        "user": DMDBConfig.USER,
        "pool_size": DMDBConfig.POOL_SIZE,
        "status": "connected" if sync_engine else "disconnected"
    }


# --------------------------
# 应用生命周期管理
# --------------------------
@contextmanager
def database_session():
    """应用级数据库会话管理"""
    try:
        logger.info("初始化数据库连接")
        if sync_engine is None:
            raise RuntimeError("数据库连接失败")

        yield sync_engine
    finally:
        logger.info("关闭数据库连接")
        close_db_connection()


# --------------------------
# 模块初始化检查
# --------------------------
if __name__ == "__main__":
    # 测试数据库连接
    print("=" * 50)
    print("达梦数据库配置测试")
    print("=" * 50)

    print(f"数据库配置: {get_db_info()}")

    if check_db_health():
        print("✅ 达梦数据库连接正常")
        # 初始化表结构（可选）
        try:
            init_db()
            print("✅ 数据库表结构初始化完成")
        except Exception as e:
            print(f"❌ 表结构初始化失败: {e}")
    else:
        print("❌ 达梦数据库连接失败")

    print("=" * 50)