# -*- coding: utf-8 -*-
"""达梦数据库配置模块"""
import os
from typing import Generator, AsyncIterator
from contextlib import asynccontextmanager

# 达梦数据库驱动
import dmPython
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 基础模型类（所有数据库模型继承此类）
Base = declarative_base()


class DMDatabaseConfig(object):
    """达梦数据库配置类，负责解析环境变量并生成连接URL"""

    def __init__(self) -> None:
        # 从环境变量读取达梦数据库配置，提供默认值
        self.dm_host = os.getenv("DATABASE_HOST", "localhost")
        self.dm_port = os.getenv("DATABASE_PORT", "5236")
        self.dm_user = os.getenv("DATABASE_USER", "SYSDBA")
        self.dm_password = os.getenv("DATABASE_PASSWORD", "Dameng123")
        self.dm_database = os.getenv("DATABASE_NAME", "DMDB")

        # 达梦数据库连接URL格式
        # 同步连接使用 dmPython 驱动
        self.sync_url = (
            f"dm+dmPython://{self.dm_user}:{self.dm_password}"
            f"@{self.dm_host}:{self.dm_port}"
        )

        # 异步连接URL（注意：达梦官方对异步支持有限，这里使用兼容格式）
        self.async_url = (
            f"dm+dmPython://{self.dm_user}:{self.dm_password}"
            f"@{self.dm_host}:{self.dm_port}"
        )

    def validate_connection(self) -> bool:
        """验证达梦数据库连接配置"""
        try:
            # 使用dmPython直接测试连接
            conn = dmPython.connect(
                user=self.dm_user,
                password=self.dm_password,
                server=self.dm_host,
                port=int(self.dm_port),
                autoCommit=True
            )
            conn.close()
            return True
        except Exception as e:
            print(f"达梦数据库连接测试失败: {e}")
            return False


class DMDatabaseSessionManager(object):
    """达梦数据库会话管理器，封装同步/异步引擎与会话创建逻辑"""

    def __init__(self, config: DMDatabaseConfig) -> None:
        self.config = config

        # 验证连接配置
        if not self.config.validate_connection():
            raise ConnectionError("达梦数据库连接配置验证失败")

        # ========== 同步引擎与会话工厂 ==========
        self.sync_engine = create_engine(
            self.config.sync_url,
            echo=True,  # 开发环境可以设为True查看SQL日志
            pool_pre_ping=True,  # 连接有效性检查
            pool_size=50,  # 连接池大小
            max_overflow=30,  # 最大溢出连接数
            pool_timeout=5,
            pool_recycle=3600,  # 连接回收时间(秒)
            connect_args={
                'autoCommit': False,  # 手动控制事务
            }
        )
        self.sync_session_factory = sessionmaker(
            bind=self.sync_engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False  # 达梦数据库建议设置
        )

        # ========== 异步引擎与会话工厂 ==========
        # 注意：达梦数据库对异步支持有限，这里提供基本实现
        try:
            self.async_engine = create_async_engine(
                self.config.async_url,
                echo=True,
                pool_size=5,  # 异步连接池较小
                max_overflow=10,
                pool_recycle=3600,
                pool_pre_ping=True
            )
            self.async_session_factory = async_sessionmaker(
                bind=self.async_engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
                class_=AsyncSession
            )
        except Exception as e:
            print(f"达梦异步引擎初始化警告: {e}")
            print("异步功能可能受限，建议使用同步连接")
            self.async_engine = None
            self.async_session_factory = None

    # ------------------------------ 同步会话管理 ------------------------------
    def get_sync_session(self) -> Generator[Session, None, None]:
        """同步会话依赖注入生成器（用于非异步路由）"""
        session = self.sync_session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    # ------------------------------ 异步会话管理 ------------------------------
    @asynccontextmanager
    async def safe_async_session(self) -> AsyncIterator[AsyncSession]:
        """安全的异步会话上下文管理器，自动处理提交/回滚/关闭"""
        if not self.async_session_factory:
            raise RuntimeError("达梦数据库异步会话未正确初始化")

        session: AsyncSession = self.async_session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def get_async_session(self) -> AsyncIterator[AsyncSession]:
        """异步会话依赖注入生成器（用于异步路由）"""
        async with self.safe_async_session() as session:
            yield session

    # ------------------------------ 数据库工具方法 ------------------------------
    def create_tables(self):
        """创建所有表结构"""
        Base.metadata.create_all(bind=self.sync_engine)
        print("达梦数据库表结构创建完成")

    def drop_tables(self):
        """删除所有表结构（谨慎使用）"""
        Base.metadata.drop_all(bind=self.sync_engine)
        print("达梦数据库表结构删除完成")

    def check_connection(self) -> bool:
        """检查数据库连接状态"""
        try:
            with self.sync_engine.connect() as conn:
                result = conn.execute(text("SELECT 1 FROM DUAL"))
                return result.scalar() == 1
        except Exception as e:
            print(f"达梦数据库连接检查失败: {e}")
            return False

    def get_database_info(self) -> dict:
        """获取数据库连接信息"""
        return {
            "host": self.config.dm_host,
            "port": self.config.dm_port,
            "user": self.config.dm_user,
            "database": self.config.dm_database,
            "status": "connected" if self.check_connection() else "disconnected",
            "async_support": self.async_engine is not None
        }


# 单例实例化（项目中全局使用一个管理器）
dm_db_config = DMDatabaseConfig()
dm_db_manager = DMDatabaseSessionManager(dm_db_config)

# 对外暴露的依赖注入函数（与FastAPI路由配合使用）
get_db = dm_db_manager.get_sync_session  # 同步会话依赖
get_async_db = dm_db_manager.get_async_session  # 异步会话依赖

# 使用示例和测试代码
if __name__ == "__main__":
    print("=" * 50)
    print("达梦数据库配置测试")
    print("=" * 50)

    # 显示数据库信息
    db_info = dm_db_manager.get_database_info()
    print(f"数据库连接信息: {db_info}")

    # 测试连接
    if dm_db_manager.check_connection():
        print("✅ 达梦数据库连接正常")

        # 测试基本查询
        try:
            with dm_db_manager.sync_engine.connect() as conn:
                # 查询达梦数据库版本
                result = conn.execute(text("SELECT * FROM V$VERSION"))
                version_info = result.fetchone()
                print(f"✅ 达梦数据库版本: {version_info[0] if version_info else '未知'}")

                # 查询当前用户
                result = conn.execute(text("SELECT USER FROM DUAL"))
                current_user = result.scalar()
                print(f"✅ 当前数据库用户: {current_user}")

        except Exception as e:
            print(f"❌ 数据库查询测试失败: {e}")
    else:
        print("❌ 达梦数据库连接失败")

    print("=" * 50)
