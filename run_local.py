#!/usr/bin/env python3
"""
로컬 개발 환경에서 실행하기 위한 스크립트
로컬 접속만 허용하고 5001 포트를 사용합니다.
"""

import os
import socket
import subprocess
import sys
import time

os.environ['FLASK_ENV'] = 'development'

from run import main


def local_main() -> None:
    """로컬 개발 환경 전용 메인 함수"""
    print("로컬 개발 환경에서 Flask 앱을 시작합니다...")
    print("로컬 서버가 http://127.0.0.1:5001에서 시작됩니다.")
    print("브라우저에서 접속하세요!")

    # 원래 main 함수 호출
    main()


if __name__ == "__main__":
    local_main()
