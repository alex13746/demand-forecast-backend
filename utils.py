# utils.py (ФИНАЛЬНАЯ ВЕРСИЯ)

import os
import uuid
from datetime import datetime
from typing import Optional

from passlib.context import CryptContext
from fastapi import UploadFile

# Настройка хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def parse_date(date_str: str) -> Optional[datetime.date]:
    """
    Преобразует строку с датой в объект date.
    Поддерживает форматы: DD.MM.YYYY, YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY
    """
    if not date_str or not isinstance(date_str, str):
        return None
    
    date_str = date_str.strip()
    
    formats = [
        "%d.%m.%Y",    # 01.01.2024
        "%Y-%m-%d",    # 2024-01-01
        "%d/%m/%Y",    # 01/01/2024
        "%d-%m-%Y",    # 01-01-2024
        "%Y/%m/%d"     # 2024/01/01
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except (ValueError, TypeError):
            continue
    
    return None


def get_password_hash(password: str) -> str:
    """Хеширует пароль с использованием bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет соответствие пароля хешу"""
    return pwd_context.verify(plain_password, hashed_password)


def save_uploaded_csv(file: UploadFile) -> str:
    """
    Сохраняет загруженный CSV-файл во временное хранилище.
    Возвращает путь к файлу.
    """
    # Проверка расширения
    if not file.filename.lower().endswith('.csv'):
        raise ValueError("Требуется CSV файл. Если у вас Excel — сохраните как CSV перед загрузкой.")
    
    # Генерация уникального имени
    filename = f"{uuid.uuid4()}.csv"
    file_path = os.path.join("/tmp", filename)
    
    # Сохранение файла
    try:
        with open(file_path, "wb") as f:
            contents = file.file.read()
            f.write(contents)
    finally:
        file.file.close()
    
    return file_path