from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from models.base import Base


class Distributor(Base):
    __tablename__ = "distributors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)  # Distributor company name
    store_rep = Column(String, nullable=True, default=None)  # Store representative name
    store_rep_phone = Column(String, nullable=True, default=None)  # Store rep phone number
    store_rep_email = Column(String, nullable=True, default=None)  # Store rep email
    phone = Column(String, nullable=True, default=None)  # General phone number
    email = Column(String, nullable=True, default=None)  # General email
    website = Column(String, nullable=True, default=None)  # Distributor website

    # Relationship to products (many-to-many via distributor_products)
    products = relationship("Product", secondary="distributor_products", back_populates="distributors")


class ProductDistributor(Base):
    """Association table for many-to-many relationship between products and distributors."""
    __tablename__ = "distributor_products"

    product_id = Column(Integer, ForeignKey("products.id"), primary_key=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), primary_key=True)
