#!/usr/bin/env bash
# Lotto Dashboard 실행 스크립트 (메뉴형) - macOS 친화 패치
set -euo pipefail

# --- 스크립트 경로/루트 계산(어떤 방식으로 실행해도 안전) ---
SCRIPT_FILE="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_FILE")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-8080}"
LOG_DIR="$ROOT_DIR/logs"
RUN_DIR="$ROOT_DIR/run"
PID_FILE="$RUN_DIR/server.pid"

mkdir -p "$LOG_DIR" "$RUN_DIR"

# --- 파이썬 실행기 선택(.venv 우선) ---
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
else
  PYTHON="$(command -v python3 || command -v python)"
fi

activate_venv() {
  if [[ -d ".venv" ]]; then
    # shellcheck disable=SC1091
    source ".venv/bin/activate"
  fi
}

find_pids() {
  # app.py 또는 wsgi.py로 실행된 Flask/Werkzeug까지 포착
  if command -v pgrep >/dev/null 2>&1; then
    pgrep -f "$PYTHON .*app.py|$PYTHON .*wsgi.py" || true
  else
    ps aux | grep -E "$PYTHON .*app.py|$PYTHON .*wsgi.py" | grep -v grep | awk '{print $2}'
  fi
}

status() {
  echo "== 서버 상태 확인 =="
  local PIDS
  PIDS="$(find_pids || true)"
  if [[ -s "$PID_FILE" ]]; then
    echo "PID 파일: $(cat "$PID_FILE")"
  fi
  if [[ -n "${PIDS:-}" ]]; then
    echo "실행 중인 PID: $PIDS"
  else
    echo "실행 중인 서버 프로세스가 없습니다."
  fi

  echo
  echo "== 포트 리스닝 (:${PORT}) =="
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$PORT" -sTCP:LISTEN || echo "$PORT 포트 리스닝 없음"
  elif command -v netstat >/dev/null 2>&1; then
    # macOS netstat에는 -p 옵션이 없습니다.
    netstat -an | grep "\.$PORT " || echo "$PORT 포트 리스닝 없음"
  else
    echo "lsof/netstat 없음 - 포트 확인 불가"
  fi
}

start_foreground() {
  echo "🚀 포그라운드 실행: http://localhost:${PORT}"
  activate_venv
  export PORT
  # SIGINT/SIGTERM 전달을 위해 exec 사용
  exec "$PYTHON" app.py
}

start_background() {
  local TS LOG_FILE
  TS="$(date +%Y%m%d_%H%M%S)"
  LOG_FILE="$LOG_DIR/server_${TS}.log"
  echo "🚀 백그라운드 실행: http://localhost:${PORT}"
  echo "   로그: $LOG_FILE"
  activate_venv
  export PORT
  nohup "$PYTHON" app.py >"$LOG_FILE" 2>&1 &
  local PID=$!
  echo "$PID" > "$PID_FILE"
  disown || true
  echo "PID: $PID (저장: $PID_FILE)"
}

stop_server() {
  echo "🛑 서버 중지"
  local KILLED=0

  if [[ -s "$PID_FILE" ]]; then
    local PID_FROM_FILE
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

  local PIDS
  PIDS="$(find_pids || true)"
  if [[ -n "${PIDS:-}" ]]; then
    echo "$PIDS" | xargs -r kill 2>/dev/null || true
    sleep 1
    echo "$PIDS" | xargs -r kill -9 2>/dev/null || true
    KILLED=1
    echo "검색된 프로세스 종료: $PIDS"
  fi

  if [[ "$KILLED" -eq 0 ]]; then
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
  echo " PY   : $PYTHON"
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

case "${1:-}" in
  foreground) start_foreground ;;
  background) start_background ;;
  status) status ;;
  stop) stop_server ;;
  "" ) menu ;;
  * ) echo "사용법: $0 {foreground|background|status|stop}"; exit 1 ;;
esac
