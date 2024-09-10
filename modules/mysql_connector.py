import asyncmy
import asyncmy.cursors
from asyncmy import create_pool
from typing import Dict, Any, List, Tuple
from modules.crypto_utils import decrypt_password
import logging

logger = logging.getLogger(__name__)

# 기본 설정값
DEFAULT_POOL_SIZE = 1

class MySQLConnector:
    def __init__(self, collector_name: str):
        self.collector_name = collector_name
        self.pools: Dict[str, Any] = {}

    async def create_pool(self, instance_info: Dict[str, Any], pool_size: int = DEFAULT_POOL_SIZE) -> None:
        """Create a connection pool for a MySQL instance."""
        try:
            decrypted_password = decrypt_password(instance_info['password'])
            self.pools[instance_info['instance_name']] = await create_pool(
                host=instance_info['host'],
                port=instance_info['port'],
                user=instance_info['user'],
                password=decrypted_password,
                db=instance_info['db'],
                maxsize=pool_size
            )
            logger.info(f"Created MySQL connection pool for {self.collector_name} - {instance_info['instance_name']} with max size {pool_size}")
        except Exception as e:
            logger.error(f"Error creating MySQL connection pool for {self.collector_name} - {instance_info['instance_name']}: {str(e)}")
            raise

    async def execute_query(self, instance_name: str, query: str, params: Tuple = None) -> List[Dict[str, Any]]:
        """Execute a query on the MySQL instance."""
        if instance_name not in self.pools:
            raise ValueError(f"No connection pool found for {instance_name} in {self.collector_name}")

        try:
            async with self.pools[instance_name].acquire() as conn:
                async with conn.cursor(asyncmy.cursors.DictCursor) as cursor:
                    await cursor.execute(query, params)
                    return await cursor.fetchall()
        except Exception as e:
            logger.error(f"Error executing query for {self.collector_name} - {instance_name}: {str(e)}")
            raise

    async def close_pool(self, instance_name: str) -> None:
        """Close the connection pool for a specific instance."""
        if instance_name not in self.pools:
            logger.warning(f"No connection pool found for {instance_name} in {self.collector_name}")
            return

        try:
            pool = self.pools[instance_name]
            pool.close()
            await pool.wait_closed()
            del self.pools[instance_name]
            logger.info(f"Closed MySQL connection pool for {self.collector_name} - {instance_name}")
        except Exception as e:
            logger.error(f"Error closing MySQL connection pool for {self.collector_name} - {instance_name}: {str(e)}")
            raise

    async def close_all_pools(self) -> None:
        """Close all connection pools for this collector."""
        for instance_name in list(self.pools.keys()):
            await self.close_pool(instance_name)

    async def set_database(self, instance_name: str, database: str) -> None:
        """Set the database for a specific instance."""
        if instance_name not in self.pools:
            raise ValueError(f"No connection pool found for {instance_name} in {self.collector_name}")

        try:
            async with self.pools[instance_name].acquire() as conn:
                await conn.select_db(database)
            logger.info(f"Set database to {database} for {self.collector_name} - {instance_name}")
        except Exception as e:
            logger.error(f"Error setting database for {self.collector_name} - {instance_name}: {str(e)}")
            raise

    async def execute_query_with_new_connection(self, connection_params: dict, query: str):
        try:
            # 비밀번호를 제외한 연결 정보 로깅
            safe_params = {k: v for k, v in connection_params.items() if k != 'password'}
            logger.info(f"Attempting to connect with parameters: {safe_params}")

            # 비밀번호 복호화
            if 'password' in connection_params:
                connection_params['password'] = decrypt_password(connection_params['password'])

            async with await asyncmy.connect(**connection_params) as connection:
                async with connection.cursor(asyncmy.cursors.DictCursor) as cursor:
                    await cursor.execute(query)
                    result = await cursor.fetchall()
                    return result
        except asyncmy.OperationalError as e:
            logger.error(f"MySQL Operational Error: {str(e)}")
            if "Access denied" in str(e):
                logger.error("This may be due to incorrect credentials or insufficient privileges.")
            raise
        except Exception as e:
            logger.error(f"Error executing query with new connection for {self.collector_name}: {str(e)}")
            logger.error(f"Query: {query}")
            raise

    @staticmethod
    async def test_connection(connection_params: dict) -> bool:
        try:
            # 비밀번호 복호화
            if 'password' in connection_params:
                connection_params['password'] = decrypt_password(connection_params['password'])

            async with await asyncmy.connect(**connection_params) as connection:
                await connection.ping()
            return True
        except Exception as e:
            logger.error(f"Error testing MySQL connection: {str(e)}")
            return False