#!/usr/bin/env bash
set -euo pipefail

# ===== 기본 경로/설정 =====
ROOT="/volume1/code_work/lotto_app"
APP="app.web:app"
PIDFILE="$ROOT/app.pid"
LOGFILE="$ROOT/app.log"
PORT_DEFAULT=8080

cd "$ROOT"

# .env에서 PORT만 안전하게 읽기
if [ -f "$ROOT/.env" ]; then
  ENV_PORT=$(grep -E '^PORT=' "$ROOT/.env" | tail -n1 | cut -d'=' -f2- || true)
  PORT="${ENV_PORT:-$PORT_DEFAULT}"
else
  PORT="$PORT_DEFAULT"
fi

VENV="$ROOT/.venv/bin"
FLASK="$VENV/flask"
PYTHON="$VENV/python"

# ===== 색상 출력 =====
color() { printf "\033[%sm%s\033[0m" "$1" "$2"; }
green() { color "32" "$1"; }
red()   { color "31" "$1"; }
yellow(){ color "33" "$1"; }
cyan()  { color "36" "$1"; }

# ===== 헬퍼 =====
need_venv() {
  if [ ! -x "$FLASK" ] || [ ! -x "$PYTHON" ]; then
    echo "$(red '[오류]') 가상환경/플라스크 실행 파일을 찾지 못했습니다: $VENV"
    echo "pip install -r requirements.txt 로 패키지 설치를 확인하세요."
    exit 1
  fi
}

# 8080 점유 PID 찾기: PIDFILE 우선, 없으면 netstat/ss
find_pid_by_port() {
  # 1) PIDFILE
  if [ -f "$PIDFILE" ]; then
    local p
    p=$(cat "$PIDFILE" 2>/dev/null || true)
    if [ -n "${p:-}" ] && ps -p "$p" > /dev/null 2>&1; then
      echo "$p"; return 0
    fi
  fi
  # 2) netstat
  if command -v netstat >/dev/null 2>&1; then
    local p
    p=$(netstat -tnlp 2>/dev/null | grep ":${PORT} " | awk '{print $7}' | cut -d'/' -f1 | head -n1 || true)
    if [ -n "${p:-}" ]; then echo "$p"; return 0; fi
  fi
  # 3) ss
  if command -v ss >/dev/null 2>&1; then
    local p
    p=$(ss -ltnp 2>/dev/null | grep ":${PORT} " | awk '{print $NF}' | sed 's/.*pid=\([0-9]\+\).*/\1/' | head -n1 || true)
    if [ -n "${p:-}" ]; then echo "$p"; return 0; fi
  fi
  return 1
}

is_running() {
  if pid=$(find_pid_by_port); then
    echo "$pid"; return 0
  fi
  return 1
}

# ===== 동작들 =====
start_bg() {
  need_venv
  if is_running >/dev/null; then
    local pid; pid=$(is_running)
    echo "$(yellow '[안내]') 이미 실행 중입니다. PID=${pid}, 포트=${PORT}"
    return 0
  fi
  export FLASK_APP="$APP"
  echo "$(cyan '[시작-BG]') 포트 ${PORT}, 로그 ${LOGFILE}"
  nohup "$FLASK" run --host=0.0.0.0 --port="$PORT" >> "$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
  sleep 1
  if is_running >/dev/null; then
    echo "$(green '[성공]') 백그라운드 시작 완료 (PID=$(cat "$PIDFILE"))"
  else
    echo "$(red '[실패]') 시작 실패. 로그 확인: $LOGFILE"
    exit 1
  fi
}

start_fg() {
  need_venv
  if is_running >/dev/null; then
    local pid; pid=$(is_running)
    echo "$(yellow '[안내]') 이미 실행 중입니다. PID=${pid}, 포트=${PORT}"
    echo "$(yellow '[안내]') 포그라운드로 다시 띄우려면 먼저 stop/kill 하세요."
    return 0
  fi
  export FLASK_APP="$APP"
  echo "$(cyan '[시작-FG]') 포트 ${PORT} (Ctrl+C로 종료). 로그는 표준출력에 표시됩니다."
  # PIDFILE은 생성하지 않음(포그라운드)
  exec "$FLASK" run --host=0.0.0.0 --port="$PORT"
}

stop_app_soft() {
  if is_running >/dev/null; then
    local pid; pid=$(is_running)
    echo "$(cyan '[종료]') 안전 종료 시도 (PID=$pid)"
    kill "$pid" || true
    for _ in 1 2 3 4 5; do
      if ps -p "$pid" > /dev/null 2>&1; then sleep 1; else break; fi
    done
    if ps -p "$pid" > /dev/null 2>&1; then
      echo "$(yellow '[경고]') 아직 내려가지 않았습니다. 강제 종료(kill)를 사용하세요."
    else
      rm -f "$PIDFILE"
      echo "$(green '[완료]') 안전 종료"
    fi
  else
    echo "$(yellow '[안내]') 실행 중인 앱이 없습니다."
  fi
}

stop_app_hard() {
  local killed=false
  if is_running >/dev/null; then
    local pid; pid=$(is_running)
    echo "$(red '[강제 종료]') SIGKILL (PID=$pid)"
    kill -9 "$pid" || true
    killed=true
  fi
  # 혹시 남은 포트 점유 프로세스도 마무리
  if command -v netstat >/dev/null 2>&1; then
    pids=$(netstat -tnlp 2>/dev/null | grep ":${PORT} " | awk '{print $7}' | cut -d'/' -f1 | xargs -r echo || true)
    [ -n "${pids:-}" ] && kill -9 $pids || true
  elif command -v ss >/dev/null 2>&1; then
    pids=$(ss -ltnp 2>/dev/null | grep ":${PORT} " | sed 's/.*pid=\([0-9]\+\).*/\1/' | xargs -r echo || true)
    [ -n "${pids:-}" ] && kill -9 $pids || true
  fi
  rm -f "$PIDFILE"
  $killed && echo "$(green '[완료]') 강제 종료" || echo "$(yellow '[안내]') 종료할 프로세스가 없습니다."
}

status_app() {
  if is_running >/dev/null; then
    local pid; pid=$(is_running)
    echo "$(green '[실행 중]') PID=${pid}, 포트=${PORT}"
  else
    echo "$(red '[중지]') 앱이 실행 중이 아닙니다."
  fi
  # 간단 헬스체크
  if command -v curl >/dev/null 2>&1; then
    if curl -m 2 -fsS "http://127.0.0.1:${PORT}/api/draws?limit=1" >/dev/null; then
      echo "$(green '[헬스체크]') OK /api/draws"
    else
      echo "$(yellow '[헬스체크]') 응답 없음"
    fi
  fi
}

logs_app() {
  touch "$LOGFILE"
  echo "$(cyan "[로그] tail -f $LOGFILE (중지: Ctrl+C)")]"
  tail -f "$LOGFILE"
}

show_latest() {
  need_venv
  "$PYTHON" -m scripts.cli show-latest 10
}

show_round() {
  local round="${1:-}"
  if [ -z "$round" ]; then echo "사용법: $0 show-round <회차>"; exit 1; fi
  need_venv
  "$PYTHON" -m scripts.cli show-round "$round"
}

fetch_latest() {
  local n="${1:-10}"
  need_venv
  "$PYTHON" -m scripts.cli fetch-latest "$n"
}

rebuild_shops() {
  local round="${1:-}"
  if [ -z "$round" ]; then echo "사용법: $0 rebuild-shops <회차>"; exit 1; fi
  need_venv
  "$PYTHON" -m scripts.cli rebuild-shops "$round"
}

backup_db() {
  local DST_DIR="$ROOT/backups"
  mkdir -p "$DST_DIR"
  local ts; ts=$(date +'%Y%m%d_%H%M%S')
  cp "$ROOT/instance/lotto.db" "$DST_DIR/lotto_${ts}.db"
  echo "$(green '[백업 완료]') $DST_DIR/lotto_${ts}.db"
}

menu() {
  while true; do
    echo
    echo "================= $(cyan '로또 앱 관리 메뉴') ================="
    echo " 1) 앱 실행(백그라운드)"
    echo " 2) 앱 실행(포그라운드)"
    echo " 3) 앱 상태 확인 (status)"
    echo " 4) 앱 안전 종료 (stop)"
    echo " 5) 앱 강제 종료 (kill)"
    echo " 6) 로그 보기 (logs)"
    echo " 7) 최신 10회 수집 (fetch-latest 10)"
    echo " 8) 특정 회차 당첨점 재수집 (rebuild-shops)"
    echo " 9) 최근 10개 번호 출력 (show-latest)"
    echo "10) 특정 회차 출력 (show-round)"
    echo "11) DB 백업 (backup)"
    echo "12) 종료 (quit)"
    echo "=============================================================="
    read -rp "선택 번호 입력: " sel
    case "$sel" in
      1) start_bg ;;
      2) start_fg ;;
      3) status_app ;;
      4) stop_app_soft ;;
      5) stop_app_hard ;;
      6) logs_app ;;
      7) fetch_latest 10 ;;
      8) read -rp "회차 입력: " r; rebuild_shops "$r" ;;
      9) show_latest ;;
     10) read -rp "회차 입력: " r; show_round "$r" ;;
     11) backup_db ;;
     12) echo "bye!"; exit 0 ;;
      *) echo "$(yellow '올바른 번호를 선택하세요.')" ;;
    esac
  done
}

usage() {
  cat <<USAGE
사용법: $0 <명령> [옵션]

명령:
  start-bg           앱 실행(백그라운드, 로그는 $LOGFILE)
  start-fg           앱 실행(포그라운드, Ctrl+C로 종료)
  stop               앱 안전 종료
  kill               앱 강제 종료
  status             앱 상태 확인 + 헬스체크
  logs               로그 tail -f
  fetch-latest [N]   최신 N회 수집 (기본 10)
  rebuild-shops R    특정 회차 당첨점 재수집
  show-latest        최근 10개 번호 출력
  show-round R       특정 회차 출력
  backup             DB 백업 (backups 디렉토리)
  menu               메뉴 UI 실행 (기본값)

예시:
  $0 start-bg
  $0 start-fg
  $0 status
  $0 fetch-latest 10
  $0 rebuild-shops 1185
  $0 show-round 1184
USAGE
}

cmd="${1:-menu}"
shift || true
case "$cmd" in
  start-bg) start_bg "$@";;
  start-fg) start_fg "$@";;
  stop) stop_app_soft "$@";;
  kill) stop_app_hard "$@";;
  status) status_app "$@";;
  logs) logs_app "$@";;
  fetch-latest) fetch_latest "${1:-10}";;
  rebuild-shops) rebuild_shops "${1:-}";;
  show-latest) show_latest;;
  show-round) show_round "${1:-}";;
  backup) backup_db;;
  menu|"") menu;;
  *) usage; exit 1;;
esac
