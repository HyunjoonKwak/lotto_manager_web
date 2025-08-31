import os
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models import Example, Draw, WinningShop, Purchase, RecommendationSet


def main() -> None:
    app = create_app()
    os.makedirs(app.instance_path, exist_ok=True)
    with app.app_context():
        db.create_all()

        if not Example.query.first():
            db.session.add(Example(name="hello"))
            db.session.commit()

        # 테이블 생성 확인
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables_created = inspector.get_table_names()

        print(f"Database initialized at: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print(f"Tables created: {', '.join(tables_created)}")


if __name__ == "__main__":
    main()
