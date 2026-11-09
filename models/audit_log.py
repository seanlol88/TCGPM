from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from models.base import Base


class AuditLog(Base):
    """General-purpose audit log for all app changes (products, customers, categories, subcategories, settings)."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    entity_type = Column(String(50), nullable=False)  # e.g., "product", "customer", "category", "subcategory", "settings"
    entity_id = Column(Integer, nullable=True)  # ID of the affected entity
    action = Column(Text, nullable=False)  # Description of the change
    staff_name = Column(String, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)
