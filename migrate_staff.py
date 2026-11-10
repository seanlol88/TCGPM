"""
Migration script to add the staff table and seed default staff members.
Run this once after deploying the new staff login feature.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import inspect
from models.base import engine, init_db, SessionLocal
from models.staff import Staff

def migrate():
    # Ensure all tables are created (including new staff table)
    init_db()
    
    # Check if staff table exists
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if "staff" not in tables:
        print("Staff table does not exist. It will be created on next app start.")
        print("Run the app once to create the table, then run this script again to seed data.")
        return
    
    db = SessionLocal()
    try:
        # Check if any staff already exist
        existing_count = db.query(Staff).count()
        if existing_count > 0:
            print(f"Staff table already has {existing_count} staff members. Skipping seed.")
            # List existing staff
            staff_list = db.query(Staff).all()
            for s in staff_list:
                print(f"  - {s.name} (PIN: {s.pin}, active: {s.active})")
            return
        
        # Seed default staff members
        default_staff = [
            Staff(name="Admin", pin="0000", active=True),
        ]
        
        for staff in default_staff:
            db.add(staff)
        db.commit()
        
        print("Seeded default staff members:")
        for staff in default_staff:
            print(f"  - {staff.name} (PIN: {staff.pin})")
        print("\nIMPORTANT: Change the default PINs after first login!")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding staff: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
