import requests
from configs.slack_conf import SLACK_WEBHOOK_URL
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def send_slack_notification(header: str, body: Dict[str, Any], footer: str = None):
    """
    Slack으로 유연한 형식의 알림을 보냅니다.

    :param header: 알림의 헤더 (제목)
    :param body: 알림의 본문 (딕셔너리 형태)
    :param footer: 알림의 푸터 (선택적)
    """
    formatted_message = f"*{header}*\n\n"

    for key, value in body.items():
        formatted_message += f"*{key}*: {value}\n"

    if footer:
        formatted_message += f"\n{footer}"

    payload = {'text': formatted_message}
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)

    if response.status_code != 200:
        error_message = f"Slack 알림 전송 실패. 상태 코드: {response.status_code}, 응답: {response.text}"
        logger.error(error_message)
        raise ValueError(error_message)

    logger.info(f"Slack 알림 전송 성공: {header}")


# 사용 예시
if __name__ == "__main__":
    try:
        # 시스템 상태 알림 예시
        send_slack_notification(
            header="DB 슬랙 봇 테스트",
            body={
                "상태": "정상",
                "CPU 사용률": "65%",
                "메모리 사용률": "80%",
                "디스크 공간": "500GB 남음"
            },
            footer="자세한 내용은 대시보드를 확인해주세요."
        )

        # 보안 알림 예시
        send_slack_notification(
            header="보안 경고",
            body={
                "이벤트 유형": "무단 접근 시도",
                "IP 주소": "192.168.1.100",
                "시도 횟수": "5회",
                "시간": "2023-10-21 15:30:00"
            },
            footer="즉시 보안 팀에 보고해주세요."
        )

    except ValueError as e:
        logger.error(f"Slack 알림 전송 중 오류 발생: {e}")