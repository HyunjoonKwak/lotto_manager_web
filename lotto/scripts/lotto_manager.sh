#!/usr/bin/env bash
set -euo pipefail

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# 심볼 텍스트 정의 (이모지 제거)
DICE="*"
CHECK="[OK]"
CROSS="[X]"
ARROW=">"
CLOCK="(wait)"
WEB="WEB"
ROCKET="PID"
STOP="STOP"
EYE="LOG"
FILE="FILE"

# 환경 로드
set -a; [ -f "$(dirname "$0")/.env" ] && . "$(dirname "$0")/.env"; set +a
APP_PY="$SCRIPTS_PATH/lotto_webapp.py"
CRAWLER="$SCRIPTS_PATH/lotto_crawler.py"
ANALYZER="$SCRIPTS_PATH/lotto_analyzer.py"
RECO="$SCRIPTS_PATH/lotto_recommender.py"
VENV_BIN="$APP_ROOT/.venv/bin"
LOG_DIR="${LOG_DIR:-$APP_ROOT/logs}"
mkdir -p "$LOG_DIR"

# 헤더 출력
print_header() {
    clear
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    ${DICE} 로또 번호 분석 시스템 ${DICE}                    ║"
    echo "║                    AI 기반 분석 및 추천                        ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# 상태 표시
print_status() {
    local status=$1
    local message=$2
    case $status in
        "success") echo -e "${GREEN}${CHECK} $message${NC}" ;;
        "error") echo -e "${RED}${CROSS} $message${NC}" ;;
        "warning") echo -e "${YELLOW}[WARN] $message${NC}" ;;
        "info") echo -e "${BLUE}${ARROW} $message${NC}" ;;
        "loading") echo -e "${CYAN}${CLOCK} $message${NC}" ;;
    esac
}

# 진행률 표시
show_progress() {
    local message=$1
    echo -ne "${CYAN}${CLOCK} $message"
    for i in {1..3}; do
        sleep 0.3
        echo -n "."
    done
    echo -e "${NC}"
}

# 웹앱 시작
start_web() {
    print_header
    print_status "loading" "웹 애플리케이션을 시작하는 중..."
    
    if pgrep -f "lotto_webapp.py" >/dev/null; then
        print_status "warning" "웹 애플리케이션이 이미 실행 중입니다."
        return 1
    fi
    
    # PID 파일 경로
    local pid_file="$LOG_DIR/webapp.pid"
    
    # 이전 PID 파일 정리
    if [ -f "$pid_file" ]; then
        local old_pid=$(cat "$pid_file")
        if kill -0 "$old_pid" 2>/dev/null; then
            print_status "warning" "이전 프로세스(PID: $old_pid)를 종료합니다..."
            kill "$old_pid" 2>/dev/null || true
            sleep 1
        fi
        rm -f "$pid_file"
    fi
    
    # 백그라운드에서 웹앱 실행
    (
        cd "$(dirname "$APP_PY")"
        nohup "$VENV_BIN/python3" "$APP_PY" > "$LOG_DIR/webapp.log" 2>&1 &
        local webapp_pid=$!
        echo "$webapp_pid" > "$pid_file"
        
        # 시작 로그 기록
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WEBAPP STARTED (PID: $webapp_pid)" >> "$LOG_DIR/webapp.log"
    ) &
    
    show_progress "서버 초기화"
    
    # 서버 시작 대기
    local max_wait=30
    local wait_count=0
    
    while [ $wait_count -lt $max_wait ]; do
        if [ -f "$pid_file" ]; then
            local pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                # 포트 확인 (5000번 포트)
                if netstat -tlnp 2>/dev/null | grep -q ":5000 "; then
                    print_status "success" "웹 애플리케이션이 성공적으로 시작되었습니다!"
                    echo -e "${WHITE}${WEB} 접속 주소: ${GREEN}http://localhost:5000${NC}"
                    echo -e "${WHITE}${ROCKET} PID: ${GREEN}$pid${NC}"
                    return 0
                fi
            fi
        fi
        sleep 1
        wait_count=$((wait_count + 1))
        echo -ne "\r${CYAN}서버 시작 대기 중... ${wait_count}/${max_wait}초${NC}"
    done
    
    echo ""
    print_status "error" "웹 애플리케이션 시작 시간 초과 (${max_wait}초)"
    return 1
}

# 웹앱 중지
stop_web() {
    print_header
    print_status "loading" "웹 애플리케이션을 중지하는 중..."
    
    local pid_file="$LOG_DIR/webapp.pid"
    
    # PID 파일에서 프로세스 확인
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            print_status "info" "PID 파일에서 프로세스 발견: $pid"
            
            # 정상 종료 시도
            kill "$pid" 2>/dev/null || true
            show_progress "프로세스 종료"
            
            # 종료 대기
            local max_wait=10
            local wait_count=0
            while [ $wait_count -lt $max_wait ]; do
                if ! kill -0 "$pid" 2>/dev/null; then
                    break
                fi
                sleep 1
                wait_count=$((wait_count + 1))
            done
            
            # 강제 종료 시도
            if kill -0 "$pid" 2>/dev/null; then
                print_status "warning" "강제 종료를 시도합니다..."
                kill -9 "$pid" 2>/dev/null || true
                sleep 2
            fi
            
            # 종료 확인
            if ! kill -0 "$pid" 2>/dev/null; then
                print_status "success" "웹 애플리케이션이 성공적으로 중지되었습니다."
                rm -f "$pid_file"
                return 0
            else
                print_status "error" "웹 애플리케이션 강제 종료에 실패했습니다."
                return 1
            fi
        else
            print_status "warning" "PID 파일의 프로세스가 이미 종료되었습니다."
            rm -f "$pid_file"
        fi
    fi
    
    # PID 파일이 없거나 프로세스가 없는 경우 pgrep으로 확인
    if pgrep -f "lotto_webapp.py" >/dev/null; then
        local pids=$(pgrep -f "lotto_webapp.py")
        print_status "warning" "PID 파일 없이 실행 중인 프로세스 발견: $pids"
        
        pkill -f "lotto_webapp.py" || true
        show_progress "프로세스 종료"
        
        sleep 2
        if pgrep -f "lotto_webapp.py" >/dev/null; then
            print_status "warning" "강제 종료를 시도합니다..."
            pkill -9 -f "lotto_webapp.py" || true
            sleep 2
        fi
        
        if ! pgrep -f "lotto_webapp.py" >/dev/null; then
            print_status "success" "웹 애플리케이션이 성공적으로 중지되었습니다."
            return 0
        else
            print_status "error" "웹 애플리케이션 중지에 실패했습니다."
            return 1
        fi
    else
        print_status "warning" "실행 중인 웹 애플리케이션이 없습니다."
        return 0
    fi
}

# 상태 확인
status() {
    print_header
    echo -e "${WHITE}${WEB} 시스템 상태${NC}"
    echo "══════════════════════════════════════════════════════════════"
    
    # 웹 애플리케이션 상태
    local pid_file="$LOG_DIR/webapp.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            local uptime=$(ps -o etime= -p "$pid" 2>/dev/null || echo "알 수 없음")
            print_status "success" "웹 애플리케이션 실행 중"
            echo -e "   ${WHITE}PID: ${GREEN}$pid${NC}"
            echo -e "   ${WHITE}실행 시간: ${GREEN}$uptime${NC}"
            echo -e "   ${WHITE}접속 주소: ${GREEN}http://localhost:5000${NC}"
        else
            print_status "error" "PID 파일의 프로세스가 종료됨"
        fi
    elif pgrep -f "lotto_webapp.py" >/dev/null; then
        local pid=$(pgrep -f "lotto_webapp.py")
        local uptime=$(ps -o etime= -p "$pid" 2>/dev/null || echo "알 수 없음")
        print_status "warning" "웹 애플리케이션 실행 중 (PID 파일 없음)"
        echo -e "   ${WHITE}PID: ${YELLOW}$pid${NC}"
        echo -e "   ${WHITE}실행 시간: ${GREEN}$uptime${NC}"
        echo -e "   ${WHITE}접속 주소: ${GREEN}http://localhost:5000${NC}"
    else
        print_status "error" "웹 애플리케이션 중지됨"
    fi
    
    echo ""
    
    # 포트 상태 확인
    echo -e "${WHITE}${WEB} 포트 상태${NC}"
    echo "══════════════════════════════════════════════════════════════"
    
    if netstat -tlnp 2>/dev/null | grep -q ":5000 "; then
        local port_info=$(netstat -tlnp 2>/dev/null | grep ":5000 " | head -1)
        print_status "success" "포트 5000 활성화됨"
        echo -e "   ${WHITE}상태: ${GREEN}$port_info${NC}"
    else
        print_status "error" "포트 5000 비활성화됨"
    fi
}

# 로그 보기
logs() {
    print_header
    echo -e "${WHITE}${EYE} 실시간 로그 모니터링${NC}"
    echo "══════════════════════════════════════════════════════════════"
    echo -e "${YELLOW}로그를 종료하려면 Ctrl+C를 누르세요.${NC}"
    echo ""
    
    if [ -f "$LOG_DIR/webapp.log" ]; then
        tail -n 50 -f "$LOG_DIR/webapp.log"
    else
        print_status "error" "로그 파일을 찾을 수 없습니다: $LOG_DIR/webapp.log"
    fi
}

# 포트 모니터링
monitor_ports() {
    print_header
    echo -e "${WHITE}${WEB} 실시간 포트 모니터링${NC}"
    echo "══════════════════════════════════════════════════════════════"
    echo -e "${YELLOW}포트 모니터링을 종료하려면 Ctrl+C를 누르세요.${NC}"
    echo ""
    
    # 모니터링할 포트들
    local ports=("5000" "8080" "3000" "8000")
    
    while true; do
        clear
        print_header
        echo -e "${WHITE}${WEB} 실시간 포트 모니터링${NC}"
        echo "══════════════════════════════════════════════════════════════"
        echo -e "${WHITE}${CLOCK} 마지막 업데이트: ${GREEN}$(date '+%Y-%m-%d %H:%M:%S')${NC}"
        echo ""
        
        for port in "${ports[@]}"; do
            if netstat -tlnp 2>/dev/null | grep -q ":$port "; then
                local port_info=$(netstat -tlnp 2>/dev/null | grep ":$port " | head -1)
                print_status "success" "포트 $port 활성화됨"
                echo -e "   ${WHITE}상태: ${GREEN}$port_info${NC}"
            else
                print_status "error" "포트 $port 비활성화됨"
            fi
            echo ""
        done
        
        echo -e "${CYAN}5초 후 자동 새로고침...${NC}"
        sleep 5
    done
}

# 데이터 수집
crawl() {
    print_header
    print_status "loading" "로또 데이터를 수집하는 중..."
    echo -e "${WHITE}데이터 수집 시작${NC}"
    echo "══════════════════════════════════════════════════════════════"
    
    "$VENV_BIN/python3" "$CRAWLER" 2>&1 | tee -a "$LOG_DIR/crawler.log"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_status "success" "데이터 수집이 완료되었습니다!"
    else
        print_status "error" "데이터 수집에 실패했습니다."
        return 1
    fi
}

# 데이터 분석
analyze() {
    print_header
    print_status "loading" "로또 데이터를 분석하는 중..."
    echo -e "${WHITE}데이터 분석 시작${NC}"
    echo "══════════════════════════════════════════════════════════════"
    
    "$VENV_BIN/python3" "$ANALYZER" 2>&1 | tee -a "$LOG_DIR/analyzer.log"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_status "success" "데이터 분석이 완료되었습니다!"
    else
        print_status "error" "데이터 분석에 실패했습니다."
        return 1
    fi
}

# 추천 생성
recommend() {
    print_header
    print_status "loading" "로또 번호를 추천하는 중..."
    echo -e "${WHITE}추천 번호 생성 시작${NC}"
    echo "══════════════════════════════════════════════════════════════"
    
    "$VENV_BIN/python3" "$RECO" 2>&1 | tee -a "$LOG_DIR/recommend.log"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_status "success" "추천 번호 생성이 완료되었습니다!"
    else
        print_status "error" "추천 번호 생성에 실패했습니다."
        return 1
    fi
}

# 대화형 메뉴
interactive_menu() {
    while true; do
        print_header
        echo -e "${WHITE}메인 메뉴${NC}"
        echo "══════════════════════════════════════════════════════════════"
        echo -e "${GREEN}1.${NC} ${ROCKET} 웹 애플리케이션 시작"
        echo -e "${GREEN}2.${NC} ${STOP} 웹 애플리케이션 중지"
        echo -e "${GREEN}3.${NC} ${EYE} 시스템 상태 확인"
        echo -e "${GREEN}4.${NC} ${FILE} 실시간 로그 보기"
        echo -e "${GREEN}5.${NC} ${WEB} 포트 모니터링"
        echo -e "${GREEN}6.${NC} 데이터 수집"
        echo -e "${GREEN}7.${NC} 데이터 분석"
        echo -e "${GREEN}8.${NC} 추천 번호 생성"
        echo -e "${RED}0.${NC} 종료"
        echo "══════════════════════════════════════════════════════════════"
        echo -ne "${CYAN}선택하세요 (0-8): ${NC}"
        read -r choice
        
        case $choice in
            1) start_web; echo -e "\n${YELLOW}계속하려면 Enter를 누르세요...${NC}"; read ;;
            2) stop_web; echo -e "\n${YELLOW}계속하려면 Enter를 누르세요...${NC}"; read ;;
            3) status; echo -e "\n${YELLOW}계속하려면 Enter를 누르세요...${NC}"; read ;;
            4) logs ;;
            5) monitor_ports ;;
            6) crawl; echo -e "\n${YELLOW}계속하려면 Enter를 누르세요...${NC}"; read ;;
            7) analyze; echo -e "\n${YELLOW}계속하려면 Enter를 누르세요...${NC}"; read ;;
            8) recommend; echo -e "\n${YELLOW}계속하려면 Enter를 누르세요...${NC}"; read ;;
            0) 
                print_header
                print_status "info" "로또 번호 분석 시스템을 종료합니다."
                echo -e "${WHITE}${DICE} 감사합니다! ${DICE}${NC}"
                exit 0 
                ;;
            *) 
                print_status "error" "잘못된 선택입니다. 다시 시도해주세요."
                sleep 2 
                ;;
        esac
    done
}

# 도움말 출력
show_help() {
    print_header
    echo -e "${WHITE}사용법${NC}"
    echo "══════════════════════════════════════════════════════════════"
    echo -e "${GREEN}대화형 모드:${NC}"
    echo "   $0"
    echo ""
    echo -e "${GREEN}명령어 모드:${NC}"
    echo "   $0 start      - 웹 애플리케이션 시작"
    echo "   $0 stop       - 웹 애플리케이션 중지"
    echo "   $0 status     - 시스템 상태 확인"
    echo "   $0 logs       - 실시간 로그 보기"
    echo "   $0 monitor    - 포트 모니터링"
    echo "   $0 crawl      - 데이터 수집"
    echo "   $0 analyze    - 데이터 분석"
    echo "   $0 recommend  - 추천 번호 생성"
    echo "   $0 help       - 도움말 표시"
    echo ""
    echo -e "${WHITE}${DICE} 로또 번호 분석 시스템 v2.0 ${DICE}${NC}"
}

# 메인 로직
case "${1:-}" in
    start)      start_web ;;
    stop)       stop_web ;;
    status)     status ;;
    logs)       logs ;;
    monitor)    monitor_ports ;;
    crawl)      crawl ;;
    analyze)    analyze ;;
    recommend)  recommend ;;
    help|--help|-h) show_help ;;
    "")         interactive_menu ;;
    *)          show_help; exit 1 ;;
esac
