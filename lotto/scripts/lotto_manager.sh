#!/bin/sh
# Lotto WebApp Simple Manager (portable: macOS / Linux / Synology NAS)
# POSIX sh only. No bashisms.

set -eu

# --- Paths ---
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
APP="$ROOT/scripts/lotto_webapp.py"
LOGDIR="$ROOT/logs"
PIDFILE="$LOGDIR/app.pid"
LOGFILE="$LOGDIR/app.log"

# --- Config ---
PORT="${PORT:-8080}"              # export PORT=9090 로 바꿀 수 있음
LOTTO_DB="${LOTTO_DB:-$ROOT/database/lotto.db}"   # 필요시 export LOTTO_DB=... 로 지정
export LOTTO_DB PORT

# --- Utils ---
say() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

ensure_dirs() {
  mkdir -p "$LOGDIR" "$ROOT/database" "$ROOT/templates" "$ROOT/static"
}

detect_python() {
  # 1) 활성화된 venv
  if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    echo "$VIRTUAL_ENV/bin/python"; return
  fi
  # 2) 프로젝트 .venv
  if [ -x "$ROOT/.venv/bin/python" ]; then
    echo "$ROOT/.venv/bin/python"; return
  fi
  # 3) 상위 .venv (로컬과 서버 디렉터리 구조 다를 때 대비)
  if [ -x "$ROOT/../.venv/bin/python" ]; then
    echo "$ROOT/../.venv/bin/python"; return
  fi
  # 4) 시스템
  if command -v python3 >/dev/null 2>&1; then
    echo python3; return
  fi
  if command -v python >/dev/null 2>&1; then
    echo python; return
  fi
  echo ""
}

PYTHON="$(detect_python)"

is_running() {
  [ -f "$PIDFILE" ] || return 1
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  [ -n "${pid:-}" ] || return 1
  # POSIX way to check process
  kill -0 "$pid" 2>/dev/null
}

# --- Kill processes bound to PORT (portable) ---
kill_port_procs() {
  # 1) macOS/리눅스에서 lsof가 가장 안정적
  if command -v lsof >/dev/null 2>&1; then
    # lsof 가 PID만 출력
    PIDS="$(lsof -t -i TCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
    [ -n "${PIDS:-}" ] || PIDS="$(lsof -t -i TCP:"$PORT" 2>/dev/null || true)"
    for p in $PIDS; do
      say "포트 $PORT 사용 프로세스 종료(PID=$p)"
      kill -9 "$p" 2>/dev/null || true
    done
    return 0
  fi

  # 2) fuser (BusyBox/리눅스에 흔함)
  if command -v fuser >/dev/null 2>&1; then
    # 조용히 종료
    fuser -k -TERM -n tcp "$PORT" 2>/dev/null || true
    # 혹시 남았으면 KILL
    fuser -k -KILL -n tcp "$PORT" 2>/dev/null || true
    return 0
  fi

  # 3) ss (리눅스)
  if command -v ss >/dev/null 2>&1; then
    # ss -ltnp 는 루트 권한 없으면 이름만 보일 수도 있음
    PIDS="$(ss -ltnp 2>/dev/null | awk -v p=":$PORT" '$4 ~ p {print $6}' | sed 's/.*pid=\([0-9]*\).*/\1/' | sort -u)"
    for p in $PIDS; do
      say "포트 $PORT 사용 프로세스 종료(PID=$p)"
      kill -9 "$p" 2>/dev/null || true
    done
    return 0
  fi

  # 4) netstat (플랫폼별 옵션 다름 → best-effort)
  if command -v netstat >/dev/null 2>&1; then
    # 여러 OS 케이스를 시도: mac은 -vanp tcp 없음, 리눅스는 -tulpn
    # 리눅스 스타일
    PIDS="$(netstat -tulpn 2>/dev/null | awk -v p=":$PORT" '$4 ~ p {print $7}' | cut -d/ -f1 | grep -E '^[0-9]+$' || true)"
    # mac/일부 busybox는 PID 못 줌 → 여기서는 포기(사용자에게 lsof/fuser 권장)
    for p in $PIDS; do
      say "포트 $PORT 사용 프로세스 종료(PID=$p)"
      kill -9 "$p" 2>/dev/null || true
    done
    return 0
  fi

  say "포트 $PORT 강제 종료 도구(lsof/fuser/ss/netstat)를 찾지 못했습니다."
}

action_fg() {
  ensure_dirs
  [ -n "$PYTHON" ] || { echo "Python을 찾지 못했습니다. venv 활성화 또는 python3 설치 필요."; exit 1; }
  say "포그라운드 실행 (PORT=$PORT)"
  exec "$PYTHON" "$APP"
}

action_start() {
  ensure_dirs
  [ -n "$PYTHON" ] || { echo "Python을 찾지 못했습니다. venv 활성화 또는 python3 설치 필요."; exit 1; }
  say "백그라운드 실행 (PORT=$PORT)"
  nohup "$PYTHON" "$APP" >"$LOGFILE" 2>&1 &
  echo $! >"$PIDFILE"
  sleep 1
  action_status
}

action_status() {
  if is_running; then
    pid="$(cat "$PIDFILE")"
    say "실행 중 (PID=$pid, PORT=$PORT)"
  else
    say "앱이 실행 중이지 않습니다."
  fi
}

action_stop() {
  say "앱 종료 시도..."

  killed="false"
  if is_running; then
    pid="$(cat "$PIDFILE")"
    say "PID=$pid 종료"
    kill "$pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      say "강제 종료(KILL)"
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PIDFILE"
    killed="true"
  fi

  # 포트 점유 프로세스까지 정리
  kill_port_procs || true

  if [ "$killed" = "true" ]; then
    say "앱이 완전히 종료되었습니다."
  else
    say "종료할 프로세스가 없습니다."
  fi
}

action_logs() {
  if [ -f "$LOGFILE" ]; then
    tail -n 50 -f "$LOGFILE"
  else
    say "로그 파일이 아직 없습니다. ($LOGFILE)"
  fi
}

menu() {
  while :; do
    cat <<EOF

=============================
 🎲 Lotto WebApp Manager
 ROOT: $ROOT
 PORT: $PORT
 LOG : $LOGFILE
=============================
1) 포그라운드 실행
2) 백그라운드 실행
3) 상태 확인
4) 앱 종료 (포트 ${PORT}까지 정리)
5) 로그 보기
0) 종료
=============================
EOF
    printf "메뉴 번호 선택: "
    IFS= read -r ans
    case "${ans:-}" in
      1) action_fg ;;
      2) action_start ;;
      3) action_status ;;
      4) action_stop ;;
      5) action_logs ;;
      0) echo "Bye!"; exit 0 ;;
      *) echo "잘못된 선택입니다." ;;
    esac
  done
}

menu
