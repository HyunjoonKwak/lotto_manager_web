"""
Configuration settings for Lotto OCR App
"""

# API 설정
WEB_APP_URL = "http://127.0.0.1:5001"  # 로컬 개발
# WEB_APP_URL = "http://your-ec2-domain:8080"  # 프로덕션
API_ENDPOINT = f"{WEB_APP_URL}/api/purchases/upload"

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
WINDOW_SIZE = "800x600"
SUPPORTED_FORMATS = [
    ("로또 용지 사진 (JPG, PNG)", "*.jpg *.jpeg *.png"),
    ("모든 이미지 파일", "*.jpg *.jpeg *.png *.bmp *.tiff *.gif"),
    ("모든 파일", "*.*")
]
