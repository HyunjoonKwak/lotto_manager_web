from flask import Flask
from .config import Config
from .cache import cache
from .models import db
from flask_migrate import Migrate

migrate = Migrate()

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    import os
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    cache.init_app(app)
    migrate.init_app(app, db)

    from .api import api_bp
    from .web import web_bp
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(web_bp)

    return app
