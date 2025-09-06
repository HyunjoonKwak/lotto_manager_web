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

os.environ['FLASK_ENV'] = 'nas'

from run import main, find_process_using_port, kill_processes, is_port_in_use, handle_port_conflict, find_available_port


def nas_main() -> None:
    """NAS 환경 전용 메인 함수"""
    print("NAS 환경에서 Flask 앱을 시작합니다...")

    # NAS 환경 설정
    host = "0.0.0.0"
    port = 8080

    # Flask reloader 재시작 시에는 포트 충돌 검사를 건너뛰기
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'

    if not is_reloader_process:
        print(f"포트 {port} 사용 가능 여부를 확인합니다...")

        # 포트 충돌 확인 및 해결
        if not handle_port_conflict(host, port):
            print(f"포트 {port}를 해제할 수 없습니다. 다른 포트를 찾고 있습니다...")
            try:
                port = find_available_port(host, port + 1)
                print(f"사용 가능한 포트 {port}를 찾았습니다.")
                # 찾은 포트를 환경변수로 설정
                os.environ['FLASK_PORT_OVERRIDE'] = str(port)
            except RuntimeError as e:
                print(f"오류: {e}")
                sys.exit(1)
    else:
        # reloader 프로세스에서는 저장된 포트 사용
        if 'FLASK_PORT_OVERRIDE' in os.environ:
            port = int(os.environ['FLASK_PORT_OVERRIDE'])
            print(f"Reloader: 포트 {port}를 사용합니다.")

    print(f"NAS 서버가 http://0.0.0.0:{port}에서 시작됩니다.")
    print("외부에서 접속하려면: http://[NAS_IP]:{port}")

    # 원래 main 함수 호출
    main()


if __name__ == "__main__":
    nas_main()
