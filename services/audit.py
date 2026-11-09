"""Audit service for logging all app changes."""
from models.base import SessionLocal
from models.audit_log import AuditLog


def log_change(entity_type: str, entity_id: int, action: str, staff_name: str = None):
    """Log a change to the audit trail.
    
    Args:
        entity_type: Type of entity changed (product, customer, category, subcategory, settings)
        entity_id: ID of the affected entity
        action: Human-readable description of the change
        staff_name: Name of the staff member who made the change
    """
    db = SessionLocal()
    try:
        entry = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            staff_name=staff_name,
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Audit log error: {e}")
    finally:
        db.close()
