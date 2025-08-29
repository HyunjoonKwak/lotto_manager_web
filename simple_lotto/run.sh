#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/specialrisk_mac/code_work/NAS_CODE/simple_lotto"
VENV="$ROOT/.venv/bin"
APP="app.web:app"
PORT="${PORT:-8080}"
PIDFILE="$ROOT/app.pid"
LOGFILE="$ROOT/app.log"

cd "$ROOT"

ensure_venv() {
  if [ ! -x "$VENV/flask" ]; then
    echo "가상환경 또는 Flask가 없습니다. 먼저 패키지를 설치하세요."
    exit 1
  fi
}

is_running() {
  if [ -f "$PIDFILE" ]; then
    local pid
    pid=$(cat "$PIDFILE" 2>/dev/null || true)
    if [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
      return 0
    fi
  fi
  return 1
}

start() {
  ensure_venv
  if is_running; then
    echo "이미 실행 중입니다. (PID=$(cat "$PIDFILE"))"
    exit 0
  fi
  export FLASK_APP="$APP"
  source "$ROOT/.env" 2>/dev/null || true
  : "${PORT:=${PORT}}"
  echo "실행: 포트 $PORT, 로그 $LOGFILE"
  nohup "$VENV/flask" run --host=0.0.0.0 --port="$PORT" >> "$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
  sleep 1
  if is_running; then
    echo "시작 완료 (PID=$(cat "$PIDFILE"))"
  else
    echo "시작 실패. 로그를 확인하세요: $LOGFILE"
    exit 1
  fi
}

status() {
  if is_running; then
    echo "실행 중 (PID=$(cat "$PIDFILE"), 포트=$PORT)"
  else
    echo "실행 중 아님"
  fi
}

stop() {
  if is_running; then
    local pid
    pid=$(cat "$PIDFILE")
    echo "종료 중 (PID=$pid)"
    kill "$pid" || true
    # 최대 5초 대기 후 강제 종료
    for i in {1..5}; do
      if ps -p "$pid" > /dev/null 2>&1; then
        sleep 1
      else
        break
      fi
    done
    if ps -p "$pid" > /dev/null 2>&1; then
      echo "강제 종료(SIGKILL)"
      kill -9 "$pid" || true
    fi
    rm -f "$PIDFILE"
    echo "종료 완료"
  else
    echo "실행 중 아님"
  fi
}

restart() {
  stop || true
  start
}

logs() {
  echo "로그 tail: $LOGFILE (중지: Ctrl+C)"
  touch "$LOGFILE"
  tail -f "$LOGFILE"
}

case "${1:-}" in
  start) start ;;
  status) status ;;
  stop) stop ;;
  restart) restart ;;
  logs) logs ;;
  *)
    echo "사용법: $0 {start|status|stop|restart|logs}"
    exit 1
    ;;
esac
