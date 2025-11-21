"""
达梦数据库适配器
由于达梦数据库的特殊性，提供专门的适配器来处理连接和SQL语句
"""

# 标准库
import asyncio
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager
import logging

# 第三方库
import dmPython
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


import os



logger = logging.getLogger(__name__)


class DMDatabaseAdapter(object):
    """达梦数据库适配器"""

    def __init__(self)-> None:
        self.connection_pool = []
        self.pool_size = 10
        self.current_connections = 0
        self._lock = asyncio.Lock()

    def _create_connection(self) -> dmPython.Connection:
        """创建达梦数据库连接"""
        try:
            connection = dmPython.connect(
                server=os.getenv("DATABASE_HOST", "localhost"),
                port=os.getenv("DATABASE_PORT", "5236"),
                user=os.getenv("DATABASE_USER", "SYSDBA"),
                password=os.getenv("DATABASE_PASSWORD", "Dameng123"),
                autoCommit=False
            )
            logger.info("达梦数据库连接创建成功")
            return connection
        except Exception as e:
            logger.error(f"达梦数据库连接创建失败: {e}")
            raise

    async def _get_connection(self) -> dmPython.Connection:
        """从连接池获取连接"""
        async with self._lock:
            if self.connection_pool:
                return self.connection_pool.pop()

            if self.current_connections < self.pool_size:
                self.current_connections += 1
                return self._create_connection()

            # 如果连接池满了，等待一段时间后重试
            await asyncio.sleep(0.1)
            return await self._get_connection()

    async def _return_connection(self, connection: dmPython.Connection) -> None:
        """将连接返回到连接池"""
        async with self._lock:
            if len(self.connection_pool) < self.pool_size:
                self.connection_pool.append(connection)
            else:
                try:
                    connection.close()
                    self.current_connections -= 1
                except Exception as e:
                    logger.error(f"关闭达梦数据库连接失败: {e}")

    @asynccontextmanager
    async def get_connection(self) -> None:
        """获取数据库连接的上下文管理器"""
        connection = await self._get_connection()
        try:
            yield connection
        except Exception as e:
            try:
                connection.rollback()
            except:
                pass
            logger.error(f"数据库操作错误: {e}")
            raise
        finally:
            await self._return_connection(connection)

    async def execute_query(self, sql: str, params: Optional[tuple] = None) -> list[dict[str, Any]]:
        """执行查询语句"""
        async with self.get_connection() as conn:
            # 1. 获取游标需要 await
            cursor = conn.cursor()
            try:
                if params:
                    # 2. 执行SQL需要 await
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)

                # 获取列名（cursor.description 是属性，无需 await）
                columns = [desc[0] for desc in cursor.description] if cursor.description else []

                # 获取所有结果（fetchall 是异步方法，需要 await）
                rows = cursor.fetchall()

                # 转换为字典列表
                result = []
                for row in rows:
                    result.append(dict(zip(columns, row)))

                return result

            finally:
                # 4. 关闭游标需要 await
                cursor.close()

    async def execute_non_query(self, sql: str, params: Optional[tuple] = None) -> int:
        """执行非查询语句（INSERT, UPDATE, DELETE）"""
        async with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)

                conn.commit()
                return cursor.rowcount

            except Exception as e:
                conn.rollback()
                raise
            finally:
                cursor.close()

    async def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            result = await self.execute_query("SELECT 1 as test")
            return len(result) > 0 and result[0].get('TEST') == 1
        except Exception as e:
            logger.error(f"达梦数据库连接测试失败: {e}")
            return False

    async def close_all_connections(self)->None:
        """关闭所有连接"""
        async with self._lock:
            for connection in self.connection_pool:
                try:
                    connection.close()
                except:
                    pass
            self.connection_pool.clear()
            self.current_connections = 0
            logger.info("所有达梦数据库连接已关闭")


async def query_users()-> Optional[list[dict[str, Any]]]:
    # 假设 dm_adapter 已正确初始化
    dm_adapter = DMDatabaseAdapter()  # 你的数据库适配器实例化代码

    # 在异步函数内部使用 await 是合法的
    result = await dm_adapter.execute_query('select username from dba_users')
    return result


# 2. 在程序入口处，通过 asyncio 事件循环运行异步函数
if __name__ == "__main__":
    import asyncio

    # 用 asyncio.run() 启动事件循环并执行异步函数
    print(asyncio.run(query_users()))
