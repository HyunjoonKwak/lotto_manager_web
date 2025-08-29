from flask import Flask


def create_app(config_object: str | None = None) -> Flask:
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
    if config_object:
        app.config.from_object(config_object)

    # Ensure instance folder exists
    try:
        import os

        os.makedirs(app.instance_path, exist_ok=True)
    except Exception:
        # If the instance path cannot be created, continue without failing
        pass

    # Init extensions
    from .extensions import db

    db.init_app(app)

    # Register blueprints
    from .routes import main_bp

    app.register_blueprint(main_bp)

    # Health check
    @app.get("/health")
    def healthcheck():  # type: ignore[unused-ignore]
        return {"status": "ok"}, 200

    return app
