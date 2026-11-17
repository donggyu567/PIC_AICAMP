"""서버를 중지한 뒤 운영자가 테스트 기기 토큰을 발급한다.

파일 잠금이 프로세스 내부에만 있으므로 실행 중인 서버와 동시에 사용하면 안 된다.
토큰은 안전한 경로로 전달한다.
"""

from server.security.access import device_store


if __name__ == "__main__":
    print(device_store.issue_device())
