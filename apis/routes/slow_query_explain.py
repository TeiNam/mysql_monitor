import re
import sqlparse
import json
import logging
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from datetime import datetime, timezone, timedelta

from modules.mongodb_connector import MongoDBConnector
from modules.mysql_connector import MySQLConnector
from modules.load_instance import load_instances_from_mongodb
from configs.mongo_conf import mongo_settings

router = APIRouter(tags=["Query Tool"])

kst_delta = timedelta(hours=9)
logger = logging.getLogger(__name__)


class ExplainRequest(BaseModel):
    pid: int


class SQLQueryExecutor:
    @staticmethod
    def remove_sql_comments(sql_text):
        return re.sub(r'/\*.*?\*/', '', sql_text, flags=re.DOTALL)

    @staticmethod
    def validate_sql_query(sql_text):
        query_without_comments = SQLQueryExecutor.remove_sql_comments(sql_text).strip()
        if not query_without_comments.lower().startswith("select"):
            raise ValueError("SELECT 쿼리만 가능합니다.")
        if "into" in query_without_comments.lower().split("from")[0]:
            raise ValueError("SELECT ... INTO ... FROM 형태의 프로시저 쿼리는 실행할 수 없습니다.")
        return query_without_comments

    @staticmethod
    async def execute(mysql_connector, connection_params, sql_text):
        try:
            validated_sql = SQLQueryExecutor.validate_sql_query(sql_text)
            explain_query = f"EXPLAIN FORMAT=JSON {validated_sql}"

            execution_plan = await mysql_connector.execute_query_with_new_connection(connection_params, explain_query)
            if not execution_plan or 'EXPLAIN' not in execution_plan[0]:
                raise ValueError("EXPLAIN 결과가 예상된 형식이 아닙니다.")
            return json.loads(execution_plan[0]['EXPLAIN'])
        except Exception as e:
            logger.error(f"SQL 실행 중 오류 발생: {str(e)}")
            logger.error(f"쿼리: {explain_query}")
            raise HTTPException(status_code=500, detail=f"SQL 실행 중 오류 발생: {str(e)}")


class MarkdownGenerator:
    @staticmethod
    def generate(document):
        formatted_sql = sqlparse.format(document['sql_text'], reindent=True, keyword_case='upper')
        formatted_explain = json.dumps(document['explain_result'], indent=4, ensure_ascii=False)
        markdown_content = (
            f"### 인스턴스: {document['instance']}\n\n"
            f"- 데이터베이스: {document['db']}\n"
            f"- PID: {document['pid']}\n"
            f"- 사용자: {document.get('user', 'N/A')}\n"
            f"- 실행시간: {document['time']}\n\n"
            f"- SQL TEXT:\n```sql\n{formatted_sql}\n```\n\n"
            f"- Explain:\n```json\n{formatted_explain}\n```\n\n"
        )
        return markdown_content


@router.post("/explain")
async def execute_sql(request: ExplainRequest):
    pid = request.pid
    try:
        mongodb = await MongoDBConnector.get_database()
        slow_log_collection = mongodb[mongo_settings.MONGO_SLOW_LOG_COLLECTION]
        plan_collection = mongodb[mongo_settings.MONGO_SLOW_LOG_PLAN_COLLECTION]

        if not pid:
            raise HTTPException(status_code=422, detail="PID is required")
        document = await slow_log_collection.find_one({"pid": pid})
        if document is None:
            raise HTTPException(status_code=404, detail="해당 PID의 문서를 찾을 수 없습니다.")

        rds_instances = await load_instances_from_mongodb()
        rds_info = next((item for item in rds_instances if item["instance_name"] == document["instance"]), None)
        if not rds_info:
            raise HTTPException(status_code=400, detail="instance_name에 해당하는 RDS 인스턴스 정보를 찾을 수 없습니다.")

        connection_params = {
            "host": rds_info["host"],
            "port": rds_info["port"],
            "user": rds_info["user"],
            "password": rds_info["password"],  # MySQLConnector 내부에서 복호화됨
            "db": document["db"],
            "charset": 'utf8mb4'
        }

        mysql_connector = MySQLConnector("slow_query_explain")
        execution_plan = await SQLQueryExecutor.execute(mysql_connector, connection_params, document["sql_text"])

        query_plan_document = {
            "pid": pid,
            "instance": document["instance"],
            "db": document["db"],
            "user": document["user"],
            "time": document["time"],
            "sql_text": SQLQueryExecutor.remove_sql_comments(document["sql_text"]),
            "explain_result": execution_plan,
            "created_at": datetime.now(timezone.utc)
        }
        await plan_collection.update_one({"pid": pid}, {"$set": query_plan_document}, upsert=True)

        return {"message": "SQL 쿼리에 대한 EXPLAIN이 실행되었으며, 실행 계획이 저장되었습니다."}
    except Exception as e:
        logger.error(f"execute_sql 함수 실행 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"내부 서버 오류: {str(e)}")


@router.get("/download", response_class=Response)
async def download_markdown(pid: int = Query(...)):
    try:
        mongodb = await MongoDBConnector.get_database()
        plan_collection = mongodb[mongo_settings.MONGO_SLOW_LOG_PLAN_COLLECTION]

        cursor = plan_collection.find({"pid": pid})
        markdown_content = ""
        async for document in cursor:
            markdown_content += MarkdownGenerator.generate(document)

        if not markdown_content:
            raise HTTPException(status_code=404, detail="주어진 PID에 대한 기록을 찾을 수 없습니다.")

        filename = f"slowlog_pid_{pid}.md"
        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
        return Response(content=markdown_content.encode('utf-8'), media_type="text/markdown", headers=headers)
    except Exception as e:
        logger.error(f"download_markdown 함수 실행 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"내부 서버 오류: {str(e)}")


@router.get("/plans/")
async def get_items():
    try:
        mongodb = await MongoDBConnector.get_database()
        collection = mongodb[mongo_settings.MONGO_SLOW_LOG_PLAN_COLLECTION]
        items = []
        sort = [("_id", -1)]

        async for item in collection.find({}).sort(sort):
            if '_id' in item:
                del item['_id']
            if 'explain_result' in item:
                del item['explain_result']
            if 'created_at' in item:
                item['created_at'] = item['created_at'] + kst_delta
            items.append(item)

        return items
    except Exception as e:
        logger.error(f"get_items 함수 실행 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"내부 서버 오류: {str(e)}")