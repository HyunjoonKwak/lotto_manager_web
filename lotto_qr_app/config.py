"""
Configuration settings for Lotto OCR App
"""

# 서버 설정
SERVERS = {
    "local": {
        "name": "로컬 서버",
        "url": "http://127.0.0.1:5001",
        "description": "로컬 개발 서버 (5001 포트)"
    },
    "remote": {
        "name": "EC2 원격 서버",
        "url": "http://43.201.26.3:8080",
        "description": "AWS EC2 프로덕션 서버 (8080 포트)"
    }
}

# 기본 서버 설정
DEFAULT_SERVER = "local"
WEB_APP_URL = SERVERS[DEFAULT_SERVER]["url"]
API_ENDPOINT = f"{WEB_APP_URL}/api/purchases"

# 앱 버전
APP_VERSION = "1.2.0"
APP_NAME = "로또 QR 인식 앱"

# OCR 설정
TESSERACT_CONFIG = '--psm 8 -c tessedit_char_whitelist=0123456789'
TESSERACT_PATH = '/opt/homebrew/bin/tesseract'  # macOS Homebrew 경로

# 이미지 처리 설정
MAX_IMAGE_SIZE = (1920, 1080)
MIN_NUMBER_SIZE = 20  # 최소 번호 크기 (픽셀)

# 로또 번호 검증
LOTTO_MIN_NUMBER = 1
LOTTO_MAX_NUMBER = 45
NUMBERS_PER_GAME = 6

# GUI 설정
WINDOW_SIZE = "1200x1250"
SUPPORTED_FORMATS = [
    ("로또 용지 사진 (JPG, PNG)", "*.jpg *.jpeg *.png"),
    ("모든 이미지 파일", "*.jpg *.jpeg *.png *.bmp *.tiff *.gif"),
    ("모든 파일", "*.*")
]
