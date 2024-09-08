import requests
from configs.slack_conf import SLACK_API_TOKEN, SLACK_WEBHOOK_URL, HOST
from configs.log_conf import setup_logging
import logging

setup_logging()

def get_slack_user_id(email: str) -> str:
    """
    이메일을 사용하여 Slack 사용자 ID를 조회합니다.

    :param email: 사용자 이메일
    :return: Slack 사용자 ID 또는 None (사용자를 찾지 못한 경우)
    """
    headers = {
        'Authorization': f'Bearer {SLACK_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    response = requests.get(f'https://slack.com/api/users.lookupByEmail?email={email}', headers=headers, verify=False)
    if response.status_code == 200 and response.json()['ok']:
        return response.json()['user']['id']
    logging.error(f"Slack 사용자 ID 조회 실패: {email}")
    return None

def send_slack_notification(user_email: str, title: str, instance_info: str, db_info: str, pid_info: str, execution_time: float):
    """
    Slack으로 SQL 쿼리 실행 알림을 보냅니다.

    :param user_email: 사용자 이메일
    :param title: 알림 제목
    :param instance_info: 인스턴스 정보
    :param db_info: 데이터베이스 정보
    :param pid_info: 프로세스 ID 정보
    :param execution_time: 쿼리 실행 시간 (초)
    """
    user_id = get_slack_user_id(user_email)
    if user_id is None:
        raise ValueError(f"Slack에서 사용자를 찾을 수 없습니다: {user_email}")

    formatted_message = (
        f'*{title}*\n'
        f'<@{user_id}> 계정으로 실행한 SQL쿼리(PID: {pid_info})가\n'
        f'*{instance_info}*, *{db_info}* DB에서 *{execution_time}* 초 동안 실행 되었습니다.\n'
        f'쿼리 검수 및 실행 시 주의가 필요합니다.\n'
        f'http://{HOST}:8000/sql-plan?pid={pid_info}'
    )

    payload = {'text': formatted_message}
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)

    if response.status_code != 200:
        error_message = f"Slack 알림 전송 실패. 상태 코드: {response.status_code}, 응답: {response.text}"
        logging.error(error_message)
        raise ValueError(error_message)

    logging.info(f"Slack 알림 전송 성공: {user_email}")

# 사용 예시
if __name__ == "__main__":
    try:
        send_slack_notification(
            user_email="example@example.com",
            title="SQL 쿼리 실행 알림",
            instance_info="Production Server",
            db_info="Main Database",
            pid_info="12345",
            execution_time=10.5
        )
    except ValueError as e:
        logging.error(f"Slack 알림 전송 중 오류 발생: {e}")