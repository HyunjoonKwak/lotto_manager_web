class Config:
    SECRET_KEY = "dev"  # override in production or via environment


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
