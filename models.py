# models.py

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class User(Base):
    """Пользователи системы (владельцы магазинов)."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)  # ← ДОБАВЛЕНО
    password_hash = Column(String, nullable=False)  # ← Переименовано для согласованности
    store_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    products = relationship("Product", back_populates="user", cascade="all, delete-orphan")
    sales_history = relationship("SalesHistory", back_populates="user", cascade="all, delete-orphan")


class Product(Base):
    """Товары в системе."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sku = Column(String, nullable=False, index=True)  # Артикул
    name = Column(String, nullable=False)  # Название товара
    current_stock = Column(Float, default=0.0)  # Текущий остаток
    unit_price = Column(Float, default=0.0)  # Цена за единицу
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    user = relationship("User", back_populates="products")
    sales_history = relationship("SalesHistory", back_populates="product", cascade="all, delete-orphan")
    forecasts = relationship("Forecast", back_populates="product", cascade="all, delete-orphan")


class SalesHistory(Base):
    """История продаж."""
    __tablename__ = "sales_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    date = Column(Date, nullable=False, index=True)  # Дата продажи
    quantity_sold = Column(Float, nullable=False)  # Кол-во проданного
    sale_price = Column(Float, nullable=False)  # Цена продажи
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    user = relationship("User", back_populates="sales_history")
    product = relationship("Product", back_populates="sales_history")


class Forecast(Base):
    """Прогнозы продаж (результаты Prophet)."""
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    forecast_date = Column(Date, nullable=False, index=True)  # Дата прогноза
    predicted_quantity = Column(Float, nullable=False)  # Прогнозируемое кол-во продаж
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    product = relationship("Product", back_populates="forecasts")
