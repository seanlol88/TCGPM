"""Migration script to add recovery_token_hash column to store_settings table."""
import sqlite3
import os

db_path = os.path.join("database", "app.db")

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}. Skipping migration.")
    exit(0)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(store_settings)")
columns = [col[1] for col in cursor.fetchall()]

if "recovery_token_hash" not in columns:
    cursor.execute("ALTER TABLE store_settings ADD COLUMN recovery_token_hash VARCHAR(64)")
    conn.commit()
    print("Migration completed successfully: added recovery_token_hash column to store_settings.")
else:
    print("Column 'recovery_token_hash' already exists. No migration needed.")

conn.close()
