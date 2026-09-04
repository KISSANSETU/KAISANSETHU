import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "gramai.db")


def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def add_column_if_missing(cursor, table_name, column_name, column_type):
    if not column_exists(cursor, table_name, column_name):
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )
        print(f"ADDED: {table_name}.{column_name}")
    else:
        print(f"EXISTS: {table_name}.{column_name}")


def migrate():
    print("Opening database:", DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ---------------------------------------------------------
    # Add quality verification fields to listings
    # ---------------------------------------------------------

    add_column_if_missing(
        cursor,
        "listings",
        "quality_grade",
        "TEXT"
    )

    add_column_if_missing(
        cursor,
        "listings",
        "quality_confidence",
        "REAL"
    )

    add_column_if_missing(
        cursor,
        "listings",
        "quality_verified",
        "INTEGER DEFAULT 0"
    )

    add_column_if_missing(
        cursor,
        "listings",
        "quality_certificate",
        "TEXT"
    )

    add_column_if_missing(
        cursor,
        "listings",
        "quality_image",
        "TEXT"
    )

    # ---------------------------------------------------------
    # Geolocation information
    # ---------------------------------------------------------

    add_column_if_missing(
        cursor,
        "listings",
        "latitude",
        "REAL"
    )

    add_column_if_missing(
        cursor,
        "listings",
        "longitude",
        "REAL"
    )

    add_column_if_missing(
        cursor,
        "listings",
        "location_verified",
        "INTEGER DEFAULT 0"
    )

    add_column_if_missing(
        cursor,
        "listings",
        "location_source",
        "TEXT"
    )

    # ---------------------------------------------------------
    # Quality verification history
    # ---------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quality_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER,

            crop TEXT,

            predicted_grade TEXT,

            confidence REAL,

            image_path TEXT,

            latitude REAL,

            longitude REAL,

            location_source TEXT,

            certificate_path TEXT,

            model_name TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    # ---------------------------------------------------------
    # Certificate records
    # ---------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quality_certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            verification_id INTEGER,

            certificate_number TEXT UNIQUE,

            farmer_id INTEGER,

            crop TEXT,

            grade TEXT,

            confidence REAL,

            latitude REAL,

            longitude REAL,

            certificate_path TEXT,

            issued_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(verification_id)
                REFERENCES quality_verifications(id),

            FOREIGN KEY(farmer_id)
                REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()

    print("")
    print("--------------------------------")
    print("QUALITY DATABASE MIGRATION DONE")
    print("--------------------------------")


if __name__ == "__main__":
    migrate()