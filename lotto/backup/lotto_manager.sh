#!/bin/bash

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 메뉴 표시 함수
show_menu() {
    clear
    echo -e "${CYAN}🎲 로또 분석 시스템 관리자${NC}"
    echo -e "${YELLOW}================================${NC}"
    echo ""
    echo -e "${GREEN}1.${NC} 🔄 전체 업데이트 실행"
    echo -e "${GREEN}2.${NC} ⚡ 빠른 업데이트 실행"
    echo -e "${GREEN}3.${NC} 🧠 고급 분석 실행"
    echo -e "${GREEN}4.${NC} 🛒 구매 관리 실행"
    echo -e "${GREEN}5.${NC} 📊 전체 데이터 수집"
    echo -e "${GREEN}6.${NC} 📊 시스템 상태 확인"
    echo -e "${GREEN}7.${NC} 🌐 웹 서버 시작"
    echo -e "${GREEN}8.${NC} 📋 로그 파일 보기"
    echo -e "${GREEN}9.${NC} 🌐 웹 서버 백그라운드 시작"
    echo -e "${GREEN}10.${NC} 🔍 8080 포트 프로세스 확인/종료"
    echo -e "${GREEN}0.${NC} 🚪 종료"
    echo ""
    echo -e "${YELLOW}원하는 기능의 번호를 입력하세요:${NC} "
}

# 전체 업데이트 실행
run_full_update() {
    echo -e "${BLUE}🔄 전체 업데이트 실행${NC}"
    cd /volume1/web/lotto/scripts
    python3 lotto_auto_updater.py full
    echo ""
    echo -e "${GREEN}✅ 전체 업데이트가 완료되었습니다.${NC}"
    read -p "계속하려면 Enter를 누르세요..."
}

# 빠른 업데이트 실행
run_quick_update() {
    echo -e "${BLUE}⚡ 빠른 업데이트 실행${NC}"
    cd /volume1/web/lotto/scripts
    python3 lotto_auto_updater.py quick
    echo ""
    echo -e "${GREEN}✅ 빠른 업데이트가 완료되었습니다.${NC}"
    read -p "계속하려면 Enter를 누르세요..."
}

# 고급 분석 실행
run_analysis() {
    echo -e "${BLUE}🧠 고급 분석 실행${NC}"
    cd /volume1/web/lotto/scripts
    python3 lotto_advanced_analyzer.py
    echo ""
    echo -e "${GREEN}✅ 고급 분석이 완료되었습니다.${NC}"
    read -p "계속하려면 Enter를 누르세요..."
}

# 구매 관리 실행
run_purchase_manager() {
    echo -e "${BLUE}🛒 구매 관리 실행${NC}"
    cd /volume1/web/lotto/scripts
    python3 lotto_purchase_manager.py
    echo ""
    echo -e "${GREEN}✅ 구매 관리가 완료되었습니다.${NC}"
    read -p "계속하려면 Enter를 누르세요..."
}

# 전체 데이터 수집
run_data_collection() {
    echo -e "${BLUE}📊 전체 데이터 수집${NC}"
    cd /volume1/web/lotto/scripts
    python3 lotto_full_collector.py
    echo ""
    echo -e "${GREEN}✅ 전체 데이터 수집이 완료되었습니다.${NC}"
    read -p "계속하려면 Enter를 누르세요..."
}

# 시스템 상태 확인
check_status() {
    echo -e "${BLUE}📊 시스템 상태 확인${NC}"
    cd /volume1/web/lotto/scripts

    # 데이터베이스 상태
    echo -e "${YELLOW}🗄️ 데이터베이스 정보:${NC}"
    sqlite3 /volume1/web/lotto/database/lotto.db "SELECT COUNT(*) as '총 회차' FROM lotto_results;"
    sqlite3 /volume1/web/lotto/database/lotto.db "SELECT MAX(draw_no) as '최신 회차' FROM lotto_results;"
    sqlite3 /volume1/web/lotto/database/lotto.db "SELECT COUNT(*) as '추천 번호' FROM recommended_numbers;"
    sqlite3 /volume1/web/lotto/database/lotto.db "SELECT COUNT(*) as '구매 기록' FROM purchase_records;"

    # 로그 파일 확인
    echo ""
    echo -e "${YELLOW}📝 최근 로그:${NC}"
    if [ -f "/volume1/web/lotto/logs/update.log" ]; then
        echo "마지막 전체 업데이트:"
        tail -3 /volume1/web/lotto/logs/update.log
    fi

    echo ""
    read -p "계속하려면 Enter를 누르세요..."
}

# 웹 서버 시작
start_web_server() {
    echo -e "${BLUE}🌐 웹 서버 시작${NC}"
    echo -e "${YELLOW}웹 서버를 시작합니다. 종료하려면 Ctrl+C를 누르세요.${NC}"
    cd /volume1/web/lotto/scripts
    python3 lotto_webapp.py
}

# 로그 파일 보기
view_logs() {
    echo -e "${BLUE}📋 로그 파일 보기${NC}"
    echo ""

    if [ -f "/volume1/web/lotto/logs/update.log" ]; then
        echo -e "${YELLOW}=== 업데이트 로그 ===${NC}"
        tail -20 /volume1/web/lotto/logs/update.log
        echo ""
    fi

    if [ -f "/volume1/web/lotto/logs/quick.log" ]; then
        echo -e "${YELLOW}=== 빠른 업데이트 로그 ===${NC}"
        tail -10 /volume1/web/lotto/logs/quick.log
        echo ""
    fi

    read -p "계속하려면 Enter를 누르세요..."
}

# 웹 서버 백그라운드 시작
start_web_server_background() {
    echo -e "${BLUE}🌐 웹 서버 백그라운드 시작${NC}"

    # 이미 실행 중인지 확인
    if pgrep -f "lotto_webapp.py" > /dev/null; then
        echo -e "${YELLOW}⚠️ 웹 서버가 이미 실행 중입니다.${NC}"
        echo -e "${YELLOW}프로세스 ID: $(pgrep -f 'lotto_webapp.py')${NC}"
        read -p "계속하려면 Enter를 누르세요..."
        return
    fi

    cd /volume1/web/lotto/scripts

    # 백그라운드에서 웹 서버 시작
    nohup python3 lotto_webapp.py > /volume1/web/lotto/logs/webapp.log 2>&1 &
    WEB_PID=$!

    echo -e "${GREEN}✅ 웹 서버가 백그라운드에서 시작되었습니다.${NC}"
    echo -e "${YELLOW}프로세스 ID: $WEB_PID${NC}"
    echo -e "${YELLOW}로그 파일: /volume1/web/lotto/logs/webapp.log${NC}"
    echo -e "${YELLOW}웹 서버를 중지하려면 'kill $WEB_PID' 명령을 사용하세요.${NC}"

    # 프로세스 ID를 파일에 저장 (나중에 중지할 때 사용)
    echo $WEB_PID > /volume1/web/lotto/scripts/webapp.pid

    read -p "계속하려면 Enter를 누르세요..."
}

# 8080 포트 프로세스 확인 및 종료
check_and_kill_port_8080() {
    echo -e "${BLUE}🔍 8080 포트 프로세스 확인/종료${NC}"
    echo ""

    # 8080 포트를 사용하는 프로세스 확인 (netstat 사용)
    PORT_INFO=$(netstat -tlnp 2>/dev/null | grep ":8080 " | head -1)

    if [ -z "$PORT_INFO" ]; then
        echo -e "${GREEN}✅ 8080 포트에서 실행 중인 프로세스가 없습니다.${NC}"
        read -p "계속하려면 Enter를 누르세요..."
        return
    fi

    # PID 추출 (마지막 컬럼에서 /이전의 숫자)
    PID=$(echo "$PORT_INFO" | awk '{print $7}' | cut -d'/' -f1)

    if [ -z "$PID" ] || [ "$PID" = "-" ]; then
        echo -e "${YELLOW}⚠️ 8080 포트는 사용 중이지만 PID를 확인할 수 없습니다.${NC}"
        echo -e "${YELLOW}포트 정보: $PORT_INFO${NC}"
        read -p "계속하려면 Enter를 누르세요..."
        return
    fi

    echo -e "${YELLOW}⚠️ 8080 포트에서 실행 중인 프로세스:${NC}"
    echo ""

    # 프로세스 정보 출력
    PROCESS_INFO=$(ps -p $PID -o pid,ppid,user,command --no-headers 2>/dev/null)
    echo -e "${CYAN}프로세스 ID: $PID${NC}"
    echo -e "${YELLOW}포트 정보: $PORT_INFO${NC}"
    echo -e "${YELLOW}프로세스 정보: $PROCESS_INFO${NC}"
    echo ""

    echo -e "${RED}이 프로세스를 종료하시겠습니까? (y/N):${NC} "
    read -r confirm

    if [[ $confirm =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}🔄 프로세스 종료 중...${NC}"

        echo -e "${YELLOW}프로세스 $PID 종료 중...${NC}"
        kill -TERM $PID 2>/dev/null

        # 3초 대기 후 강제 종료
        sleep 3
        if kill -0 $PID 2>/dev/null; then
            echo -e "${RED}프로세스 $PID 강제 종료 중...${NC}"
            kill -KILL $PID 2>/dev/null
        fi

        # 종료 확인
        sleep 2
        REMAINING_PORT_INFO=$(netstat -tlnp 2>/dev/null | grep ":8080 " | head -1)

        if [ -z "$REMAINING_PORT_INFO" ]; then
            echo -e "${GREEN}✅ 프로세스가 성공적으로 종료되었습니다.${NC}"
        else
            echo -e "${RED}❌ 프로세스가 여전히 실행 중입니다:${NC}"
            echo -e "${RED}포트 정보: $REMAINING_PORT_INFO${NC}"
        fi
    else
        echo -e "${YELLOW}프로세스 종료를 취소했습니다.${NC}"
    fi

    read -p "계속하려면 Enter를 누르세요..."
}

# 메인 메뉴 루프
main_menu() {
    while true; do
        show_menu
        read -r choice

        case $choice in
            1)
                run_full_update
                ;;
            2)
                run_quick_update
                ;;
            3)
                run_analysis
                ;;
            4)
                run_purchase_manager
                ;;
            5)
                run_data_collection
                ;;
            6)
                check_status
                ;;
            7)
                start_web_server
                ;;
            8)
                view_logs
                ;;
            9)
                start_web_server_background
                ;;
            10)
                check_and_kill_port_8080
                ;;
            0)
                echo -e "${GREEN}👋 로또 분석 시스템을 종료합니다.${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}❌ 잘못된 선택입니다. 0-10 사이의 숫자를 입력하세요.${NC}"
                sleep 2
                ;;
        esac
    done
}

# 스크립트 시작
main_menu
