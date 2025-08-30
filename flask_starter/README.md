# Flask 로또 분석 애플리케이션

## 프로젝트 개요

이 프로젝트는 Flask 기반의 로또 번호 분석 및 추천 시스템입니다. 로또 데이터를 수집하고 분석하여 사용자에게 유용한 정보를 제공합니다.

## 주요 기능

- 로또 당첨 번호 데이터 수집 및 저장
- 당첨 번호 통계 분석
- 번호 추천 알고리즘
- 웹 기반 사용자 인터페이스
- 데이터베이스 관리 및 마이그레이션

## 기술 스택

- **Backend**: Flask (Python)
- **Database**: SQLite
- **Frontend**: HTML, CSS, JavaScript
- **기타**: SQLAlchemy (ORM)

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
python scripts/init_db.py
```

### 5. 애플리케이션 실행
```bash
python run.py
```

애플리케이션이 `http://127.0.0.1:5000`에서 실행됩니다.

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

## API 엔드포인트

### 기본 엔드포인트
- `GET /` - 메인 페이지
- `GET /health` - 헬스 체크
- `GET /info` - 로또 정보 페이지
- `GET /strategy` - 전략 분석 페이지
- `GET /crawling` - 데이터 수집 페이지
- `GET /draw_info` - 추첨 정보 페이지

## 설정

### 개발 환경
기본 설정은 개발용으로 구성되어 있습니다. 다음 환경 변수를 설정할 수 있습니다:

- `SECRET_KEY`: 애플리케이션 시크릿 키
- `DATABASE_URL`: 데이터베이스 연결 URL
- `FLASK_ENV`: Flask 환경 (development/production)

### 배포 시 주의사항
1. `SECRET_KEY`를 안전한 값으로 변경하세요
2. 프로덕션 데이터베이스 사용을 권장합니다
3. 적절한 로깅 설정을 구성하세요

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
# 전체 데이터 업데이트
python scripts/update_all.py

# 특정 회차 데이터 업데이트
python scripts/update_rounds.py
```

## 개발 가이드

### 코드 스타일
- PEP 8 Python 코딩 스타일을 따릅니다
- 함수와 클래스에 적절한 docstring을 작성하세요
- 변수명은 의미가 명확하도록 작성하세요

### 테스트
```bash
# 테스트 실행 (테스트 파일이 있는 경우)
python -m pytest
```

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 문의사항

프로젝트에 대한 질문이나 제안사항이 있으시면 이슈를 생성해 주세요.
