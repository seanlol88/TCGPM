"""Migration script to add permissions column to the staff table.

- Adds the `permissions` TEXT column if it doesn't exist.
- Sets the first staff member (Admin) to full admin permissions.
- Sets all other staff members to default (restricted) permissions.
"""
import json
import sqlite3
import os
from models.staff import ADMIN_PERMISSIONS, DEFAULT_PERMISSIONS

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "app.db")


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. Nothing to migrate.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if permissions column already exists
    cursor.execute("PRAGMA table_info(staff)")
    columns = [row[1] for row in cursor.fetchall()]

    if "permissions" in columns:
        print("Permissions column already exists. Skipping migration.")
        conn.close()
        return

    # Add the permissions column
    print("Adding 'permissions' column to staff table...")
    cursor.execute("ALTER TABLE staff ADD COLUMN permissions TEXT")

    # Get all staff members
    cursor.execute("SELECT id, name FROM staff ORDER BY id")
    staff_rows = cursor.fetchall()

    for staff_id, name in staff_rows:
        # First staff member (typically Admin) gets full admin permissions
        if staff_id == 1:
            perms = ADMIN_PERMISSIONS
            role = "Admin (full access)"
        else:
            perms = DEFAULT_PERMISSIONS
            role = "Staff (restricted)"
        cursor.execute(
            "UPDATE staff SET permissions = ? WHERE id = ?",
            (json.dumps(perms), staff_id),
        )
        print(f"  Set {name} (id={staff_id}) -> {role}")

    conn.commit()
    conn.close()
    print("Migration complete!")


if __name__ == "__main__":
    migrate()
