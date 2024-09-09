from asyncmy import create_pool
from typing import Dict, Any, List, Tuple
from modules.crypto_utils import decrypt_password
import logging

logger = logging.getLogger(__name__)

# 기본 설정값
DEFAULT_POOL_SIZE = 1

class MySQLConnector:
    def __init__(self):
        self.pools: Dict[str, Any] = {}
        self.current_db: Dict[str, str] = {}

    async def create_pool(self, instance_info: Dict[str, Any], pool_size: int = DEFAULT_POOL_SIZE) -> None:
        """Create a connection pool for a MySQL instance."""
        try:
            instance_name = instance_info['instance_name']
            decrypted_password = decrypt_password(instance_info['password'])
            pool = await create_pool(
                host=instance_info['host'],
                port=instance_info['port'],
                user=instance_info['user'],
                password=decrypted_password,
                db=instance_info['db'],
                maxsize=pool_size
            )
            self.pools[instance_name] = pool
            self.current_db[instance_name] = instance_info['db']
            logger.info(f"Created MySQL connection pool for {instance_name} with max size {pool_size}")
        except Exception as e:
            logger.error(f"Error creating MySQL connection pool for {instance_info['instance_name']}: {str(e)}")
            raise

    async def set_database(self, instance_name: str, db_name: str) -> None:
        """Set the current database for a specific instance."""
        if instance_name not in self.pools:
            raise ValueError(f"No connection pool found for instance: {instance_name}")
        self.current_db[instance_name] = db_name
        logger.info(f"Set current database for {instance_name} to {db_name}")

    async def execute_query(self, instance_name: str, query: str, params: Tuple = None) -> List[Dict[str, Any]]:
        """Execute a query on the specified MySQL instance."""
        if instance_name not in self.pools:
            raise ValueError(f"No connection pool found for instance: {instance_name}")

        pool = self.pools[instance_name]
        try:
            async with pool.acquire() as conn:
                if instance_name in self.current_db:
                    await conn.select_db(self.current_db[instance_name])
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    columns = [column[0] for column in cursor.description]
                    return [dict(zip(columns, row)) for row in await cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error executing query on {instance_name}: {str(e)}")
            raise

    async def close_all_pools(self) -> None:
        """Close all connection pools."""
        for instance_name, pool in self.pools.items():
            pool.close()
            await pool.wait_closed()
            logger.info(f"Closed MySQL connection pool for {instance_name}")
        self.pools.clear()
        self.current_db.clear()

mysql_connector = MySQLConnector()