import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///lotto.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CACHE_TYPE = "FileSystemCache"
    CACHE_DIR = "/tmp/lotto_cache"
    CACHE_DEFAULT_TIMEOUT = 3600
