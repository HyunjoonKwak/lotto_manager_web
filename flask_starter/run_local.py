#!/usr/bin/env python3
"""
로컬 개발 환경에서 실행하기 위한 스크립트
로컬 접속만 허용하고 5000 포트를 사용합니다.
"""

import os
os.environ['FLASK_ENV'] = 'development'

from run import main

if __name__ == "__main__":
    main()
