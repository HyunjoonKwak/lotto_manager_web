#!/bin/bash

# 간단한 Git 백업 메뉴
# 사용법: bash git_menu.sh

# 색상
G='\033[0;32m'; R='\033[0;31m'; Y='\033[1;33m'; NC='\033[0m'

# 현재 상태 확인
check_git() {
    if [ ! -d ".git" ]; then
        echo -e "${R}❌ Git 저장소가 아닙니다.${NC}"
        exit 1
    fi
}

# 메뉴 표시
show_menu() {
    clear
    echo -e "${G}=== Git 백업 메뉴 ===${NC}"
    echo ""
    echo -e "${G}현재 위치:${NC} $(pwd)"
    echo -e "${G}현재 브랜치:${NC} $(git branch --show-current 2>/dev/null || echo 'main')"

    # 변경사항 확인
    changes=$(git status --porcelain 2>/dev/null | wc -l)
    if [ "$changes" -gt 0 ]; then
        echo -e "${Y}📝 변경된 파일: ${changes}개${NC}"
    else
        echo -e "${G}✅ 변경사항 없음${NC}"
    fi

    echo ""
    echo "1) 빠른 백업 (자동 메시지)"
    echo "2) 메시지 입력해서 백업"
    echo "3) 상태만 확인"
    echo "4) 최근 커밋 보기"
    echo "0) 종료"
    echo ""
}

# 빠른 백업
quick_backup() {
    if [ "$(git status --porcelain | wc -l)" -eq 0 ]; then
        echo -e "${Y}변경사항이 없습니다.${NC}"
        return
    fi

    msg="작업 저장 $(date '+%m%d_%H%M')"
    echo -e "${G}백업 중: $msg${NC}"

    git add . && git commit -m "$msg" && git push
    [ $? -eq 0 ] && echo -e "${G}✅ 백업 완료!${NC}" || echo -e "${R}❌ 백업 실패${NC}"
}

# 메시지 백업
message_backup() {
    if [ "$(git status --porcelain | wc -l)" -eq 0 ]; then
        echo -e "${Y}변경사항이 없습니다.${NC}"
        return
    fi

    echo -n "커밋 메시지: "
    read msg
    [ -z "$msg" ] && msg="작업 저장 $(date '+%H:%M')"

    git add . && git commit -m "$msg" && git push
    [ $? -eq 0 ] && echo -e "${G}✅ 백업 완료!${NC}" || echo -e "${R}❌ 백업 실패${NC}"
}

# 상태 확인
check_status() {
    echo -e "${G}=== 변경사항 ===${NC}"
    git status --short
    echo ""
    echo -e "${G}=== 브랜치 ===${NC}"
    git branch
}

# 최근 커밋
show_log() {
    echo -e "${G}=== 최근 커밋 ===${NC}"
    git log --oneline -10 --graph
}

# 메인 루프
check_git

while true; do
    show_menu
    echo -n "선택 (0-4): "
    read choice

    case $choice in
        1) quick_backup ;;
        2) message_backup ;;
        3) check_status ;;
        4) show_log ;;
        0) echo -e "${G}안녕!${NC}"; exit 0 ;;
        *) echo -e "${R}잘못된 선택${NC}" ;;
    esac

    echo ""
    echo -n "계속하려면 Enter..."
    read
done
