import os
import socket
import subprocess
import sys
import time
from app import create_app
from app.config import config


def find_process_using_port(port: int) -> list:
    """포트를 사용하는 프로세스 찾기"""
    try:
        if sys.platform == "darwin":  # macOS
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split('\n')
        elif sys.platform.startswith("linux"):  # Linux
            result = subprocess.run(
                ["fuser", f"{port}/tcp"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split()
    except Exception:
        pass
    return []


def kill_processes(pids: list) -> bool:
    """프로세스들을 종료"""
    success = True
    for pid in pids:
        try:
            pid = pid.strip()
            if pid:
                subprocess.run(["kill", "-9", pid], check=True)
                print(f"프로세스 {pid} 종료됨")
        except subprocess.CalledProcessError:
            print(f"프로세스 {pid} 종료 실패")
            success = False
        except Exception as e:
            print(f"프로세스 {pid} 종료 중 오류: {e}")
            success = False
    return success


def is_port_in_use(host: str, port: int) -> bool:
    """포트가 사용 중인지 확인"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result == 0
    except Exception:
        return False


def handle_port_conflict(host: str, port: int) -> bool:
    """포트 충돌 해결"""
    if not is_port_in_use(host, port):
        return True

    print(f"포트 {port}이 이미 사용 중입니다.")

    # 포트를 사용하는 프로세스 찾기
    pids = find_process_using_port(port)

    if not pids:
        print("포트를 사용하는 프로세스를 찾을 수 없습니다.")
        # macOS AirPlay 서비스가 포트를 점유할 수 있음
        if sys.platform == "darwin" and port == 5000:
            print("macOS AirPlay 서비스가 포트 5000을 사용 중일 수 있습니다.")
            print("시스템 설정 > 일반 > AirDrop 및 Handoff > AirPlay 수신기를 비활성화하거나")
            print("다른 포트를 사용하는 것을 권장합니다.")
        return False

    print(f"포트 {port}을 사용하는 프로세스: {', '.join(pids)}")
    print("기존 프로세스를 종료합니다...")

    # 프로세스 종료
    if kill_processes(pids):
        # 잠시 대기 후 포트 상태 재확인
        time.sleep(2)  # 대기 시간 증가

        # 여러 번 확인 (일부 서비스가 재시작될 수 있음)
        for i in range(3):
            if not is_port_in_use(host, port):
                print(f"포트 {port} 해제 완료")
                return True
            if i < 2:
                print(f"포트 해제 대기 중... ({i+1}/3)")
                time.sleep(1)

        print(f"포트 {port} 해제 실패 - 서비스가 자동으로 재시작되었을 수 있습니다.")
        return False
    else:
        print("일부 프로세스 종료에 실패했습니다.")
        return False


def find_available_port(host: str, start_port: int, max_attempts: int = 10) -> int:
    """사용 가능한 포트 찾기"""
    for port in range(start_port, start_port + max_attempts):
        if not is_port_in_use(host, port):
            return port
    raise RuntimeError(f"포트 {start_port}-{start_port + max_attempts - 1} 범위에서 사용 가능한 포트를 찾을 수 없습니다.")


def main() -> None:
    # 환경 변수로 설정 선택 (기본값: development)
    env = os.environ.get('FLASK_ENV', 'development')
    config_class = config.get(env, config['default'])

    app = create_app(config_class)

    # 설정에서 host와 port 가져기
    host = getattr(config_class, 'HOST', '127.0.0.1')
    original_port = getattr(config_class, 'PORT', 5000)
    debug = getattr(config_class, 'DEBUG', True)

    print(f"Starting Flask app in {env} mode")
    print(f"Debug mode: {debug}")

    # Flask reloader 재시작 시에는 포트 충돌 검사를 건너뛰기
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'

    port = original_port
    if not is_reloader_process:
        # 최초 실행 시에만 포트 충돌 확인 및 해결
        if not handle_port_conflict(host, port):
            print(f"포트 {port}를 해제할 수 없습니다. 다른 포트를 찾고 있습니다...")
            try:
                port = find_available_port(host, original_port + 1)
                print(f"사용 가능한 포트 {port}를 찾았습니다.")
                # 찾은 포트를 환경변수로 설정하여 reloader 프로세스에서도 사용
                os.environ['FLASK_PORT_OVERRIDE'] = str(port)
            except RuntimeError as e:
                print(f"오류: {e}")
                sys.exit(1)
    else:
        # reloader 프로세스에서는 저장된 포트 사용
        if 'FLASK_PORT_OVERRIDE' in os.environ:
            port = int(os.environ['FLASK_PORT_OVERRIDE'])

    print(f"Server will be available at: http://{host}:{port}")

    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
