#!/bin/sh
# Lotto Manager (Synology /bin/sh compatible) — clean version with config
set -eu

########## [경로/설정 로딩] ##########
# 스크립트 실경로(심볼릭링크 따라감)
SCRIPT_PATH="$0"
case "$SCRIPT_PATH" in /*) :;; *) SCRIPT_PATH="$(pwd)/$SCRIPT_PATH";; esac
while [ -L "$SCRIPT_PATH" ]; do
  LNK="$(readlink "$SCRIPT_PATH")"
  case "$LNK" in
    /*) SCRIPT_PATH="$LNK" ;;
    *)  SCRIPT_PATH="$(cd "$(dirname "$SCRIPT_PATH")" && cd "$(dirname "$LNK")" && pwd -P)/$(basename "$LNK")" ;;
  esac
done

APP_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd -P)"
APP_ROOT="${APP_ROOT_OVERRIDE:-$APP_ROOT}"

VENV="$APP_ROOT/.venv/bin/activate"
LOGDIR="$APP_ROOT/logs"
PIDFILE="$LOGDIR/lotto.pid"
CFG="$APP_ROOT/.lotto_manager.conf"

mkdir -p "$LOGDIR"

# 기본값
PORT_DEFAULT=8080
HOST_DEFAULT="http://127.0.0.1:${PORT_DEFAULT}"

# 설정파일 로드
if [ -f "$CFG" ]; then
  # shellcheck disable=SC1090
  . "$CFG"
fi

# 최종 HOST/PORT 결정 (env > config > default)
PORT="${PORT:-${LM_PORT:-$PORT_DEFAULT}}"
HOST="${HOST:-${LM_HOST:-${HOST_DEFAULT}}}"

########## [공용 함수] ##########
usage() {
  cat <<USAGE
Usage:
  $0 run-fg                     # 앱 실행 (포그라운드, reloader OFF)
  $0 run-bg                     # 앱 실행 (백그라운드, PID 기록)
  $0 status                     # 앱 상태 확인
  $0 stop                       # 앱 종료
  $0 update-latest              # 최신 회차 당첨번호 업데이트
  $0 update-range START END     # 특정 범위 업데이트
  $0 shops ROUND                # 특정 회차 1등 당첨점 수집
  $0 rec-generate [ROUND]       # 추천 생성(완전5/반자동5). 미입력시 최신+1
  $0 rec-list [LIMIT]           # 최근 추천 목록
  $0 analysis [TOP]             # 분석 요약(기본 TOP=10)
  $0 config-show                # 현재 HOST/PORT 설정 보기
  $0 config-set-host URL        # HOST 설정 저장 (예: http://192.168.1.81:8080)
  $0 config-set-port PORT       # PORT 설정 저장 (예: 8080)
  $0 menu                       # 번호 선택 메뉴 UI

Env (optional):
  APP_ROOT_OVERRIDE=/volume1/code_work/lotto_app
  HOST=http://192.168.1.81:8080  PORT=8080
(설정 파일은 $CFG 에 저장됩니다)
USAGE
}

need_venv() {
  if [ ! -f "$VENV" ]; then
    echo "[에러] 가상환경 스크립트가 없습니다: $VENV" >&2
    echo "APP_ROOT 확인 또는 APP_ROOT_OVERRIDE 로 지정하세요. 현재 APP_ROOT: $APP_ROOT" >&2
    exit 1
  fi
}

save_cfg() {
  echo "LM_HOST=\"$HOST\"" > "$CFG"
  echo "LM_PORT=\"$PORT\"" >> "$CFG"
  echo "[저장] $CFG"
}

config_show() {
  echo "APP_ROOT : $APP_ROOT"
  echo "CFG      : $CFG"
  echo "HOST     : $HOST"
  echo "PORT     : $PORT"
}

config_set_host() {
  new="${1:-}"
  if [ -z "$new" ]; then
    echo "Usage: $0 config-set-host http://192.168.1.81:8080"; exit 1
  fi
  HOST="$new"
  save_cfg
  config_show
}

config_set_port() {
  new="${1:-}"
  if [ -z "$new" ]; then
    echo "Usage: $0 config-set-port 8080"; exit 1
  fi
  PORT="$new"
  # HOST 안에 포트가 포함된 경우 갱신 유도 안내
  echo "[안내] HOST 에 포트가 포함되어 있다면 필요 시 HOST도 함께 수정하세요."
  save_cfg
  config_show
}

########## [앱 제어] ##########
run_fg() {
  need_venv
  . "$VENV"
  echo "[FG] Flask starting on port $PORT (reloader OFF)…"
  # 디버그/리로더 끔: 자식 PID 혼동 방지
  FLASK_DEBUG=0 flask --app wsgi run --host=0.0.0.0 --port="$PORT"
}

run_bg() {
  need_venv
  . "$VENV"
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "이미 백그라운드로 실행 중 (PID=$(cat "$PIDFILE")). 먼저 stop 하세요."
    exit 1
  fi
  echo "[BG] Flask starting on port $PORT (reloader OFF)…"
  nohup sh -c 'FLASK_DEBUG=0 flask --app wsgi run --host=0.0.0.0 --port='"$PORT" \
    > "$LOGDIR/app.log" 2>&1 &
  echo $! > "$PIDFILE"
  sleep 1
  echo "Started. PID=$(cat "$PIDFILE"). Log: $LOGDIR/app.log"
}

status_app() {
  echo "APP_ROOT: $APP_ROOT"
  echo "HOST    : $HOST"
  echo "PORT    : $PORT"
  echo "PIDFILE : $PIDFILE"

  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "Process : alive (PID=$(cat "$PIDFILE"))"
  else
    echo "Process : not running (or started in other way)"
  fi

  if command -v netstat >/dev/null 2>&1; then
    echo "--- netstat :$PORT ---"
    netstat -tlnp | grep ":$PORT" || true
  fi

  echo "--- HTTP /health ---"
  curl -s "$HOST/health" || echo "(no response)"
  echo
  echo "--- HTTP /api/ping ---"
  curl -s "$HOST/api/ping" || echo "(no response)"
  echo
}

stop_app() {
  if [ -f "$PIDFILE" ]; then
    PID="$(cat "$PIDFILE")"
    if kill -0 "$PID" 2>/dev/null; then
      echo "Stopping PID=$PID …"
      kill "$PID" || true
      sleep 1
      if kill -0 "$PID" 2>/dev/null; then
        echo "Force kill …"
        kill -9 "$PID" || true
      fi
    fi
    rm -f "$PIDFILE"
    echo "Stopped."
  else
    echo "PID 파일이 없습니다. 백그라운드 실행 중이 아닐 수 있습니다."
  fi
}

########## [업데이트/크롤/분석/추천] ##########
update_latest() {
  need_venv
  . "$VENV"
  python3 "$APP_ROOT/scripts/update_draws.py"
}

update_range() {
  START="${1:-}"; END="${2:-}"
  if [ -z "$START" ] || [ -z "$END" ]; then
    echo "Usage: $0 update-range START END"; exit 1
  fi
  curl -s -H "Content-Type: application/json" \
       -d "{\"start\":$START,\"end\":$END}" \
       -X POST "$HOST/api/draws/update-range"
  echo
}

shops_round() {
  ROUND="${1:-0}"
  case "$ROUND" in ''|0) echo "Usage: $0 shops ROUND"; exit 1;; esac
  need_venv
  . "$VENV"
  python3 "$APP_ROOT/scripts/update_shops.py" "$ROUND"
}

rec_generate() {
  ROUND="${1:-}"
  if [ -n "$ROUND" ]; then
    curl -s -H "Content-Type: application/json" \
      -d "{\"round\": $ROUND}" \
      -X POST "$HOST/api/recommendations/generate" | python -m json.tool
  else
    curl -s -H "Content-Type: application/json" \
      -d '{}' \
      -X POST "$HOST/api/recommendations/generate" | python -m json.tool
  fi
}

rec_list() {
  LIMIT="${1:-10}"
  curl -s "$HOST/api/recommendations/latest?limit=$LIMIT" | python -m json.tool
}

analysis_summary() {
  TOP="${1:-10}"
  curl -s "$HOST/api/analysis/summary?top=$TOP" | python -m json.tool
}

########## [메뉴 UI] ##########
menu_ui() {
  while :; do
    echo
    echo "================= Lotto Manager ================="
    echo "1) 앱 실행 (포그라운드)"
    echo "2) 앱 실행 (백그라운드)"
    echo "3) 앱 상태 확인"
    echo "4) 앱 종료"
    echo "5) 최신 회차 업데이트"
    echo "6) 범위 업데이트"
    echo "7) 1등 당첨점 크롤링 (회차 입력)"
    echo "8) 추천 생성 (라운드 입력/미입력시 최신+1)"
    echo "9) 최근 추천 보기"
    echo "10) 분석 요약 보기"
    echo "11) 설정 보기/변경(HOST/PORT)"
    echo "0) 종료"
    printf "선택 번호 입력: "
    read CHOICE
    case "$CHOICE" in
      1) run_fg ;;
      2) run_bg ;;
      3) status_app ;;
      4) stop_app ;;
      5) update_latest ;;
      6) printf "시작 회차: "; read S; printf "끝 회차: "; read E; update_range "$S" "$E" ;;
      7) printf "회차 입력: "; read R; shops_round "$R" ;;
      8) printf "라운드(미입력시 엔터): "; read RR; rec_generate "$RR" ;;
      9) printf "표시 개수(LIMIT, 기본10): "; read LIM; rec_list "${LIM:-10}" ;;
      10) printf "TOP 개수(기본10): "; read T; analysis_summary "${T:-10}" ;;
      11)
         echo "---- 설정 ----"
         config_show
         echo "1) HOST 변경  2) PORT 변경  0) 뒤로"
         printf "선택: "; read C2
         case "$C2" in
           1) printf "새 HOST (예: http://192.168.1.81:8080): "; read NH; HOST="$NH"; save_cfg ;;
           2) printf "새 PORT (예: 8080): "; read NP; PORT="$NP"; save_cfg ;;
           0) : ;;
           *) echo "잘못된 선택입니다." ;;
         esac
         ;;
      0) echo "종료합니다."; exit 0 ;;
      *) echo "잘못된 선택입니다." ;;
    esac
  done
}

########## [엔트리] ##########
CMD="${1:-menu}"
case "$CMD" in
  run-fg)          run_fg ;;
  run-bg)          run_bg ;;
  status)          status_app ;;
  stop)            stop_app ;;
  update-latest)   update_latest ;;
  update-range)    shift; update_range "${1:-}" "${2:-}" ;;
  shops)           shift; shops_round "${1:-0}" ;;
  rec-generate)    shift; rec_generate "${1:-}" ;;
  rec-list)        shift; rec_list "${1:-10}" ;;
  analysis)        shift; analysis_summary "${1:-10}" ;;
  config-show)     config_show ;;
  config-set-host) shift; config_set_host "${1:-}" ;;
  config-set-port) shift; config_set_port "${1:-}" ;;
  menu)            menu_ui ;;
  *)               usage; exit 1 ;;
esac
