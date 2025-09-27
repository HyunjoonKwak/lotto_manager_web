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

        # Check existing columns for users table
        inspector = inspect(db.engine)
        existing_users_columns = [col['name'] for col in inspector.get_columns('users')]

        # Add new columns to users table if they don't exist
        users_columns_to_add = [
            ('failed_login_attempts', 'INTEGER DEFAULT 0'),
            ('last_failed_login', 'DATETIME'),
            ('account_locked_until', 'DATETIME')
        ]

        with db.engine.connect() as connection:
            for column_name, column_def in users_columns_to_add:
                if column_name not in existing_users_columns:
                    try:
                        connection.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_def}"))
                        connection.commit()
                        print(f"Added {column_name} column to users table")
                    except Exception as e:
                        print(f"Error adding {column_name} column to users: {e}")
                else:
                    print(f"users.{column_name} column already exists")

            # Check existing columns for purchases table
            try:
                existing_purchases_columns = [col['name'] for col in inspector.get_columns('purchases')]

                # Add new columns to purchases table for QR/OCR support
                purchases_columns_to_add = [
                    ('recognition_method', 'VARCHAR(10)'),
                    ('confidence_score', 'FLOAT'),
                    ('source', 'VARCHAR(50)')
                ]

                for column_name, column_def in purchases_columns_to_add:
                    if column_name not in existing_purchases_columns:
                        try:
                            connection.execute(text(f"ALTER TABLE purchases ADD COLUMN {column_name} {column_def}"))
                            connection.commit()
                            print(f"Added {column_name} column to purchases table")
                        except Exception as e:
                            print(f"Error adding {column_name} column to purchases: {e}")
                    else:
                        print(f"purchases.{column_name} column already exists")

            except Exception as e:
                print(f"Error checking purchases table (table may not exist yet): {e}")
                # This is okay - the table will be created by db.create_all()

        # Create all tables (will only create missing ones)
        db.create_all()
        print("Database migration completed.")


if __name__ == "__main__":
    main()
