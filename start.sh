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
    echo "║                      로또 분석 시스템                            ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# 메뉴 출력
print_menu() {
    echo -e "${WHITE}┌─────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${WHITE}│                    실행 모드 선택                              │${NC}"
    echo -e "${WHITE}├─────────────────────────────────────────────────────────────┤${NC}"
    echo -e "${WHITE}│  ${GREEN}1${NC}  │ 로컬 개발 환경 (포트 5001)                   │${NC}"
    echo -e "${WHITE}│  ${BLUE}2${NC}   │ 백그라운드 실행 (서버 환경)                    │${NC}"
    echo -e "${WHITE}│  ${YELLOW}3${NC} │ 서버 상태 확인                              │${NC}"
    echo -e "${WHITE}│  ${RED}4${NC}    │ 서버 중지                                  │${NC}"
    echo -e "${WHITE}│  ${BLUE}5${NC}   │ 환경 확인                                  │${NC}"
    echo -e "${WHITE}│  ${CYAN}6${NC}   │ IP 주소 확인                               │${NC}"
    echo -e "${WHITE}│  ${YELLOW}7${NC} │ 로그 파일 확인 (flask_app.log)              │${NC}"
    echo -e "${WHITE}│  ${RED}0${NC}    │ 종료                                      │${NC}"
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
    echo -e "${BLUE}🔍 서버 중지 작업을 시작합니다...${NC}"
    local stopped_any=false

    # 1. PID 파일 기반 프로세스 중지
    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${YELLOW}📋 PID 파일에서 발견된 서버를 중지합니다... (PID: $pid)${NC}"
            kill "$pid"
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                echo -e "${YELLOW}⚡ 강제 종료합니다...${NC}"
                kill -9 "$pid"
            fi
            echo -e "${GREEN}✓ PID 기반 서버가 중지되었습니다.${NC}"
            stopped_any=true
        else
            echo -e "${YELLOW}⚠ PID 파일이 있지만 프로세스가 이미 종료되었습니다.${NC}"
        fi
        rm -f "$PID_FILE"
    fi

    # 2. 포트 기반 프로세스 검색 및 정리
    echo -e "${BLUE}🔍 포트 사용 프로세스를 확인합니다...${NC}"
    local ports_to_check=(5001 8080)

    for port in "${ports_to_check[@]}"; do
        local pids
        if command -v lsof &> /dev/null; then
            pids=$(lsof -ti ":$port" 2>/dev/null || true)
        fi

        if [[ -n "$pids" ]]; then
            echo -e "${YELLOW}📡 포트 $port에서 실행 중인 프로세스 발견: $pids${NC}"

            # 각 PID별로 프로세스 정보 확인
            for pid in $pids; do
                if command -v ps &> /dev/null; then
                    local process_info=$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")
                    echo -e "${CYAN}   - PID $pid: $process_info${NC}"
                fi
            done

            # SIGTERM으로 정상 종료 시도
            echo -e "${YELLOW}🔄 포트 $port 프로세스들을 정상 종료합니다...${NC}"
            echo "$pids" | xargs kill -TERM 2>/dev/null || true
            sleep 3

            # 여전히 실행 중이면 SIGKILL로 강제 종료
            local remaining_pids
            if command -v lsof &> /dev/null; then
                remaining_pids=$(lsof -ti ":$port" 2>/dev/null || true)
            fi

            if [[ -n "$remaining_pids" ]]; then
                echo -e "${YELLOW}⚡ 포트 $port 프로세스들을 강제 종료합니다...${NC}"
                echo "$remaining_pids" | xargs kill -KILL 2>/dev/null || true
                sleep 1
            fi

            # 최종 확인
            if command -v lsof &> /dev/null; then
                local final_check=$(lsof -ti ":$port" 2>/dev/null || true)
                if [[ -z "$final_check" ]]; then
                    echo -e "${GREEN}✓ 포트 $port가 정리되었습니다.${NC}"
                else
                    echo -e "${RED}⚠ 포트 $port에 여전히 프로세스가 남아있습니다.${NC}"
                fi
            fi
            stopped_any=true
        else
            echo -e "${GREEN}✓ 포트 $port는 사용 중이지 않습니다.${NC}"
        fi
    done

    # 3. Flask 관련 프로세스 검색 (추가 안전장치)
    echo -e "${BLUE}🔍 Flask 관련 프로세스를 확인합니다...${NC}"
    if command -v pgrep &> /dev/null; then
        local flask_pids=$(pgrep -f "python.*run" 2>/dev/null || true)
        if [[ -n "$flask_pids" ]]; then
            echo -e "${YELLOW}🐍 Flask 관련 프로세스 발견: $flask_pids${NC}"
            for pid in $flask_pids; do
                if command -v ps &> /dev/null; then
                    local cmd=$(ps -p "$pid" -o args= 2>/dev/null || echo "unknown")
                    echo -e "${CYAN}   - PID $pid: $cmd${NC}"
                fi
            done

            echo -e "${YELLOW}🔄 Flask 프로세스들을 정리합니다...${NC}"
            echo "$flask_pids" | xargs kill -TERM 2>/dev/null || true
            sleep 2

            # 강제 종료 (필요시)
            local remaining_flask=$(pgrep -f "python.*run" 2>/dev/null || true)
            if [[ -n "$remaining_flask" ]]; then
                echo -e "${YELLOW}⚡ Flask 프로세스들을 강제 종료합니다...${NC}"
                echo "$remaining_flask" | xargs kill -KILL 2>/dev/null || true
            fi
            stopped_any=true
        else
            echo -e "${GREEN}✓ Flask 관련 프로세스가 없습니다.${NC}"
        fi
    fi

    # 최종 결과 출력
    if [[ "$stopped_any" == true ]]; then
        echo -e "${GREEN}🎉 모든 서버 프로세스가 정리되었습니다.${NC}"
    else
        echo -e "${BLUE}ℹ️  실행 중인 서버가 없었습니다.${NC}"
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

# 로그 파일 확인
check_log_file() {
    local log_file="flask_app.log"
    echo -e "${BLUE}📋 로그 파일 확인 중...${NC}"
    echo ""

    if [[ -f "$log_file" ]]; then
        echo -e "${GREEN}✓ 로그 파일이 발견되었습니다: $log_file${NC}"
        echo -e "${CYAN}파일 크기: $(du -h "$log_file" | cut -f1)${NC}"
        echo -e "${CYAN}마지막 수정: $(date -r "$log_file" 2>/dev/null || stat -c %y "$log_file" 2>/dev/null || echo "확인 실패")${NC}"
        echo ""

        while true; do
            echo -e "${YELLOW}로그 확인 옵션:${NC}"
            echo -e "${WHITE}  ${GREEN}1${NC} │ 전체 로그 보기${NC}"
            echo -e "${WHITE}  ${GREEN}2${NC} │ 마지막 20줄 보기${NC}"
            echo -e "${WHITE}  ${GREEN}3${NC} │ 마지막 50줄 보기${NC}"
            echo -e "${WHITE}  ${GREEN}4${NC} │ 실시간 로그 보기 (Ctrl+C로 종료)${NC}"
            echo -e "${WHITE}  ${GREEN}5${NC} │ 오류만 검색${NC}"
            echo -e "${WHITE}  ${GREEN}6${NC} │ 로그 파일 지우기${NC}"
            echo -e "${WHITE}  ${RED}0${NC} │ 돌아가기${NC}"
            echo ""
            echo -e "${YELLOW}선택하세요 (0-6):${NC} "
            read -r log_choice

            case $log_choice in
                1)
                    echo -e "${GREEN}전체 로그를 표시합니다...${NC}"
                    echo -e "${CYAN}==================== 전체 로그 ====================${NC}"
                    cat "$log_file"
                    echo -e "${CYAN}===================== 로그 끝 =====================${NC}"
                    ;;
                2)
                    echo -e "${GREEN}마지막 20줄을 표시합니다...${NC}"
                    echo -e "${CYAN}================== 마지막 20줄 ==================${NC}"
                    tail -20 "$log_file"
                    echo -e "${CYAN}===================== 로그 끝 =====================${NC}"
                    ;;
                3)
                    echo -e "${GREEN}마지막 50줄을 표시합니다...${NC}"
                    echo -e "${CYAN}================== 마지막 50줄 ==================${NC}"
                    tail -50 "$log_file"
                    echo -e "${CYAN}===================== 로그 끝 =====================${NC}"
                    ;;
                4)
                    echo -e "${GREEN}실시간 로그를 표시합니다... (Ctrl+C로 종료)${NC}"
                    echo -e "${CYAN}=================== 실시간 로그 ==================${NC}"
                    tail -f "$log_file"
                    ;;
                5)
                    echo -e "${GREEN}오류 로그를 검색합니다...${NC}"
                    echo -e "${CYAN}==================== 오류 로그 ====================${NC}"
                    grep -i -E "(error|exception|traceback|failed)" "$log_file" || echo -e "${YELLOW}오류가 발견되지 않았습니다.${NC}"
                    echo -e "${CYAN}===================== 로그 끝 =====================${NC}"
                    ;;
                6)
                    echo -e "${RED}로그 파일을 지우시겠습니까? (y/N):${NC} "
                    read -r confirm
                    if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
                        > "$log_file"
                        echo -e "${GREEN}✓ 로그 파일이 지워졌습니다.${NC}"
                    else
                        echo -e "${YELLOW}로그 삭제가 취소되었습니다.${NC}"
                    fi
                    ;;
                0)
                    return
                    ;;
                *)
                    echo -e "${RED}잘못된 선택입니다. 0-6 사이의 숫자를 입력하세요.${NC}"
                    ;;
            esac
            echo ""
            echo -e "${YELLOW}계속하려면 Enter를 누르세요...${NC}"
            read -r
            echo ""
        done
    else
        echo -e "${RED}✗ 로그 파일을 찾을 수 없습니다: $log_file${NC}"
        echo -e "${YELLOW}백그라운드 서버가 실행되지 않았거나 아직 로그가 생성되지 않았을 수 있습니다.${NC}"
    fi
    echo ""
}


# 기존 프로세스 정리
cleanup_existing_processes() {
    local port=$1
    echo -e "${YELLOW}기존 프로세스를 정리합니다...${NC}"

    # 포트를 사용하는 프로세스 찾기
    local pids
    if command -v lsof &> /dev/null; then
        pids=$(lsof -ti ":$port" 2>/dev/null || true)
    fi

    if [[ -n "$pids" ]]; then
        echo -e "${YELLOW}포트 $port를 사용하는 프로세스: $pids${NC}"
        # SIGTERM으로 정상 종료 시도
        echo "$pids" | xargs kill -TERM 2>/dev/null || true
        sleep 3

        # 여전히 실행 중이면 SIGKILL로 강제 종료
        local remaining_pids
        remaining_pids=$(lsof -ti ":$port" 2>/dev/null || true)
        if [[ -n "$remaining_pids" ]]; then
            echo -e "${YELLOW}강제 종료합니다...${NC}"
            echo "$remaining_pids" | xargs kill -KILL 2>/dev/null || true
            sleep 1
        fi
    fi

    # PID 파일 정리
    rm -f "$PID_FILE"
}

# 서버 시작
start_server() {
    local mode=$1

    case $mode in
        "local")
            echo -e "${GREEN}🚀 로컬 개발 서버를 시작합니다...${NC}"
            echo -e "${CYAN}접속 URL: http://127.0.0.1:5001${NC}"

            # 기존 프로세스 정리
            cleanup_existing_processes 5001

            # 환경 변수 설정
            export FLASK_ENV=development
            export FLASK_DEBUG=1

            # 가상환경 활성화 및 Python 스크립트 실행
            source .venv/bin/activate && python3 run.py
            ;;
        "bg")
            if check_server_status > /dev/null 2>&1; then
                echo -e "${YELLOW}서버가 이미 실행 중입니다.${NC}"
                return 1
            fi

            echo -e "${GREEN}🚀 백그라운드에서 NAS 서버를 시작합니다...${NC}"
            echo -e "${CYAN}접속 URL: http://0.0.0.0:8080${NC}"

            # 기존 프로세스 정리
            cleanup_existing_processes 8080

            # 환경 변수 설정
            export FLASK_ENV=nas
            export FLASK_DEBUG=0

            # 백그라운드 실행
            source .venv/bin/activate && nohup python3 -u run_nas.py > flask_app.log 2>&1 &
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
                echo -e "${BLUE}백그라운드 실행을 선택했습니다.${NC}"
                start_server "bg"
                echo -e "${YELLOW}계속하려면 Enter를 누르세요...${NC}"
                read -r
                ;;
            3)
                echo -e "${YELLOW}서버 상태 확인을 선택했습니다.${NC}"
                check_server_status
                echo -e "${YELLOW}계속하려면 Enter를 누르세요...${NC}"
                read -r
                ;;
            4)
                echo -e "${RED}서버 중지를 선택했습니다.${NC}"
                stop_server
                echo -e "${YELLOW}계속하려면 Enter를 누르세요...${NC}"
                read -r
                ;;
            5)
                echo -e "${BLUE}환경 확인을 선택했습니다.${NC}"
                check_environment
                echo -e "${YELLOW}계속하려면 Enter를 누르세요...${NC}"
                read -r
                ;;
            6)
                echo -e "${CYAN}IP 주소 확인을 선택했습니다.${NC}"
                get_ip_addresses
                echo -e "${YELLOW}계속하려면 Enter를 누르세요...${NC}"
                read -r
                ;;
            7)
                echo -e "${YELLOW}로그 파일 확인을 선택했습니다.${NC}"
                check_log_file
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
    echo "  ${GREEN}local${NC}     - 로컬 개발 환경 (포트 5001)"
    echo "  ${GREEN}bg${NC}        - 백그라운드 실행 (NAS 환경)"
    echo "  ${GREEN}status${NC}    - 서버 상태 확인"
    echo "  ${GREEN}stop${NC}      - 서버 중지"
    echo "  ${GREEN}ip${NC}        - IP 주소 확인"
    echo "  ${GREEN}log${NC}       - 로그 파일 확인"
    echo "  ${GREEN}menu${NC}      - 대화형 메뉴 모드"
    echo "  ${GREEN}help${NC}      - 이 도움말 출력"
    echo ""
    echo -e "${YELLOW}예시:${NC}"
    echo "  $0 local    # 로컬 개발 서버 시작"
    echo "  $0 bg       # 백그라운드에서 NAS 서버 시작"
    echo "  $0 status   # 서버 상태 확인"
    echo "  $0 stop     # 서버 중지"
    echo "  $0 log      # 로그 파일 확인"
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
        "log")
            check_log_file
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
