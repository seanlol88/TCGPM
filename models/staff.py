from sqlalchemy import Column, Integer, String, Boolean, Text
from models.base import Base
import json


# Default permissions for a new staff member (general staff role)
DEFAULT_PERMISSIONS = {
    "view_orders": True,
    "create_orders": True,
    "edit_orders": True,
    "delete_orders": False,
    "view_customers": True,
    "edit_customers": True,
    "view_inventory": True,
    "edit_inventory": False,
    "view_categories": True,
    "edit_categories": False,
    "view_payments": True,
    "edit_payments": True,
    "view_distributors": True,
    "edit_distributors": False,
    "view_audit_log": False,
    "manage_settings": False,
    "manage_backups": False,
    "manage_staff": False,
    "manage_system": False,
}

# Full admin permissions (all True)
ADMIN_PERMISSIONS = {k: True for k in DEFAULT_PERMISSIONS}


class Staff(Base):
    """Staff member with a 4-digit PIN for login and role-based permissions."""
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    pin = Column(String(4), nullable=False, unique=True)  # 4-digit PIN
    active = Column(Boolean, default=True)  # Whether this staff account is active
    permissions = Column(Text, nullable=True)  # JSON string of permission key-value pairs

    def get_permissions(self) -> dict:
        """Return permissions as a dict. Falls back to ADMIN_PERMISSIONS for legacy records."""
        if self.permissions:
            try:
                return json.loads(self.permissions)
            except (json.JSONDecodeError, TypeError):
                pass
        return dict(ADMIN_PERMISSIONS)

    def has_permission(self, key: str) -> bool:
        """Check if this staff member has a specific permission."""
        perms = self.get_permissions()
        return perms.get(key, False)

    def __repr__(self):
        return f"<Staff(name='{self.name}', active={self.active})>"
