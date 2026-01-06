# forecast_engine.py (ИСПРАВЛЕННАЯ ВЕРСИЯ)

import pandas as pd
from datetime import datetime
from typing import Dict
from sqlalchemy.orm import Session
from prophet import Prophet

from models import Product, SalesHistory, Forecast
from utils import parse_date


def process_sales_and_forecast(
    db: Session,
    user_id: int,
    file_path: str,
    separator: str = ","
) -> Dict[str, int]:
    """
    Основная логика MVP:
    1. Парсинг CSV
    2. Создание/обновление товаров
    3. Сохранение истории продаж
    4. Прогнозирование через Prophet
    """
    # Чтение CSV с обработкой кодировок
    try:
        df = pd.read_csv(file_path, sep=separator, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, sep=separator, encoding='cp1251')

    # Автоопределение колонок (гибкость!)
    column_mapping = {}
    for col in df.columns:
        col_lower = col.lower().strip()
        if 'дата' in col_lower or 'date' in col_lower:
            column_mapping['date'] = col
        elif 'артикул' in col_lower or 'sku' in col_lower or 'код' in col_lower:
            column_mapping['sku'] = col
        elif 'товар' in col_lower or 'product' in col_lower or 'название' in col_lower:
            column_mapping['name'] = col
        elif 'кол' in col_lower or 'qty' in col_lower or 'количество' in col_lower:
            column_mapping['quantity'] = col
        elif 'цена' in col_lower or 'price' in col_lower or 'стоимость' in col_lower:
            column_mapping['price'] = col

    if len(column_mapping) < 5:
        raise ValueError(f"Не удалось определить все колонки. Найдено: {list(column_mapping.keys())}")

    # Переименовываем для единообразия
    df = df.rename(columns={
        column_mapping['date']: 'дата',
        column_mapping['sku']: 'артикул',
        column_mapping['name']: 'товар',
        column_mapping['quantity']: 'кол-во',
        column_mapping['price']: 'цена'
    })

    # Преобразование дат
    df['дата'] = df['дата'].apply(parse_date)
    df = df.dropna(subset=['дата'])  # Удаляем строки с невалидными датами

    rows_loaded = 0
    products_seen = set()

    # Проверяем наличие минимум 30 дней для каждого SKU
    skus_in_file = df['артикул'].unique()

    for sku in skus_in_file:
        product = db.query(Product).filter_by(user_id=user_id, sku=sku).first()
        
        if not product:
            # Создаём новый товар
            sku_data = df[df['артикул'] == sku]
            last_row = sku_data.sort_values('дата').iloc[-1]
            
            product = Product(
                user_id=user_id,
                sku=sku,
                name=last_row['товар'],
                current_stock=100,  # Дефолтное значение (можно улучшить)
                unit_price=float(last_row['цена'])
            )
            db.add(product)
            db.flush()

        # Проверяем общее кол-во дней
        existing_days = db.query(SalesHistory.date)\
            .filter_by(product_id=product.id)\
            .distinct().count()
        
        new_days = df[df['артикул'] == sku]['дата'].nunique()
        total_days = existing_days + new_days

        if total_days < 30:
            raise ValueError(
                f"Товар '{sku}': недостаточно данных ({total_days} дней, нужно ≥30)"
            )

    # Сохраняем продажи
    for _, row in df.iterrows():
        product = db.query(Product).filter_by(user_id=user_id, sku=row['артикул']).first()
        
        sale = SalesHistory(
            user_id=user_id,
            product_id=product.id,
            date=row['дата'],
            quantity_sold=float(row['кол-во']),
            sale_price=float(row['цена'])
        )
        db.add(sale)
        rows_loaded += 1
        products_seen.add(product.id)

    db.commit()

    # Прогнозирование
    for product_id in products_seen:
        _generate_forecast(db, user_id, product_id)

    return {
        "rows_loaded": rows_loaded,
        "products_count": len(products_seen)
    }


def _generate_forecast(db: Session, user_id: int, product_id: int):
    """Генерация прогноза через Prophet"""
    # Получаем историю
    sales_data = db.query(SalesHistory.date, SalesHistory.quantity_sold)\
        .filter_by(product_id=product_id)\
        .order_by(SalesHistory.date)\
        .all()

    if len(sales_data) < 30:
        return

    # Подготовка для Prophet
    df_prophet = pd.DataFrame(sales_data, columns=['ds', 'y'])
    df_prophet['ds'] = pd.to_datetime(df_prophet['ds'])

    # Обучение
    model = Prophet(
        daily_seasonality=False,
        weekly_seasonality=True,
        yearly_seasonality=True,
        interval_width=0.95
    )
    model.fit(df_prophet)

    # Прогноз на 30 дней
    future = model.make_future_dataframe(periods=30)
    forecast = model.predict(future)

    # Удаляем старые прогнозы (избегаем дублей)
    db.query(Forecast).filter_by(product_id=product_id).delete()

    # Сохраняем новые
    for _, row in forecast.tail(30).iterrows():
        db_forecast = Forecast(
            product_id=product_id,
            forecast_date=row['ds'].date(),
            predicted_quantity=max(0, row['yhat'])  # Не даём отрицательные
        )
        db.add(db_forecast)

    db.commit()