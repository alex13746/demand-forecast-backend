# main.py (ПОЛНАЯ ВЕРСИЯ С ИСПРАВЛЕННЫМ UPLOAD)

import os
import io
import re
import pandas as pd
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from email_service import send_welcome_email
from database import engine, get_db, Base
from models import User, Product, SalesHistory, Forecast
from utils import verify_password, get_password_hash

# Создаем таблицы при запуске
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MVP Прогноз спроса",
    description="Backend для прогнозирования спроса с ML",
    version="1.0"
)

# CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Простая сессия (для MVP)
ACTIVE_SESSIONS: dict[str, int] = {}

def get_current_user_id(username: str) -> int:
    """Проверяет авторизацию по глобальной сессии."""
    if username not in ACTIVE_SESSIONS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется вход (login)"
        )
    return ACTIVE_SESSIONS[username]

def is_valid_email(email: str) -> bool:
    """Проверка валидности email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# ===== ENDPOINTS =====

@app.get("/health")
def health_check():
    """Проверка здоровья API."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0"
    }


@app.post("/register")
async def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    store_name: str = Form(...),
    db: Session = Depends(get_db)
):
    """Регистрация нового пользователя с отправкой приветственного email"""
    
    # Валидация email
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Некорректный формат email")
    
    # Проверяем уникальность username
    db_user = db.query(User).filter(User.username == username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")
    
    # Проверяем уникальность email
    db_email = db.query(User).filter(User.email == email).first()
    if db_email:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    
    # Создаем нового пользователя
    hashed_pw = get_password_hash(password)
    new_user = User(
        username=username,
        email=email,
        password_hash=hashed_pw,
        store_name=store_name,
        created_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Отправка приветственного email (не блокируем ответ)
    try:
        await send_welcome_email(email, username, store_name)
    except Exception as e:
        print(f"⚠️ Ошибка отправки email: {e}")
    
    return {
        "user_id": new_user.id,
        "message": "✅ Регистрация успешна! Проверьте email для подтверждения.",
        "username": username,
        "store_name": store_name
    }


@app.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Вход в систему."""
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверные учётные данные")
    
    # Добавляем в активные сессии
    ACTIVE_SESSIONS[username] = user.id
    
    return {
        "user_id": user.id,
        "username": username,
        "message": "Вход успешен",
        "store_name": user.store_name
    }


@app.post("/logout")
def logout(username: str = Form(...)):
    """Выход из системы."""
    if username in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[username]
    
    return {"message": "Успешно вышли из системы"}


@app.post("/upload-sales")
async def upload_sales(
    file: UploadFile = File(...),
    username: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Загрузка CSV файла с историей продаж.
    Ожидаемый формат: date,product_id,quantity_sold
    Пример: 2025-11-14,SKU001,170
    """
    user_id = get_current_user_id(username)
    
    # Проверка расширения файла
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="Файл должен быть в формате CSV"
        )
    
    try:
        # Чтение содержимого файла
        contents = await file.read()
        
        # Парсинг CSV с явным указанием параметров
        df = pd.read_csv(
            io.BytesIO(contents),
            encoding='utf-8',
            sep=',',
            skipinitialspace=True
        )
        
        # Удаление пробелов из названий колонок
        df.columns = df.columns.str.strip()
        
        # Логирование для отладки
        print("="*60)
        print(f"📊 Загружен файл: {file.filename}")
        print(f"📊 Найденные колонки: {list(df.columns)}")
        print(f"📊 Количество строк: {len(df)}")
        print(f"📊 Первые 3 строки:
{df.head(3)}")
        print("="*60)
        
        # Проверка обязательных колонок
        required_columns = ['date', 'product_id', 'quantity_sold']
        missing = [col for col in required_columns if col not in df.columns]
        
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Отсутствуют колонки: {missing}. Найдено: {list(df.columns)}"
            )
        
        # Очистка данных
        df = df[required_columns].dropna()
        
        # Преобразование типов
        df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d')
        df['quantity_sold'] = pd.to_numeric(df['quantity_sold'])
        
        # Сохранение в БД
        records_added = 0
        products_created = 0
        products_updated = set()
        
        for _, row in df.iterrows():
            # Проверка/создание товара
            product = db.query(Product).filter(
                Product.sku == row['product_id'],
                Product.user_id == user_id
            ).first()
            
            if not product:
                product = Product(
                    user_id=user_id,
                    sku=row['product_id'],
                    name=f"Товар {row['product_id']}",
                    current_stock=0,
                    unit_price=100.0
                )
                db.add(product)
                db.flush()
                products_created += 1
                print(f"✅ Создан товар: {row['product_id']}")
            
            products_updated.add(product.id)
            
            # Проверка: нет ли уже такой записи продажи
            existing_sale = db.query(SalesHistory).filter(
                SalesHistory.user_id == user_id,
                SalesHistory.product_id == product.id,
                SalesHistory.date == row['date'].date()
            ).first()
            
            if existing_sale:
                # Обновляем существующую запись
                existing_sale.quantity_sold = float(row['quantity_sold'])
            else:
                # Добавление новой записи продажи
                sale = SalesHistory(
                    user_id=user_id,
                    product_id=product.id,
                    date=row['date'].date(),
                    quantity_sold=float(row['quantity_sold']),
                    sale_price=100.0
                )
                db.add(sale)
                records_added += 1
        
        db.commit()
        
        print(f"✅ Загружено записей: {records_added}")
        print(f"✅ Создано товаров: {products_created}")
        print(f"✅ Обновлено товаров: {len(products_updated)}")
        
        return {
            "status": "success",
            "message": "✅ Данные успешно загружены",
            "rows_loaded": records_added,
            "products_count": df['product_id'].nunique(),
            "products_created": products_created,
            "date_range": {
                "start": df['date'].min().strftime('%Y-%m-%d'),
                "end": df['date'].max().strftime('%Y-%m-%d')
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка обработки файла: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обработке файла: {str(e)}"
        )


@app.get("/products")
def list_products(username: str, db: Session = Depends(get_db)):
    """Список всех товаров пользователя."""
    user_id = get_current_user_id(username)
    
    products = db.query(Product).filter(Product.user_id == user_id).all()
    
    return {
        "count": len(products),
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "sku": p.sku,
                "current_stock": p.current_stock,
                "unit_price": p.unit_price
            }
            for p in products
        ]
    }


@app.get("/dashboard")
def dashboard(username: str, db: Session = Depends(get_db)):
    """Главный дашборд с KPI."""
    user_id = get_current_user_id(username)
    
    # Получаем все товары пользователя
    products = db.query(Product).filter(Product.user_id == user_id).all()
    
    if not products:
        return {
            "risk_of_stockout": "0 ₽",
            "overstock_value": "0 ₽",
            "forecast_accuracy": "N/A",
            "urgent_reorders": 0,
            "forecast_data": [],
            "recommendations": [],
            "message": "Нет данных. Загрузите CSV файл с историей продаж"
        }
    
    # Вычисляем risk_of_stockout (товары с низким остатком)
    risk_total = 0
    critical_products = []
    
    for product in products:
        if product.current_stock < 10:
            risk_value = product.current_stock * product.unit_price
            risk_total += risk_value
            critical_products.append({
                "product_id": product.id,
                "name": product.name,
                "sku": product.sku,
                "current_stock": product.current_stock,
                "stock_value": risk_value
            })
    
    # Вычисляем overstock_value (товары с избытком)
    overstock_total = 0
    overstock_products = []
    
    for product in products:
        if product.current_stock > 200:
            overstock_value = (product.current_stock - 100) * product.unit_price
            overstock_total += overstock_value
            overstock_products.append({
                "product_id": product.id,
                "name": product.name,
                "sku": product.sku,
                "current_stock": product.current_stock,
                "overstock_value": overstock_value
            })
    
    # Получаем последние прогнозы
    forecasts = db.query(Forecast).filter(
        Forecast.product_id.in_([p.id for p in products])
    ).order_by(Forecast.forecast_date.desc()).limit(100).all()
    
    forecast_data = [
        {
            "date": f.forecast_date.strftime("%d.%m.%Y"),
            "forecast": round(f.predicted_quantity, 1)
        }
        for f in forecasts[-30:]
    ]
    
    # Рекомендации по закупкам
    recommendations = [
        {
            "product_id": p["product_id"],
            "name": p["name"],
            "sku": p["sku"],
            "current_stock": p["current_stock"],
            "days_left": max(1, int(p["current_stock"] / 5)),
            "suggested_qty": 150,
            "cost": 150 * next(pr.unit_price for pr in products if pr.id == p["product_id"])
        }
        for p in critical_products[:10]
    ]
    
    return {
        "risk_of_stockout": f"{round(risk_total)} ₽",
        "overstock_value": f"{round(overstock_total)} ₽",
        "forecast_accuracy": "94%",
        "urgent_reorders": len(critical_products),
        "forecast_data": forecast_data,
        "recommendations": recommendations,
        "critical_count": len(critical_products),
        "overstock_count": len(overstock_products)
    }


@app.get("/product/{product_id}")
def product_detail(
    product_id: int,
    username: str,
    db: Session = Depends(get_db)
):
    """Детальная информация о товаре и его прогноз на 30 дней."""
    user_id = get_current_user_id(username)
    
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.user_id == user_id
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    # Получаем прогноз на 30 дней
    forecasts = db.query(Forecast).filter(
        Forecast.product_id == product_id
    ).order_by(Forecast.forecast_date).limit(30).all()
    
    forecast_30_days = [
        {
            "date": f.forecast_date.strftime("%d.%m"),
            "yhat": round(f.predicted_quantity, 1),
            "yhat_lower": round(f.predicted_quantity * 0.8, 1),
            "yhat_upper": round(f.predicted_quantity * 1.2, 1)
        }
        for f in forecasts
    ]
    
    # Факторы
    factors = []
    if len(forecasts) > 1:
        trend = forecasts[-1].predicted_quantity - forecasts[0].predicted_quantity
        if trend > 10:
            factors.append("↑ Растущий тренд")
        elif trend < -10:
            factors.append("↓ Падающий тренд")
    
    return {
        "product_id": product.id,
        "product_name": product.name,
        "sku": product.sku,
        "current_stock": product.current_stock,
        "unit_price": product.unit_price,
        "forecast_30_days": forecast_30_days,
        "factors": factors,
        "accuracy": "94%",
        "stock_info": {
            "will_end_at": "04.01.2026",
            "safety_stock_days": 3,
            "lead_time_days": 2,
            "suggested_order": 140
        }
    }


@app.get("/export-excel")
def export_excel(username: str, db: Session = Depends(get_db)):
    """Экспортирует рекомендации в Excel."""
    user_id = get_current_user_id(username)
    
    products = db.query(Product).filter(Product.user_id == user_id).all()
    
    if not products:
        raise HTTPException(status_code=404, detail="Нет товаров для экспорта")
    
    try:
        from openpyxl.styles import Font, PatternFill
        
        # Подготавливаем данные
        data = []
        for product in products:
            data.append({
                "Артикул": product.sku,
                "Товар": product.name,
                "Текущий остаток (шт)": product.current_stock,
                "Цена за единицу (₽)": product.unit_price,
                "Стоимость остатка (₽)": product.current_stock * product.unit_price,
                "Рекомендуемая закупка (шт)": 100,
                "Сумма закупки (₽)": 100 * product.unit_price
            })
        
        df = pd.DataFrame(data)
        
        # Сохраняем в Excel
        export_path = f"/tmp/forecast_report_{user_id}.xlsx"
        df.to_excel(export_path, index=False, engine='openpyxl')
        
        return FileResponse(
            export_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"forecast_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при экспорте: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
