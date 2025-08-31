import os


class Config:
    SECRET_KEY = "dev"  # override in production or via environment

    # Session security settings
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True  # Prevent XSS attacks
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
    PERMANENT_SESSION_LIFETIME = 7200  # 2 hours in seconds

    # WTF/CSRF settings
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour


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

    # Production security settings
    SESSION_COOKIE_SECURE = True  # HTTPS only in production


# 환경별 설정 매핑
config = {
    'development': DevelopmentConfig,
    'nas': NASConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
