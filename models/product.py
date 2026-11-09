from sqlalchemy import Column, ForeignKey, Integer, String, Float, Date
from sqlalchemy.orm import relationship
from models.base import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    price = Column(Float, nullable=False, default=0.0)
    cost_price = Column(Float, nullable=False, default=0.0)
    max_per_order = Column(Integer, nullable=True)  # None means unlimited
    release_date = Column(Date, nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    subcategory_id = Column(Integer, ForeignKey("subcategories.id"), nullable=True)

    category = relationship("Category", backref="products")
    subcategory = relationship("Subcategory", back_populates="products")

    @property
    def profit_per_unit(self):
        """Calculate profit per unit (selling price - cost price)."""
        return self.price - self.cost_price

    @property
    def profit_margin(self):
        """Calculate profit margin percentage."""
        if self.price <= 0:
            return 0.0
        return ((self.price - self.cost_price) / self.price) * 100
