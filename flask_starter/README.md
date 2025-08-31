# Flask 로또 분석 애플리케이션

## 프로젝트 개요

이 프로젝트는 Flask 기반의 로또 번호 분석 및 추천 시스템입니다. 로또 데이터를 수집하고 분석하여 사용자에게 유용한 정보를 제공합니다.

## 주요 기능

### 🎯 핵심 기능
- 로또 당첨 번호 데이터 수집 및 저장
- 당첨 번호 통계 분석 및 시각화
- AI 기반 번호 추천 알고리즘
- 개인별 구매 이력 관리
- 당첨 결과 자동 확인

### 🔐 사용자 관리
- 회원가입 및 로그인 (Flask-Login)
- 비밀번호 강도 검증 및 재설정
- 로그인 시도 제한 (5회 실패시 15분 잠금)
- CSRF 보호 및 세션 보안

### 🛡️ 관리자 기능
- 관리자 전용 대시보드
- 회원 목록 조회 및 관리
- 사용자 권한 관리 (일반 ↔ 관리자)
- 계정 활성화/비활성화
- 비밀번호 초기화 (임시 비밀번호 발급)
- 회원 삭제 (관련 데이터 함께 삭제)

### 📊 데이터 관리
- 실시간 백그라운드 데이터 수집
- 프로그레스 추적 및 상태 모니터링
- 데이터베이스 마이그레이션 자동화

## 기술 스택

- **Backend**: Flask 2.3+ (Python)
- **Database**: SQLite (WAL mode)
- **ORM**: Flask-SQLAlchemy 3.0+
- **Authentication**: Flask-Login
- **Security**: Flask-WTF (CSRF), Werkzeug (Password Hashing)
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **HTTP Client**: Requests with caching
- **HTML Parsing**: BeautifulSoup4

## 설치 및 실행

### 1. 저장소 클론
```bash
git clone <repository-url>
cd flask_starter
```

### 2. 가상환경 생성 및 활성화
```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# 또는
.venv\Scripts\activate     # Windows
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 데이터베이스 초기화
```bash
# 데이터베이스 테이블 생성
python scripts/init_db.py

# 데이터베이스 마이그레이션 (새 컬럼 추가)
python scripts/migrate.py
```

### 5. 애플리케이션 실행

#### 🚀 쉘 스크립트 사용 (권장)
```bash
# 실행 권한 부여 (최초 1회)
chmod +x start.sh

# 대화형 메뉴 모드 (권장)
./start.sh menu

# 직접 실행 모드
./start.sh local    # 로컬 개발 환경
./start.sh nas      # NAS 환경 (외부 접속 허용)
./start.sh dev      # 개발 환경 (기본값)
./start.sh prod     # 프로덕션 환경

# 백그라운드 실행 및 관리
./start.sh bg       # 백그라운드에서 NAS 서버 시작
./start.sh status   # 서버 상태 확인
./start.sh stop     # 서버 중지

# 도움말 보기
./start.sh help
```

#### 📝 수동 실행 방법

##### 로컬 개발 환경 (맥/윈도우)
```bash
# 기본값 (development 모드)
python run.py

# 또는 명시적으로 development 모드 지정
FLASK_ENV=development python run.py

# 또는 전용 스크립트 사용
python run_local.py
```
애플리케이션이 `http://127.0.0.1:5000`에서 실행됩니다.

##### NAS 환경 (외부 접속 허용)
```bash
# NAS 모드로 실행
FLASK_ENV=nas python run.py

# 또는 전용 스크립트 사용
python run_nas.py
```
애플리케이션이 `http://0.0.0.0:8080`에서 실행됩니다.

##### 프로덕션 환경
```bash
# 프로덕션 모드로 실행
FLASK_ENV=production python run.py
```

## 프로젝트 구조

```
flask_starter/
├── app/                    # 메인 애플리케이션 패키지
│   ├── __init__.py        # 앱 팩토리
│   ├── config.py          # 설정 파일
│   ├── extensions.py      # Flask 확장
│   ├── models.py          # 데이터베이스 모델
│   ├── routes.py          # 라우트 정의
│   ├── services/          # 비즈니스 로직
│   │   ├── analyzer.py    # 데이터 분석 서비스
│   │   ├── lotto_fetcher.py # 데이터 수집 서비스
│   │   ├── recommender.py # 추천 서비스
│   │   └── updater.py     # 데이터 업데이트 서비스
│   ├── static/            # 정적 파일 (CSS, JS)
│   └── templates/         # HTML 템플릿
├── scripts/               # 유틸리티 스크립트
│   ├── init_db.py         # 데이터베이스 초기화
│   ├── migrate.py         # 데이터베이스 마이그레이션
│   ├── update_all.py      # 전체 데이터 업데이트
│   └── update_rounds.py   # 회차별 데이터 업데이트
├── instance/              # 인스턴스별 파일 (데이터베이스 등)
├── requirements.txt       # Python 의존성
├── run.py                 # 애플리케이션 실행 파일
└── wsgi.py               # WSGI 설정
```

## 관리자 설정

### 첫 번째 관리자 계정 생성

1. **일반 사용자로 회원가입**
   ```
   http://localhost:5000/register
   ```

2. **데이터베이스에서 관리자 권한 부여**
   ```bash
   cd flask_starter
   sqlite3 instance/lotto.db "UPDATE users SET is_admin = 1 WHERE username = '사용자명';"
   ```

3. **관리자 권한 확인**
   ```bash
   sqlite3 instance/lotto.db "SELECT username, email, is_admin FROM users WHERE is_admin = 1;"
   ```

4. **관리자 기능 접근**
   - 관리자 계정으로 로그인
   - 상단 네비게이션에서 "🔧 관리자" 메뉴 클릭
   - 관리자 대시보드: `/admin`
   - 회원 관리: `/admin/users`

### 추가 관리자 지정
관리자로 로그인 후 회원 관리 페이지에서 다른 사용자를 관리자로 지정할 수 있습니다.

## API 엔드포인트

### 🏠 기본 페이지
- `GET /` - 메인 대시보드
- `GET /health` - 헬스 체크
- `GET /info` - 로또 정보 조회
- `GET /strategy` - 전략 분석 (로그인 필요)
- `GET /purchases` - 구매 이력 (로그인 필요)
- `GET /crawling` - 데이터 수집 (로그인 필요)

### 🔐 인증 엔드포인트
- `GET/POST /login` - 로그인
- `GET/POST /register` - 회원가입
- `GET /logout` - 로그아웃
- `GET/POST /forgot-password` - 비밀번호 찾기
- `GET/POST /reset-password/<token>` - 비밀번호 재설정

### 🛡️ 관리자 엔드포인트
- `GET /admin` - 관리자 대시보드
- `GET /admin/users` - 회원 관리
- `POST /admin/users/<id>/toggle-admin` - 관리자 권한 토글
- `POST /admin/users/<id>/toggle-active` - 계정 활성화 토글
- `POST /admin/users/<id>/reset-password` - 비밀번호 초기화
- `POST /admin/users/<id>/delete` - 회원 삭제

### 📊 데이터 API
- `GET /api/draw/<round>` - 특정 회차 당첨번호
- `GET /api/shops/<round>` - 특정 회차 당첨 판매점
- `GET /api/crawling-progress` - 크롤링 진행상황
- `POST /api/check-username` - 사용자명 중복 체크
- `POST /api/check-password-strength` - 비밀번호 강도 체크

## 보안 기능

### 🔐 인증 보안
- **비밀번호 해싱**: Werkzeug를 사용한 안전한 비밀번호 저장
- **로그인 시도 제한**: 5회 실패시 15분간 계정 잠금
- **세션 보안**: HttpOnly, SameSite 쿠키 설정
- **CSRF 보호**: 모든 폼에 CSRF 토큰 적용

### 🛡️ 비밀번호 정책
- **최소 8자** 이상
- **대소문자, 숫자, 특수문자** 필수 포함
- **실시간 강도 검증** 및 시각적 피드백
- **안전한 재설정** 기능 (토큰 기반)

### ⚙️ 환경 설정

#### 개발 환경
```bash
FLASK_ENV=development python run.py
# - DEBUG: True
# - HOST: 127.0.0.1
# - PORT: 5000
```

#### NAS 환경
```bash
FLASK_ENV=nas python run.py
# - DEBUG: True
# - HOST: 0.0.0.0 (외부 접속 허용)
# - PORT: 8080
```

#### 프로덕션 환경
```bash
FLASK_ENV=production python run.py
# - DEBUG: False
# - HOST: 0.0.0.0
# - PORT: 8080
# - SESSION_COOKIE_SECURE: True
```

### 🔑 중요 환경변수
- `SECRET_KEY`: Flask 세션 암호화 키 (프로덕션에서 필수 변경)
- `FLASK_ENV`: 실행 환경 (development/nas/production)
- `WTF_CSRF_TIME_LIMIT`: CSRF 토큰 만료시간 (기본: 1시간)
- `PERMANENT_SESSION_LIFETIME`: 세션 만료시간 (기본: 2시간)

## 데이터베이스 관리

### 초기화
```bash
python scripts/init_db.py
```

### 마이그레이션
```bash
python scripts/migrate.py
```

### 데이터 업데이트
```bash
# 전체 데이터 업데이트 (1회차부터 최신까지)
python scripts/update_all.py

# 누락된 회차만 업데이트
python scripts/update_rounds.py

# 웹 인터페이스 사용 (권장)
# http://localhost:5000/crawling
# - 실시간 진행상황 모니터링
# - 백그라운드 처리
# - 오류 시 자동 복구
```

## 개발 가이드

### 📁 프로젝트 구조
```
flask_starter/
├── app/
│   ├── __init__.py          # 앱 팩토리 (Flask 앱 생성)
│   ├── config.py            # 환경별 설정 클래스
│   ├── extensions.py        # Flask 확장 (SQLAlchemy, Login, CSRF)
│   ├── models.py           # 데이터베이스 모델
│   ├── routes.py           # 라우트 및 뷰 함수
│   ├── services/           # 비즈니스 로직 서비스
│   │   ├── analyzer.py     # 로또 데이터 분석
│   │   ├── lotto_fetcher.py # 데이터 수집 (크롤링)
│   │   ├── lottery_checker.py # 당첨 결과 확인
│   │   ├── recommendation_manager.py # 추천 번호 관리
│   │   ├── recommender.py  # 번호 추천 알고리즘
│   │   └── updater.py      # 데이터 업데이트 로직
│   ├── static/             # CSS, JS 등 정적 파일
│   └── templates/          # Jinja2 HTML 템플릿
│       └── admin/          # 관리자 전용 템플릿
├── scripts/                # 유틸리티 스크립트
├── instance/               # 인스턴스별 파일 (데이터베이스)
└── requirements.txt        # Python 의존성
```

### 🔧 데이터베이스 모델
- **User**: 사용자 정보 및 권한
- **Draw**: 로또 회차별 당첨번호
- **WinningShop**: 당첨 판매점 정보
- **Purchase**: 사용자별 구매 기록
- **RecommendationSet**: AI 추천번호 저장
- **PasswordResetToken**: 비밀번호 재설정 토큰

### 🎨 코드 스타일
- **PEP 8** Python 코딩 스타일 준수
- **Type Hints** 사용 권장
- **Docstring** 함수/클래스 문서화
- **의미있는 변수명** 사용

### 🧪 테스트
```bash
# 테스트 실행 (테스트 파일이 있는 경우)
python -m pytest

# 커버리지 확인
python -m pytest --cov=app
```

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 🚨 문제 해결

### 포트 충돌 해결
앱이 자동으로 포트 충돌을 감지하고 해결합니다:
- macOS에서 AirPlay가 5000번 포트 사용시 자동 우회
- 사용 가능한 포트로 자동 변경

### 데이터베이스 오류 해결
```bash
# 데이터베이스 재초기화
rm instance/lotto.db
python scripts/init_db.py

# 마이그레이션 실행
python scripts/migrate.py
```

### 관리자 권한 오류
```bash
# 관리자 권한 확인
sqlite3 instance/lotto.db "SELECT username, is_admin FROM users;"

# 관리자 권한 부여
sqlite3 instance/lotto.db "UPDATE users SET is_admin = 1 WHERE username = '사용자명';"
```

## 📞 문의사항

프로젝트에 대한 질문이나 제안사항이 있으시면 이슈를 생성해 주세요.

### 자주 묻는 질문
- **Q**: 관리자 계정은 어떻게 만드나요?
  **A**: 일반 회원가입 후 데이터베이스에서 `is_admin = 1`로 설정하세요.

- **Q**: 비밀번호를 잊어버렸어요.
  **A**: 로그인 페이지에서 '비밀번호 찾기'를 클릭하거나, 관리자가 임시 비밀번호를 발급할 수 있습니다.

- **Q**: 데이터가 업데이트되지 않아요.
  **A**: 관리자로 로그인 후 '데이터 크롤링' 페이지에서 수동으로 업데이트할 수 있습니다.
