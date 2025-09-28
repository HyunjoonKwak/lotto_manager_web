# 로또 용지 QR 인식 앱

로또 용지 QR 코드에서 번호를 자동으로 인식하고 웹 앱으로 전송하는 데스크톱 애플리케이션입니다.

## 주요 기능

### 📱 QR 코드 인식
- QR 코드에서 회차, 구매일 정보 추출
- 다양한 QR 포맷 지원 (파이프, URL, JSON, 숫자)
- 여러 검출 방법 자동 시도

### 🌐 웹 앱 연동
- EC2 웹 앱과 API 통신
- 구매 이력 자동 업로드
- 중복 데이터 방지
- 연결 상태 확인

## 설치 및 실행

### 1. 의존성 설치

```bash
# Tesseract OCR 설치 (macOS)
brew install tesseract

# Python 패키지 설치
cd lotto_ocr_app
pip install -r requirements.txt
```

### 2. 설정 확인

`config.py`에서 웹 앱 URL을 확인/수정:

```python
WEB_APP_URL = "http://127.0.0.1:5001"  # 로컬 개발
# WEB_APP_URL = "http://your-ec2-domain:8080"  # 프로덕션
```

### 3. 앱 실행

```bash
python main.py
```

## 사용법

### 기본 워크플로우

1. **이미지 선택**: "파일 선택" 버튼으로 로또 용지 사진 선택
2. **전체 처리**: "전체 처리" 버튼으로 OCR + QR 동시 인식
3. **결과 확인**: 탭에서 OCR 결과, QR 결과, 로그 확인
4. **연결 테스트**: 웹 앱 서버 연결 상태 확인
5. **데이터 업로드**: 인식된 데이터를 웹 앱으로 전송

### 개별 처리

- **OCR 처리**: 번호만 인식
- **QR 인식**: QR 코드만 인식
- **연결 테스트**: 서버 상태 확인

## 지원하는 이미지 형식

- JPG, JPEG
- PNG
- BMP
- TIFF

## OCR 인식 팁

### 📷 촬영 가이드
- **조명**: 밝고 균등한 조명 사용
- **각도**: 로또 용지를 정면에서 촬영
- **초점**: 번호가 선명하게 보이도록 초점 맞춤
- **배경**: 단색 배경이면 더 좋음

### 🖼️ 이미지 품질
- **해상도**: 최소 800x600 이상 권장
- **블러**: 흔들림 없이 선명하게
- **대비**: 번호와 배경의 대비가 뚜렷하게

## API 연동

### 업로드 데이터 형식

```json
{
  "games": [
    {
      "numbers": [1, 7, 15, 23, 33, 45],
      "type": "extracted",
      "confidence": 0.85
    }
  ],
  "round": 1234,
  "purchase_date": "2024-01-01",
  "source": "ocr_app",
  "qr_info": {
    "format": "pipe",
    "raw_data": "1234|20240101|1",
    "detection_method": "original"
  },
  "image_hash": "sha256...",
  "timestamp": "2024-01-01T12:00:00"
}
```

### 응답 형식

```json
{
  "success": true,
  "message": "2개 게임이 성공적으로 등록되었습니다",
  "purchases": [
    {
      "game": 1,
      "numbers": [1, 7, 15, 23, 33, 45],
      "round": 1234,
      "purchase_date": "2024-01-01"
    }
  ],
  "total_games": 2
}
```

## 문제 해결

### OCR 인식 안됨
- 이미지 품질 확인
- 조명 개선
- 다른 각도에서 재촬영

### QR 코드 인식 안됨
- QR 코드가 전체적으로 보이는지 확인
- 이미지가 너무 작지 않은지 확인
- QR 코드가 손상되지 않았는지 확인

### 서버 연결 실패
- 웹 앱이 실행 중인지 확인
- `config.py`의 URL이 정확한지 확인
- 방화벽 설정 확인

### 업로드 실패
- OCR 결과가 있는지 확인
- 번호가 올바르게 인식되었는지 확인
- 서버 로그 확인

## 개발자 정보

### 파일 구조

```
lotto_ocr_app/
├── main.py                  # GUI 메인 앱
├── config.py               # 설정
├── ocr_processor.py        # OCR 처리
├── qr_processor.py         # QR 코드 인식
├── image_preprocessor.py   # 이미지 전처리
├── api_client.py           # API 통신
├── requirements.txt        # 의존성
└── README.md              # 문서
```

### 주요 클래스

- `LottoOCRApp`: 메인 GUI 클래스
- `OCRProcessor`: OCR 처리 및 번호 추출
- `QRProcessor`: QR 코드 인식 및 파싱
- `ImagePreprocessor`: 이미지 전처리
- `APIClient`: 웹 앱 API 통신

## 향후 개선 사항

- [ ] 다중 이미지 일괄 처리
- [ ] 인식 정확도 향상을 위한 ML 모델 적용
- [ ] 사용자별 API 키 인증
- [ ] 설정 GUI 추가
- [ ] 처리 이력 저장
- [ ] 연금복권, 스피또 등 다른 복권 지원
