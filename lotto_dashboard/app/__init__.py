import os
import sqlite3
from flask import Flask
from sqlalchemy import event
from sqlalchemy.engine import Engine
from .config import Config
from .extensions import db, cache
from .routes.dashboard import bp as dashboard_bp
from .routes.shops import bp as shops_bp
from .routes.api import bp as api_bp
from .routes.info import bp as info_bp
from .routes.strategy import bp as strategy_bp

# SQLite PRAGMA
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA busy_timeout=5000;")
        cur.close()

def create_app():
    app = Flask(__name__, instance_relative_config=True, template_folder='../templates', static_folder='../static')
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_object(Config())
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        db_path = os.path.join(app.instance_path, "lotto.db")
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path + "?check_same_thread=false"

    db.init_app(app)
    cache.init_app(app)

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(shops_bp, url_prefix="/shops")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(info_bp, url_prefix="/info")
    app.register_blueprint(strategy_bp, url_prefix="/strategy")

    with app.app_context():
        from . import models
        db.create_all()
    return app
