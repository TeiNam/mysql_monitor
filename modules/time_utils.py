from datetime import datetime, timezone, timedelta
from typing import Optional

# 상수 정의
KST = timezone(timedelta(hours=9))
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
KST_DATETIME_FORMAT = f"{DATETIME_FORMAT} KST"


def get_kst_time() -> str:
    """
    현재 시간을 KST로 반환합니다.

    :return: KST 형식의 현재 시간 문자열
    """
    utc_now = datetime.now(timezone.utc)
    return utc_now.astimezone(KST).strftime(KST_DATETIME_FORMAT)


def convert_utc_to_kst(utc_time: Optional[datetime]) -> Optional[datetime]:
    """
    UTC 시간을 KST로 변환합니다.

    :param utc_time: 변환할 UTC 시간
    :return: KST로 변환된 시간 또는 None (입력이 None인 경우)
    """
    if utc_time is None:
        return None
    return utc_time.replace(tzinfo=timezone.utc).astimezone(KST)


def parse_datetime(date_string: str) -> Optional[datetime]:
    """
    문자열을 datetime 객체로 파싱합니다.

    :param date_string: 파싱할 날짜 문자열 ("%Y-%m-%d %H:%M:%S" 형식)
    :return: 파싱된 datetime 객체 또는 None (파싱 실패 시)
    """
    try:
        return datetime.strptime(date_string, DATETIME_FORMAT)
    except ValueError:
        return None


def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """
    datetime 객체를 문자열로 포맷팅합니다.

    :param dt: 포맷팅할 datetime 객체
    :return: 포맷팅된 문자열 또는 None (입력이 None인 경우)
    """
    if dt is None:
        return None
    return dt.strftime(KST_DATETIME_FORMAT)


# 사용 예시
if __name__ == "__main__":
    print(f"현재 KST 시간: {get_kst_time()}")

    utc_now = datetime.now(timezone.utc)
    kst_time = convert_utc_to_kst(utc_now)
    print(f"UTC to KST: {format_datetime(kst_time)}")

    date_str = "2023-05-01 12:00:00"
    parsed_date = parse_datetime(date_str)
    if parsed_date:
        print(f"파싱된 날짜: {format_datetime(parsed_date)}")
    else:
        print("날짜 파싱 실패")