from asyncmy import create_pool
from typing import Dict, Any, List, Tuple
from modules.crypto_utils import decrypt_password
import logging

logger = logging.getLogger(__name__)

# 기본 설정값
DEFAULT_POOL_SIZE = 3

class MySQLConnector:
    def __init__(self, collector_name: str):
        self.collector_name = collector_name
        self.pools: Dict[str, Any] = {}

    async def create_pool(self, instance_info: Dict[str, Any], pool_size: int = DEFAULT_POOL_SIZE) -> None:
        """Create a connection pool for a MySQL instance."""
        try:
            decrypted_password = decrypt_password(instance_info['password'])
            self.pool = await create_pool(
                host=instance_info['host'],
                port=instance_info['port'],
                user=instance_info['user'],
                password=decrypted_password,
                db=instance_info['db'],
                maxsize=pool_size
            )
            logger.info(f"Created MySQL connection pool for {self.collector_name} with max size {pool_size}")
        except Exception as e:
            logger.error(f"Error creating MySQL connection pool for {self.collector_name}: {str(e)}")
            raise

    async def execute_query(self, query: str, params: Tuple = None) -> List[Dict[str, Any]]:
        """Execute a query on the MySQL instance."""
        if not self.pool:
            raise ValueError(f"No connection pool found for {self.collector_name}")

        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    columns = [column[0] for column in cursor.description]
                    return [dict(zip(columns, row)) for row in await cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error executing query for {self.collector_name}: {str(e)}")
            raise

    async def close_pool(self) -> None:
        """Close the connection pool for this collector."""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info(f"Closed MySQL connection pool for {self.collector_name}")

    async def set_database(self, instance_name: str, database: str) -> None:
        """Set the database for a specific instance."""
        if instance_name not in self.pools:
            raise ValueError(f"No connection pool found for {instance_name} in {self.collector_name}")

        try:
            pool = self.pools[instance_name]
            async with pool.acquire() as conn:
                await conn.select_db(database)
            logger.info(f"Set database to {database} for {self.collector_name} - {instance_name}")
        except Exception as e:
            logger.error(f"Error setting database for {self.collector_name} - {instance_name}: {str(e)}")
            raise

    async def execute_query_with_new_connection(self, instance_info: Dict[str, Any], database: str, query: str,
                                                params: Tuple = None) -> List[Dict[str, Any]]:
        """Create a new connection, execute a query, and close the connection."""
        try:
            decrypted_password = decrypt_password(instance_info['password'])
            async with await create_pool(
                    host=instance_info['host'],
                    port=instance_info['port'],
                    user=instance_info['user'],
                    password=decrypted_password,
                    db=database,
                    maxsize=1
            ) as pool:
                async with pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(query, params)
                        columns = [column[0] for column in cursor.description]
                        return [dict(zip(columns, row)) for row in await cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error executing query with new connection for {self.collector_name}: {str(e)}")
            raise