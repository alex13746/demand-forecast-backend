# database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Используем PostgreSQL на Render, SQLite локально
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'sqlite:///./forecast_mvp.db'  # Fallback для локальной разработки
)

# Если URL начинается с postgres://, меняем на postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
