from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_type = Column(String, nullable=False, default="cash")  # cash, eftpos, other
    staff_name = Column(String, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)

    order = relationship("Order", back_populates="payments")
