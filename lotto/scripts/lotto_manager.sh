export LOTTO_DB=/volume1/code_work/lotto/database/lotto.db
#!/bin/sh
set -e
BASE="/volume1/code_work/lotto"
SCRIPTS="$BASE/scripts"
LOG_DIR="$BASE/logs"; mkdir -p "$LOG_DIR"
APP="$SCRIPTS/lotto_webapp.py"
PYBIN="$BASE/.venv/bin/python"
FLASK_PORT="${FLASK_PORT:-8080}"
PIDFILE="$BASE/lotto_webapp.pid"

header(){ echo "==== Lotto System @ $(date '+%F %T') ===="; }

start(){
  header; echo "[START] Flask webapp..."
  if [ -f "$PIDFILE" ] && ps -p "$(cat "$PIDFILE" 2>/dev/null)" >/dev/null 2>&1; then
    echo "Already running (PID: $(cat "$PIDFILE"))"; return 0; fi
  FLASK_PORT=$FLASK_PORT nohup "$PYBIN" "$APP" >> "$LOG_DIR/webapp.log" 2>&1 &
  echo $! > "$PIDFILE"
  echo "PID: $(cat "$PIDFILE")"; echo "URL: http://0.0.0.0:$FLASK_PORT"
}
stop(){
  header; echo "[STOP] Flask webapp..."
  if [ -f "$PIDFILE" ] && ps -p "$(cat "$PIDFILE" 2>/dev/null)" >/dev/null 2>&1; then
    kill "$(cat "$PIDFILE")" || true; sleep 1
    rm -f "$PIDFILE"; echo "Stopped"
  else
    echo "Already stopped"
  fi
}
status(){
  header; echo "[STATUS]"
  if [ -f "$PIDFILE" ] && ps -p "$(cat "$PIDFILE" 2>/dev/null)" >/dev/null 2>&1; then
    echo "RUNNING (PID: $(cat "$PIDFILE"))  URL: http://0.0.0.0:$FLASK_PORT"
  else
    echo "STOPPED"
  fi
}
logs(){ header; echo "[LOGS] tail -f"; tail -f "$LOG_DIR/webapp.log"; }
reco_next(){ header; echo "[RECOMMEND NEXT]"; curl -s -X POST "http://127.0.0.1:$FLASK_PORT/api/recommendations/generate" | jq . || true; }
validate(){ header; echo "[VALIDATE]"; D="$1"; if [ -z "$D" ]; then echo "Usage: $0 validate <draw_no>"; exit 1; fi; curl -s -X POST "http://127.0.0.1:$FLASK_PORT/api/recommendations/validate/$D" | jq . || true; }

case "$1" in
  start) start;;
  stop) stop;;
  status) status;;
  logs) logs;;
  reco_next) shift; reco_next "$@";;
  validate) shift; validate "$@";;
  *) echo "Usage: $0 {start|stop|status|logs|reco_next|validate}"; exit 1;;
esac
