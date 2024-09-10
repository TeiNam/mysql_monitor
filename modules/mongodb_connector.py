from motor.motor_asyncio import AsyncIOMotorClient
from configs.mongo_conf import MONGODB_URI, MONGODB_DB_NAME
import logging
import asyncio

logger = logging.getLogger(__name__)


class MongoDBConnector:
    _client = None
    _db = None

    @classmethod
    async def initialize(cls):
        if cls._client is None:
            await cls._connect()

    @classmethod
    async def get_database(cls):
        if cls._client is None or not await cls._is_connected():
            await cls._connect()
        return cls._db

    @classmethod
    async def reconnect(cls):
        await cls.close()
        await cls._connect()

    @classmethod
    async def close(cls):
        if cls._client:
            cls._client.close()
        cls._client = None
        cls._db = None

    @classmethod
    async def _connect(cls):
        try:
            cls._client = AsyncIOMotorClient(
                MONGODB_URI,
                tls=False,
                tlsAllowInvalidCertificates=True,
                tlsAllowInvalidHostnames=True,
                directConnection=False,
                serverSelectionTimeoutMS=5000
            )
            cls._db = cls._client[MONGODB_DB_NAME]
            await cls._client.admin.command('ping')
            logger.info("MongoDB에 성공적으로 연결되었습니다.")
        except Exception as e:
            cls._client = None
            cls._db = None
            logger.error(f"MongoDB 연결에 실패했습니다: {e}")

    @classmethod
    async def _is_connected(cls):
        try:
            await cls._client.admin.command('ping')
            return True
        except Exception:
            return False


# 사용 예시
async def example_usage():
    # 커넥터 초기화
    await MongoDBConnector.initialize()

    # 데이터베이스 가져오기
    db = await MongoDBConnector.get_database()

    # 컬렉션 선택
    collection = db.example_collection

    # 문서 삽입
    result = await collection.insert_one({"key": "value"})
    print(f"삽입된 문서 ID: {result.inserted_id}")

    # 문서 조회
    document = await collection.find_one({"key": "value"})
    print(f"조회된 문서: {document}")

    # 문서 업데이트
    update_result = await collection.update_one({"key": "value"}, {"$set": {"updated": True}})
    print(f"업데이트된 문서 수: {update_result.modified_count}")

    # 문서 삭제
    delete_result = await collection.delete_one({"key": "value"})
    print(f"삭제된 문서 수: {delete_result.deleted_count}")

    # 연결 종료
    await MongoDBConnector.close()


if __name__ == "__main__":
    asyncio.run(example_usage())