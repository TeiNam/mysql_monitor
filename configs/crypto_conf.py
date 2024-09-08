import os
import base64
from dotenv import load_dotenv
from cryptography.hazmat.primitives.ciphers import algorithms
import secrets

# 환경 변수 로드
load_dotenv()

# 상수 정의
AES_KEY_LENGTH = 32
AES_IV_LENGTH = 16


def generate_key(length):
    """지정된 길이의 랜덤 바이트 문자열을 생성하고 base64로 인코딩합니다."""
    return base64.urlsafe_b64encode(secrets.token_bytes(length)).decode()


def get_or_generate_key(key_name, length):
    """환경 변수에서 키를 가져오거나, 없으면 새로 생성합니다."""
    key = os.getenv(key_name)
    if not key:
        key = generate_key(length)
        print(f"Warning: {key_name} not found in .env. A new one has been generated.")
        print(f"Please add the following line to your .env file:")
        print(f"{key_name}={key}")
    return base64.urlsafe_b64decode(key)


# AES 키와 IV 로드 또는 생성
AES_KEY = get_or_generate_key("AES_KEY", AES_KEY_LENGTH)
AES_IV = get_or_generate_key("AES_IV", AES_IV_LENGTH)


# 키 길이 검증
if len(AES_KEY) != AES_KEY_LENGTH:
    raise ValueError(f"AES_KEY must be {AES_KEY_LENGTH} bytes long.")
if len(AES_IV) != AES_IV_LENGTH:
    raise ValueError(f"AES_IV must be {AES_IV_LENGTH} bytes long.")


# 키 생성 도구
def generate_new_keys():
    """새로운 AES 키와 IV를 생성하고 출력합니다."""
    new_aes_key = generate_key(AES_KEY_LENGTH)
    new_aes_iv = generate_key(AES_IV_LENGTH)
    print("New AES key and IV generated:")
    print(f"AES_KEY={new_aes_key}")
    print(f"AES_IV={new_aes_iv}")
    print("Please update these values in your .env file.")


if __name__ == "__main__":
    generate_new_keys()