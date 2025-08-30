import os


class Config:
    SECRET_KEY = "dev"  # override in production or via environment


class DevelopmentConfig(Config):
    DEBUG = True
    HOST = "127.0.0.1"  # 로컬 개발용
    PORT = 5000


class NASConfig(Config):
    DEBUG = True
    HOST = "0.0.0.0"  # 외부 접속 허용
    PORT = 8080


class ProductionConfig(Config):
    DEBUG = False
    HOST = "0.0.0.0"
    PORT = 8080


# 환경별 설정 매핑
config = {
    'development': DevelopmentConfig,
    'nas': NASConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
