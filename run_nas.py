#!/usr/bin/env python3
"""
NAS 환경에서 실행하기 위한 스크립트
외부 접속을 허용하고 8080 포트를 사용합니다.
"""

import os
import socket
import subprocess
import sys
import time

from run import main


def nas_main() -> None:
    """NAS 환경 전용 메인 함수"""
    print("NAS 환경에서 Flask 앱을 시작합니다...")
    print("NAS 서버가 http://0.0.0.0:8080에서 시작됩니다.")
    print("외부에서 접속하려면: http://[NAS_IP]:8080")

    # 원래 main 함수 호출
    main()


if __name__ == "__main__":
    nas_main()
