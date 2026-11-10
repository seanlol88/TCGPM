"""Migration script to move timeout settings from per-staff to global store_settings."""
import sqlite3
import os

db_path = os.path.join("database", "app.db")

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}. Skipping migration.")
    exit(0)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Add timeout columns to store_settings if they don't exist
cursor.execute("PRAGMA table_info(store_settings)")
ss_columns = [col[1] for col in cursor.fetchall()]

added = []
if "timeout_enabled" not in ss_columns:
    cursor.execute("ALTER TABLE store_settings ADD COLUMN timeout_enabled BOOLEAN DEFAULT 0")
    added.append("store_settings.timeout_enabled")

if "timeout_seconds" not in ss_columns:
    cursor.execute("ALTER TABLE store_settings ADD COLUMN timeout_seconds INTEGER DEFAULT 1800")
    added.append("store_settings.timeout_seconds")

# Migrate: if any staff had timeout enabled, enable it globally with the minimum timeout value
if added:
    # Check if any staff had timeout enabled
    cursor.execute("PRAGMA table_info(staff)")
    staff_columns = [col[1] for col in cursor.fetchall()]
    
    if "timeout_enabled" in staff_columns:
        cursor.execute("SELECT COUNT(*) FROM staff WHERE timeout_enabled = 1")
        count = cursor.fetchone()[0]
        if count > 0:
            # Get the minimum timeout_seconds from enabled staff
            cursor.execute("SELECT MIN(timeout_seconds) FROM staff WHERE timeout_enabled = 1")
            min_timeout = cursor.fetchone()[0] or 1800
            cursor.execute("UPDATE store_settings SET timeout_enabled = 1, timeout_seconds = ?", (min_timeout,))
            print(f"Migrated timeout settings from {count} staff member(s). Global timeout: {min_timeout}s")

    # Drop per-staff timeout columns
    if "timeout_enabled" in staff_columns:
        # SQLite doesn't support DROP COLUMN before 3.35.0, so we'll just leave them (harmless)
        print("Note: Per-staff timeout columns left in place (harmless, no longer used).")

conn.commit()

if added:
    print(f"Migration completed successfully. Added columns: {', '.join(added)}")
else:
    print("All columns already exist. No migration needed.")

conn.close()
