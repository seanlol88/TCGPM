from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from datetime import datetime
from models.base import Base


class OrderLog(Base):
    __tablename__ = "order_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    action = Column(Text, nullable=False)  # Description of the change
    staff_name = Column(String, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)
