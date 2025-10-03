# 배포 전 체크리스트

> 마지막 업데이트: 2025-10-03
> 프로젝트: 로또 관리 시스템

---

## 📋 배포 전 필수 작업

### 1. 데이터베이스 마이그레이션

- [ ] **마이그레이션 백업**
  ```bash
  # 기존 데이터베이스 백업
  cp instance/lotto.db instance/lotto.db.backup_$(date +%Y%m%d_%H%M%S)
  ```

- [ ] **마이그레이션 실행**
  ```bash
  # Phase 1.1: Purchase 모델 마이그레이션
  python scripts/migrate_purchase_model.py

  # Phase 3.3: 성능 최적화 인덱스 추가
  python scripts/add_composite_indexes.py
  ```

- [ ] **마이그레이션 검증**
  - 모든 필드가 정상적으로 추가되었는지 확인
  - 인덱스가 정상적으로 생성되었는지 확인
  - 기존 데이터가 정상적으로 조회되는지 확인

---

### 2. 환경 설정

- [ ] **환경 변수 확인**
  ```bash
  # NAS 또는 EC2 환경에서
  export FLASK_ENV=nas  # 또는 production
  ```

- [ ] **SECRET_KEY 설정 (프로덕션 필수)**
  ```python
  # app/config.py에서 실제 비밀키로 변경
  SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
  ```

- [ ] **데이터베이스 경로 확인**
  ```python
  # instance/lotto.db가 정상적으로 생성되는지 확인
  ```

---

### 3. 의존성 및 패키지

- [ ] **requirements.txt 최신화**
  ```bash
  pip freeze > requirements.txt
  ```

- [ ] **필수 패키지 설치**
  ```bash
  pip install -r requirements.txt
  ```

- [ ] **Python 버전 확인**
  - Python 3.8 이상 권장
  - Python 3.11 이상에서 테스트 완료

---

### 4. 기능 테스트

#### Phase 1: 데이터 모델 및 기본 구조
- [ ] **구매관리 페이지 (`/buy`)**
  - [ ] 회차 선택 기능
  - [ ] AI 추천 탭
  - [ ] 수동 입력 탭 (45개 버튼)
  - [ ] 텍스트 입력 탭 (단일/배치 모드)
  - [ ] 랜덤 생성 탭
  - [ ] 장바구니 추가/삭제
  - [ ] 구매 확정

- [ ] **전략분석 페이지 (`/strategy`)**
  - [ ] AI 추천 기능
  - [ ] "구매관리에 추가" 버튼
  - [ ] Quick Action 섹션

#### Phase 2: UX 개선 및 대시보드
- [ ] **메인 대시보드 (`/`)**
  - [ ] 다음 추첨 정보 카드
  - [ ] 실시간 카운트다운
  - [ ] 4개 빠른 액션 버튼
  - [ ] 나의 현황 요약
  - [ ] 최근 활동 피드
  - [ ] 최신 추첨 결과
  - [ ] 1등 당첨점 (5개 제한)

- [ ] **플로팅 버튼**
  - [ ] 우하단 고정 (🛒 아이콘)
  - [ ] 대시보드/구매관리/모바일에서 숨김
  - [ ] 기타 페이지에서 표시

- [ ] **모바일 페이지**
  - [ ] `/mobile` - 대시보드
  - [ ] `/mobile/buy` - 구매관리
  - [ ] `/mobile/strategy` - 전략분석
  - [ ] `/mobile/purchases` - 구매이력
  - [ ] `/mobile/info` - 정보조회
  - [ ] `/mobile/crawling` - 데이터수집

#### Phase 3: 고급 기능 및 최적화
- [ ] **배치 입력**
  - [ ] 단일/배치 모드 토글
  - [ ] 여러 줄 텍스트 입력
  - [ ] 라인별 유효성 검사
  - [ ] 오류 라인 표시
  - [ ] 전체 추가 기능

- [ ] **성능 최적화**
  - [ ] 복합 인덱스 정상 작동
  - [ ] N+1 쿼리 해결 (eager loading)
  - [ ] 페이지 로딩 속도 2초 이내

- [ ] **사용자 통계**
  - [ ] `/api/user-statistics` API
  - [ ] 구매 패턴 분석
  - [ ] 입력 방식 선호도
  - [ ] 자주 선택한 번호 TOP 10
  - [ ] 데스크톱 통계 표시
  - [ ] 모바일 통계 표시

---

### 5. 보안 체크

- [ ] **CSRF 보호**
  - [ ] 모든 POST 요청에 CSRF 토큰
  - [ ] Flask-WTF CSRF 활성화

- [ ] **비밀번호 보안**
  - [ ] Werkzeug 해싱 사용
  - [ ] 비밀번호 강도 검증

- [ ] **계정 잠금**
  - [ ] 5회 실패 시 15분 잠금
  - [ ] 계정 잠금 해제 로직

- [ ] **관리자 권한**
  - [ ] 관리자 전용 페이지 접근 제어
  - [ ] 사용자 관리 기능

---

### 6. 성능 테스트

- [ ] **부하 테스트**
  - [ ] 동시 접속 10명 이상
  - [ ] 대량 데이터 조회 (100회 이상)
  - [ ] 배치 입력 (10개 이상)

- [ ] **데이터베이스 최적화**
  - [ ] 인덱스 효과 확인
  - [ ] 쿼리 실행 시간 측정
  - [ ] VACUUM 실행

  ```bash
  sqlite3 instance/lotto.db "VACUUM;"
  ```

- [ ] **메모리 사용량**
  - [ ] 프로세스 메모리 모니터링
  - [ ] 메모리 누수 확인

---

### 7. 로깅 및 모니터링

- [ ] **로그 설정**
  ```python
  # 프로덕션 환경에서 로그 레벨 설정
  import logging
  logging.basicConfig(level=logging.INFO)
  ```

- [ ] **에러 로깅**
  - [ ] 500 에러 로그
  - [ ] 데이터베이스 에러 로그
  - [ ] API 에러 로그

- [ ] **모니터링 도구** (선택사항)
  - [ ] Sentry 통합
  - [ ] New Relic
  - [ ] CloudWatch (AWS)

---

### 8. 정적 파일

- [ ] **CSS/JS 최소화** (선택사항)
  - [ ] CSS minification
  - [ ] JavaScript minification

- [ ] **정적 파일 캐싱**
  ```python
  # app/config.py
  SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1년
  ```

---

### 9. 서버 설정

#### Flask 개발 서버 (테스트 용도만)
```bash
# 로컬 테스트
./start.sh local

# NAS 테스트
./start.sh nas
```

#### 프로덕션 서버 (권장)
```bash
# Gunicorn 설치
pip install gunicorn

# Gunicorn 실행
gunicorn -w 4 -b 0.0.0.0:8080 'app:create_app()' --daemon

# 또는 uWSGI
pip install uwsgi
uwsgi --http 0.0.0.0:8080 --wsgi-file run.py --callable app --processes 4
```

#### Nginx 리버스 프록시 (선택사항)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static {
        alias /path/to/lotto_manager_web/app/static;
        expires 1y;
    }
}
```

---

### 10. 백업 전략

- [ ] **데이터베이스 백업**
  ```bash
  # 일일 백업 cron job
  0 2 * * * cp /path/to/instance/lotto.db /path/to/backups/lotto_$(date +\%Y\%m\%d).db
  ```

- [ ] **코드 백업**
  ```bash
  # Git 저장소에 푸시
  git add .
  git commit -m "Production deployment $(date +%Y-%m-%d)"
  git push origin main
  ```

- [ ] **백업 복구 테스트**
  - [ ] 백업에서 복원 가능한지 확인
  - [ ] 복원 시간 측정

---

### 11. 문서화

- [ ] **README.md 업데이트**
  - [ ] 설치 방법
  - [ ] 실행 방법
  - [ ] 주요 기능 설명

- [ ] **CLAUDE.md 업데이트**
  - [ ] 새로운 기능 추가
  - [ ] API 엔드포인트 문서화

- [ ] **IMPROVEMENT_PLAN.md 최종 확인**
  - [ ] 완료된 작업 체크
  - [ ] 미완료 작업 명시

---

### 12. 사용자 공지

- [ ] **변경사항 공지**
  - [ ] 새로운 기능 안내
  - [ ] 사용법 가이드
  - [ ] 문의 채널 안내

- [ ] **FAQ 작성**
  - [ ] 자주 묻는 질문
  - [ ] 문제 해결 방법

---

## 🚀 배포 절차

### 단계 1: 사전 준비
```bash
# 1. 코드 풀
git pull origin main

# 2. 의존성 설치
source .venv/bin/activate
pip install -r requirements.txt

# 3. 데이터베이스 백업
cp instance/lotto.db instance/lotto.db.backup_$(date +%Y%m%d)
```

### 단계 2: 마이그레이션
```bash
# 1. Purchase 모델 마이그레이션
python scripts/migrate_purchase_model.py

# 2. 인덱스 추가
python scripts/add_composite_indexes.py

# 3. 검증
python -c "from app import create_app; app = create_app(); print('OK')"
```

### 단계 3: 서버 시작
```bash
# 개발 환경 (테스트)
./start.sh nas

# 프로덕션 환경 (권장)
gunicorn -w 4 -b 0.0.0.0:8080 'app:create_app()' --daemon
```

### 단계 4: 동작 확인
```bash
# 1. 헬스 체크
curl http://localhost:8080/

# 2. API 테스트
curl http://localhost:8080/api/data-stats

# 3. 로그 확인
tail -f logs/lotto_app.log
```

---

## ✅ 배포 완료 후 확인사항

- [ ] 메인 페이지 정상 로딩
- [ ] 로그인/로그아웃 정상 동작
- [ ] 구매 기능 정상 동작
- [ ] AI 추천 기능 정상 동작
- [ ] 통계 페이지 정상 로딩
- [ ] 모바일 페이지 정상 동작
- [ ] 크롤링 기능 정상 동작
- [ ] 데이터베이스 쿼리 성능 확인

---

## 🔧 롤백 절차

문제 발생 시 롤백:

```bash
# 1. 서버 중지
./start.sh stop
# 또는
pkill -f gunicorn

# 2. 데이터베이스 복원
cp instance/lotto.db.backup_YYYYMMDD instance/lotto.db

# 3. 코드 복원
git reset --hard HEAD~1
# 또는 특정 커밋으로
git reset --hard <commit-hash>

# 4. 서버 재시작
./start.sh nas
```

---

## 📞 문의 및 지원

- **이슈 트래커**: https://github.com/your-repo/issues
- **이메일**: your-email@example.com
- **긴급 연락처**: XXX-XXXX-XXXX

---

## 📝 배포 기록

| 날짜 | 버전 | 주요 변경사항 | 배포자 |
|------|------|--------------|--------|
| 2025-10-03 | 2.0.0 | Phase 1-3 개선사항 배포 | - |
| - | - | - | - |
