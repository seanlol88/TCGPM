from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    order_date = Column(DateTime, nullable=False, default=datetime.now)
    total = Column(Float, nullable=False, default=0.0)
    deposit = Column(Float, nullable=False, default=0.0)
    staff_name = Column(String, nullable=True)
    picked_up = Column(Boolean, nullable=False, default=False)
    deleted = Column(Boolean, nullable=False, default=False)

    customer = relationship("Customer")
    items = relationship("OrderItem", back_populates="order")
    payments = relationship("Payment", back_populates="order")
    notes = relationship("OrderNote", back_populates="order")

    @property
    def balance(self):
        return self.total - self.deposit

    @property
    def pickup_progress(self):
        """Returns (picked_up_items, total_items) for display."""
        if not self.items:
            return 0, 0
        total = sum(item.quantity for item in self.items)
        picked = sum(item.picked_up_quantity for item in self.items)
        return picked, total

    @property
    def is_fully_picked_up(self):
        """Check if all items in the order are fully picked up."""
        picked, total = self.pickup_progress
        return total > 0 and picked >= total


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    picked_up_quantity = Column(Integer, nullable=False, default=0)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")

    @property
    def is_fully_picked_up(self):
        return self.picked_up_quantity >= self.quantity
