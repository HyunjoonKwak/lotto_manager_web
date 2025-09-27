from flask import Flask
from typing import Optional, Type


def create_app(config_class: Optional[Type] = None) -> Flask:
    """Application factory for the Flask app.

    Optionally loads a config object path (e.g., "app.config.Config").
    """
    app = Flask(__name__, instance_relative_config=True)

    # Default config
    app.config.from_mapping(
        SECRET_KEY="dev",  # replace in production or via environment
    )

    # Database: SQLite under instance folder as lotto.db
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", f"sqlite:///{app.instance_path}/lotto.db")
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

    # Load extra config if provided
    if config_class:
        app.config.from_object(config_class)

    # Ensure instance folder exists
    try:
        import os

        os.makedirs(app.instance_path, exist_ok=True)
    except Exception:
        # If the instance path cannot be created, continue without failing
        pass

    # Init extensions
    from .extensions import db, login_manager, csrf

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = '로그인이 필요합니다.'

    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return User.query.get(int(user_id))

    # Register blueprints
    from .routes import main_bp

    app.register_blueprint(main_bp)

    # Health check
    @app.get("/health")
    def healthcheck():  # type: ignore[unused-ignore]
        return {"status": "ok"}, 200

    return app
