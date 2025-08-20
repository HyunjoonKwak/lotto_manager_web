import os, pathlib

# 프로젝트 루트: .../lotto
ROOT = pathlib.Path(__file__).resolve().parents[1]

# DB 경로: 환경변수 LOTTO_DB 우선, 없으면 프로젝트 내부 database/lotto.db
DB = os.environ.get("LOTTO_DB") or str(ROOT / "database" / "lotto.db")

# 로그/서버 설정
LOG_DIR = str(ROOT / "logs")
HOST = os.environ.get("LOTTO_HOST", "0.0.0.0")
PORT = int(os.environ.get("LOTTO_PORT", "8080"))
