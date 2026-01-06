# database.py

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Определяем путь к базе данных
# Если на Render — используем persistent disk, локально — текущую папку
if os.getenv('RENDER'):
    # На Render используем /data для persistent storage
    SQLITE_URL = "sqlite:////data/forecast_mvp.db"
else:
    # Локальная разработка
    SQLITE_URL = "sqlite:///./forecast_mvp.db"

# Создаем движок SQLAlchemy
engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False}  # Нужно для SQLite
)

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей
Base = declarative_base()


# Dependency для FastAPI
def get_db():
    """
    Генератор сессий базы данных для FastAPI.
    Использование:
    
    @app.get("/endpoint")
    def endpoint(db: Session = Depends(get_db)):
        ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()