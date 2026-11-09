from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base


class CustomerCredit(Base):
    __tablename__ = "customer_credits"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    amount = Column(Float, nullable=False)
    credit_type = Column(String, nullable=False)  # "add" or "remove"
    staff_name = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)

    customer = relationship("Customer")
