from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class AdministrativeLevel(Base):
    __tablename__ = "administrative_levels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(20), unique=True, nullable=False)

    # Relationships
    administrative_areas = relationship(
        "Administrative", back_populates="level"
    )


class Administrative(Base):
    __tablename__ = "administrative"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(Text, nullable=False, index=True)
    name = Column(Text, nullable=False)
    level_id = Column(
        Integer, ForeignKey("administrative_levels.id"), nullable=False
    )
    parent_id = Column(Integer, ForeignKey("administrative.id"), nullable=True)
    path = Column(Text, nullable=False)

    # Relationships
    level = relationship(
        "AdministrativeLevel", back_populates="administrative_areas"
    )
    parent = relationship("Administrative", remote_side=[id])
    children = relationship("Administrative", overlaps="parent")
    user_administrative = relationship(
        "UserAdministrative", back_populates="administrative"
    )
    customer_administrative = relationship(
        "CustomerAdministrative", back_populates="administrative"
    )


class UserAdministrative(Base):
    __tablename__ = "user_administrative"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    administrative_id = Column(
        Integer, ForeignKey("administrative.id"), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="user_administrative")
    administrative = relationship(
        "Administrative", back_populates="user_administrative"
    )


class CustomerAdministrative(Base):
    __tablename__ = "customer_administrative"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    administrative_id = Column(
        Integer, ForeignKey("administrative.id"), nullable=False
    )

    # Relationships
    customer = relationship(
        "Customer", back_populates="customer_administrative"
    )
    administrative = relationship(
        "Administrative", back_populates="customer_administrative"
    )
