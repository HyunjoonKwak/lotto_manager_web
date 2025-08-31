import os
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from sqlalchemy import text


def main() -> None:
    app = create_app()
    with app.app_context():
        from sqlalchemy import text, inspect

        # Check existing columns
        inspector = inspect(db.engine)
        existing_columns = [col['name'] for col in inspector.get_columns('users')]

        # Add new columns if they don't exist
        columns_to_add = [
            ('failed_login_attempts', 'INTEGER DEFAULT 0'),
            ('last_failed_login', 'DATETIME'),
            ('account_locked_until', 'DATETIME')
        ]

        with db.engine.connect() as connection:
            for column_name, column_def in columns_to_add:
                if column_name not in existing_columns:
                    try:
                        connection.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_def}"))
                        connection.commit()
                        print(f"Added {column_name} column to users table")
                    except Exception as e:
                        print(f"Error adding {column_name} column: {e}")
                else:
                    print(f"{column_name} column already exists")

        # Create all tables (will only create missing ones)
        db.create_all()
        print("Database migration completed.")


if __name__ == "__main__":
    main()
