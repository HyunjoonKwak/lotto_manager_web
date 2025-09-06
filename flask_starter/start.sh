#!/bin/bash

# Flask Lotto Application Launcher
# 로또 분석 애플리케이션 실행 스크립트

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

# PID 파일 경로
PID_FILE="flask_app.pid"

# 로고 출력
print_logo() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    Flask Lotto Application                   ║"
    echo "║                      로또 분석 시스템                        ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# 메뉴 출력
print_menu() {
    echo -e "${WHITE}┌─────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${WHITE}│                    실행 모드 선택                          │${NC}"
    echo -e "${WHITE}├─────────────────────────────────────────────────────────────┤${NC}"
    echo -e "${WHITE}│  ${GREEN}1${NC} │ 로컬 개발 환경 (포트 5000)                    │${NC}"
    echo -e "${WHITE}│  ${GREEN}2${NC} │ NAS 환경 (포트 8080, 외부 접속 허용)         │${NC}"
    echo -e "${WHITE}│  ${BLUE}3${NC} │ 백그라운드 실행 (NAS 환경)                   │${NC}"
    echo -e "${WHITE}│  ${YELLOW}4${NC} │ 서버 상태 확인                              │${NC}"
    echo -e "${WHITE}│  ${RED}5${NC} │ 서버 중지                                    │${NC}"
    echo -e "${WHITE}│  ${BLUE}6${NC} │ 환경 확인                                   │${NC}"
    echo -e "${WHITE}│  ${CYAN}7${NC} │ IP 주소 확인                                │${NC}"
    echo -e "${WHITE}│  ${RED}0${NC} │ 종료                                        │${NC}"
    echo -e "${WHITE}└─────────────────────────────────────────────────────────────┘${NC}"
    echo ""
}

# 서버 상태 확인
check_server_status() {
    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${GREEN}✓ 서버가 실행 중입니다. (PID: $pid)${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠ PID 파일이 있지만 프로세스가 실행되지 않습니다.${NC}"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        echo -e "${RED}✗ 서버가 실행되지 않습니다.${NC}"
        return 1
    fi
}

# 서버 중지
stop_server() {
    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${YELLOW}서버를 중지합니다... (PID: $pid)${NC}"
            kill "$pid"
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                echo -e "${YELLOW}강제 종료합니다...${NC}"
                kill -9 "$pid"
            fi
            rm -f "$PID_FILE"
            echo -e "${GREEN}✓ 서버가 중지되었습니다.${NC}"
        else
            echo -e "${YELLOW}프로세스가 이미 종료되었습니다.${NC}"
            rm -f "$PID_FILE"
        fi
    else
        echo -e "${RED}서버가 실행되지 않습니다.${NC}"
    fi
}

# 환경 확인
check_environment() {
    echo -e "${BLUE}🔍 환경 확인 중...${NC}"

    # Python 버전 확인
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
        echo -e "${GREEN}✓ Python 버전: $PYTHON_VERSION${NC}"
    else
        echo -e "${RED}✗ Python3가 설치되지 않았습니다.${NC}"
        return 1
    fi

    # 가상환경 확인
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        echo -e "${GREEN}✓ 가상환경 활성화됨: $(basename $VIRTUAL_ENV)${NC}"
    else
        echo -e "${YELLOW}⚠ 가상환경이 활성화되지 않았습니다.${NC}"
    fi

    # requirements.txt 확인
    if [[ -f "requirements.txt" ]]; then
        echo -e "${GREEN}✓ requirements.txt 발견${NC}"
    else
        echo -e "${RED}✗ requirements.txt를 찾을 수 없습니다.${NC}"
        return 1
    fi

    # 데이터베이스 확인
    if [[ -f "instance/lotto.db" ]]; then
        echo -e "${GREEN}✓ 데이터베이스 파일 발견${NC}"
    else
        echo -e "${YELLOW}⚠ 데이터베이스 파일이 없습니다.${NC}"
    fi

    echo ""
    return 0
}

# IP 주소 확인
get_ip_addresses() {
    echo -e "${BLUE}🌐 IP 주소 확인 중...${NC}"

    # 로컬 IP 주소
    echo -e "${CYAN}로컬 IP 주소:${NC}"
    if command -v ifconfig &> /dev/null; then
        ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1
    else
        echo -e "${YELLOW}IP 주소를 확인할 수 없습니다.${NC}"
    fi

    # 외부 IP 주소
    echo -e "${CYAN}외부 IP 주소:${NC}"
    if command -v curl &> /dev/null; then
        EXTERNAL_IP=$(curl -s --max-time 5 https://ifconfig.me 2>/dev/null || echo "확인 실패")
        echo "$EXTERNAL_IP"
    else
        echo -e "${YELLOW}curl이 설치되지 않아 외부 IP를 확인할 수 없습니다.${NC}"
    fi
    echo ""
}

# 포트 사용 여부 확인
check_port() {
    local port=$1
    if command -v lsof &> /dev/null; then
        lsof -i :$port > /dev/null 2>&1
    elif command -v netstat &> /dev/null; then
        netstat -tuln | grep ":$port " > /dev/null 2>&1
    else
        return 1
    fi
}

# 포트 사용 프로세스 종료
kill_port_process() {
    local port=$1
    echo -e "${YELLOW}포트 $port 사용 가능 여부를 확인합니다...${NC}"

    if check_port $port; then
        echo -e "${YELLOW}포트 $port이 이미 사용 중입니다.${NC}"

        # 포트를 사용하는 프로세스 찾기
        local pids=""
        if command -v lsof &> /dev/null; then
            pids=$(lsof -ti :$port 2>/dev/null)
        elif command -v netstat &> /dev/null; then
            pids=$(netstat -tulnp | grep ":$port " | awk '{print $7}' | cut -d'/' -f1 | grep -v '-' | sort -u)
        fi

        if [[ -n "$pids" ]]; then
            echo -e "${YELLOW}포트 $port을 사용하는 프로세스: $pids${NC}"
            echo -e "${YELLOW}기존 프로세스를 종료합니다...${NC}"
            echo $pids | xargs kill -9 2>/dev/null || true
            sleep 2
            echo -e "${GREEN}✓ 기존 프로세스가 종료되었습니다.${NC}"
        fi
    else
        echo -e "${GREEN}✓ 포트 $port이 사용 가능합니다.${NC}"
    fi
}

# 서버 시작
start_server() {
    local mode=$1

    case $mode in
        "local")
            echo -e "${GREEN}🚀 로컬 개발 서버를 시작합니다...${NC}"
            echo -e "${CYAN}접속 URL: http://127.0.0.1:5000${NC}"
            export FLASK_ENV=development
            python run_local.py
            ;;
        "nas")
            echo -e "${GREEN}🚀 NAS 서버를 시작합니다...${NC}"
            kill_port_process 8080
            echo -e "${CYAN}접속 URL: http://0.0.0.0:8080${NC}"
            echo -e "${CYAN}외부 접속: http://[NAS_IP]:8080${NC}"
            export FLASK_ENV=nas
            python run_nas.py
            ;;
        "bg")
            if check_server_status > /dev/null 2>&1; then
                echo -e "${YELLOW}서버가 이미 실행 중입니다.${NC}"
                return 1
            fi

            echo -e "${GREEN}🚀 백그라운드에서 NAS 서버를 시작합니다...${NC}"
            kill_port_process 8080
            echo -e "${CYAN}접속 URL: http://0.0.0.0:8080${NC}"
            export FLASK_ENV=nas
            nohup python -u run_nas.py > flask_app.log 2>&1 &
            local pid=$!
            echo $pid > "$PID_FILE"
            echo -e "${GREEN}✓ 서버가 백그라운드에서 시작되었습니다. (PID: $pid)${NC}"
            echo -e "${YELLOW}로그 파일: flask_app.log${NC}"
            ;;
    esac
}

# 메뉴 선택 처리
select_menu() {
    while true; do
        print_menu
        echo -e "${YELLOW}실행할 작업을 선택하세요 (0-7):${NC} "
        read -r choice

        case $choice in
            1)
                echo -e "${GREEN}로컬 개발 환경을 선택했습니다.${NC}"
                start_server "local"
                break
                ;;
            2)
                echo -e "${GREEN}NAS 환경을 선택했습니다.${NC}"
                start_server "nas"
                break
                ;;
            3)
                echo -e "${BLUE}백그라운드 실행을 선택했습니다.${NC}"
                start_server "bg"
                echo -e "${YELLOW}계속하려면 Enter를 누르세요...${NC}"
                read -r
                ;;
            4)
                echo -e "${YELLOW}서버 상태 확인을 선택했습니다.${NC}"
                check_server_status
                echo -e "${YELLOW}계속하려면 Enter를 누르세요...${NC}"
                read -r
                ;;
            5)
                echo -e "${RED}서버 중지를 선택했습니다.${NC}"
                stop_server
                echo -e "${YELLOW}계속하려면 Enter를 누르세요...${NC}"
                read -r
                ;;
            6)
                echo -e "${BLUE}환경 확인을 선택했습니다.${NC}"
                check_environment
                echo -e "${YELLOW}계속하려면 Enter를 누르세요...${NC}"
                read -r
                ;;
            7)
                echo -e "${CYAN}IP 주소 확인을 선택했습니다.${NC}"
                get_ip_addresses
                echo -e "${YELLOW}계속하려면 Enter를 누르세요...${NC}"
                read -r
                ;;
            0)
                echo -e "${RED}프로그램을 종료합니다.${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}잘못된 선택입니다. 0-7 사이의 숫자를 입력하세요.${NC}"
                echo -e "${YELLOW}계속하려면 Enter를 누르세요...${NC}"
                read -r
                ;;
        esac
    done
}

# 도움말 출력
print_help() {
    echo -e "${YELLOW}사용법:${NC}"
    echo "  $0 [옵션]"
    echo ""
    echo -e "${YELLOW}옵션:${NC}"
    echo "  ${GREEN}local${NC}     - 로컬 개발 환경 (포트 5000)"
    echo "  ${GREEN}nas${NC}       - NAS 환경 (포트 8080, 외부 접속 허용)"
    echo "  ${GREEN}bg${NC}        - 백그라운드 실행 (NAS 환경)"
    echo "  ${GREEN}status${NC}    - 서버 상태 확인"
    echo "  ${GREEN}stop${NC}      - 서버 중지"
    echo "  ${GREEN}ip${NC}        - IP 주소 확인"
    echo "  ${GREEN}menu${NC}      - 대화형 메뉴 모드"
    echo "  ${GREEN}help${NC}      - 이 도움말 출력"
    echo ""
    echo -e "${YELLOW}예시:${NC}"
    echo "  $0 local    # 로컬 개발 서버 시작"
    echo "  $0 nas      # NAS 서버 시작"
    echo "  $0 bg       # 백그라운드에서 NAS 서버 시작"
    echo "  $0 status   # 서버 상태 확인"
    echo "  $0 stop     # 서버 중지"
    echo "  $0 menu     # 대화형 메뉴 모드"
    echo ""
}

# 메인 함수
main() {
    local mode=${1:-"menu"}

    print_logo

    # 특별한 명령어 처리
    case $mode in
        "help"|"-h"|"--help")
            print_help
            exit 0
            ;;
        "status")
            check_server_status
            exit 0
            ;;
        "stop")
            stop_server
            exit 0
            ;;
        "bg")
            start_server "bg"
            exit 0
            ;;
        "ip")
            get_ip_addresses
            exit 0
            ;;
    esac

    # 메뉴 모드 또는 직접 실행
    if [[ "$mode" == "menu" ]]; then
        if ! check_environment; then
            echo -e "${RED}환경 확인에 실패했습니다. 문제를 해결한 후 다시 시도하세요.${NC}"
            exit 1
        fi
        select_menu
    else
        check_environment
        start_server "$mode"
    fi
}

# 스크립트 실행
main "$@"
