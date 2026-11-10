"""Migration script to add setup_complete column to store_settings table."""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "database", "app.db")

if not os.path.exists(db_path):
    print("No database found. Skipping migration.")
    exit(0)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if column already exists
cursor.execute("PRAGMA table_info(store_settings)")
columns = [col[1] for col in cursor.fetchall()]

if "setup_complete" not in columns:
    cursor.execute("ALTER TABLE store_settings ADD COLUMN setup_complete BOOLEAN DEFAULT 0")
    conn.commit()
    print("Migration completed successfully. Added setup_complete column to store_settings.")
else:
    print("setup_complete column already exists. No migration needed.")

conn.close()
