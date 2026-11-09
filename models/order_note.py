from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base


class OrderNote(Base):
    __tablename__ = "order_notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    text = Column(Text, nullable=False)
    staff_name = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    order = relationship("Order")
