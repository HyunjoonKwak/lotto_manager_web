#!/bin/bash
# Lotto Dashboard 실행 스크립트 (메뉴형)
# - 포그라운드 실행
# - 백그라운드 실행 (nohup, 로그 저장)
# - 상태 확인
# - 중지

set -e

ROOT_DIR="$(dirname "$(dirname "$0")")"
cd "$ROOT_DIR" || exit 1

PORT="${PORT:-8080}"
LOG_DIR="$ROOT_DIR/logs"
RUN_DIR="$ROOT_DIR/run"
PID_FILE="$RUN_DIR/server.pid"

mkdir -p "$LOG_DIR" "$RUN_DIR"

activate_venv() {
  if [ -d ".venv" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi
}

find_pids() {
  # 우선 pgrep 사용
  if command -v pgrep >/dev/null 2>&1; then
    pgrep -f "python .*app.py" || true
  else
    # BusyBox 환경용 대체
    ps aux | grep -E "python .*app.py" | grep -v grep | awk '{print $2}'
  fi
}

status() {
  echo "== 서버 상태 확인 =="
  PIDS="$(find_pids)"
  if [ -s "$PID_FILE" ]; then
    echo "PID 파일: $(cat "$PID_FILE")"
  fi
  if [ -n "$PIDS" ]; then
    echo "실행 중인 PID: $PIDS"
  else
    echo "실행 중인 서버 프로세스가 없습니다."
  fi
  # 포트 리스닝 확인 (가능하면)
  if command -v ss >/dev/null 2>&1; then
    echo
    echo "== 포트 리스닝 (:${PORT}) =="
    ss -tulnp 2>/dev/null | grep ":$PORT" || echo "$PORT 포트 리스닝 없음"
  elif command -v netstat >/dev/null 2>&1; then
    echo
    echo "== 포트 리스닝 (:${PORT}) =="
    netstat -tulnp 2>/dev/null | grep ":$PORT" || echo "$PORT 포트 리스닝 없음"
  fi
}

start_foreground() {
  echo "🚀 포그라운드 실행: http://<NAS-IP>:${PORT}"
  activate_venv
  export PORT
  python app.py
}

start_background() {
  TS="$(date +%Y%m%d_%H%M%S)"
  LOG_FILE="$LOG_DIR/server_${TS}.log"
  echo "🚀 백그라운드 실행: http://<NAS-IP>:${PORT}"
  echo "   로그: $LOG_FILE"
  activate_venv
  export PORT
  nohup python app.py >"$LOG_FILE" 2>&1 &
  PID=$!
  echo "$PID" > "$PID_FILE"
  disown || true
  echo "PID: $PID (저장: $PID_FILE)"
}

stop_server() {
  echo "🛑 서버 중지"
  KILLED=0
  if [ -s "$PID_FILE" ]; then
    PID_FROM_FILE="$(cat "$PID_FILE")"
    if kill -0 "$PID_FROM_FILE" 2>/dev/null; then
      kill "$PID_FROM_FILE" 2>/dev/null || true
      sleep 1
      if kill -0 "$PID_FROM_FILE" 2>/dev/null; then
        kill -9 "$PID_FROM_FILE" 2>/dev/null || true
      fi
      KILLED=1
      echo "PID 파일의 프로세스 종료: $PID_FROM_FILE"
    fi
    rm -f "$PID_FILE"
  fi

  # 혹시 남아있을 수 있는 프로세스 추가 종료
  PIDS="$(find_pids)"
  if [ -n "$PIDS" ]; then
    echo "$PIDS" | xargs -r kill 2>/dev/null || true
    sleep 1
    echo "$PIDS" | xargs -r kill -9 2>/dev/null || true
    KILLED=1
    echo "검색된 프로세스 종료: $PIDS"
  fi

  if [ "$KILLED" -eq 0 ]; then
    echo "종료할 프로세스가 없습니다."
  fi
}

menu() {
  echo "====================================="
  echo " Lotto Dashboard 서버 제어 메뉴"
  echo " ROOT : $ROOT_DIR"
  echo " PORT : $PORT"
  echo " LOG  : $LOG_DIR"
  echo " PID  : $PID_FILE"
  echo "====================================="
  echo " 1) 포그라운드 실행 (Ctrl+C로 종료)"
  echo " 2) 백그라운드 실행 (nohup)"
  echo " 3) 실행 상태 확인"
  echo " 4) 실행 중지"
  echo " 5) 종료"
  echo "-------------------------------------"
  read -rp "선택 번호 입력: " choice

  case "$choice" in
    1) start_foreground ;;
    2) start_background ;;
    3) status ;;
    4) stop_server ;;
    5) exit 0 ;;
    *) echo "잘못된 선택입니다." ;;
  esac
}

# 인자 기반 빠른 실행 (옵션형)
case "$1" in
  foreground) start_foreground ;;
  background) start_background ;;
  status) status ;;
  stop) stop_server ;;
  "" ) menu ;;
  * ) echo "사용법: $0 {foreground|background|status|stop}"; exit 1 ;;
esac
