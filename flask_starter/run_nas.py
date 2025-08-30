#!/usr/bin/env python3
"""
NAS 환경에서 실행하기 위한 스크립트
외부 접속을 허용하고 8080 포트를 사용합니다.
"""

import os
os.environ['FLASK_ENV'] = 'nas'

from run import main

if __name__ == "__main__":
    main()
