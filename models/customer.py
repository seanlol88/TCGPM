from sqlalchemy import Column, Integer, String
from models.base import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    email = Column(String, nullable=True)

    @property
    def full_name(self):
        first = self.first_name or ''
        last = self.last_name or ''
        return f"{first} {last}".strip()
