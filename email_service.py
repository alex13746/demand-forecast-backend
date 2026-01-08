# email_service.py
import os
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from typing import List

# Конфигурация для Mail.ru SMTP
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", "9277756@mail.ru"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", "yEh-fLN-szd-7gD"),
    MAIL_FROM=os.getenv("MAIL_FROM", "9277756@mail.ru"),
    MAIL_PORT=465,  # Mail.ru использует порт 465 с SSL
    MAIL_SERVER="smtp.mail.ru",  # SMTP сервер Mail.ru
    MAIL_STARTTLS=False,  # Mail.ru не использует STARTTLS
    MAIL_SSL_TLS=True,  # Используем SSL/TLS
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

async def send_welcome_email(email: str, username: str, store_name: str):
    """Отправляет приветственное письмо новому пользователю"""
    
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0; text-align: center;">🎉 Добро пожаловать!</h1>
            </div>
            
            <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px;">
                <h2 style="color: #1f2937;">Привет, {username}!</h2>
                
                <p style="color: #4b5563; font-size: 16px; line-height: 1.6;">
                    Спасибо за регистрацию в системе прогнозирования спроса! 
                    Ваша компания<strong style="color: #667eea;">"{store_name}"</strong> успешно добавлена.
                </p>
                
                <div style="background: white; border-left: 4px solid #667eea; padding: 15px; margin: 20px 0;">
                    <h3 style="color: #1f2937; margin-top: 0;">🚀 Что дальше?</h3>
                    <ul style="color: #4b5563; line-height: 1.8;">
                        <li>Загрузите исторические данные о продажах (CSV формат)</li>
                        <li>Получите автоматические прогнозы спроса на основе ML</li>
                        <li>Получите рекомендации по закупкам товаров</li>
                        <li>Избегайте дефицита и перезатоваривания складов</li>
                    </ul>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <p style="background: #667eea; color: white; padding: 15px 30px; 
                              border-radius: 5px; font-weight: bold;
                              display: inline-block; margin: 0;">
                        Успешная регистрация!
                    </p>
                </div>
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                
                <p style="color: #9ca3af; font-size: 14px; text-align: center;">
                    Если у вас есть вопросы, свяжитесь с нами по адресу 
                    <a href="mailto:9277756@mail.ru" style="color: #667eea;">9277756@mail.ru</a>
                </p>
                
                <p style="color: #9ca3af; font-size: 12px; text-align: center; margin-top: 20px;">
                    Это письмо отправлено автоматически. Пожалуйста, не отвечайте на него.
                </p>
            </div>
        </body>
    </html>
    """
    
    text_content = f"""
    Добро пожаловать, {username}!
    
    Спасибо за регистрацию в системе прогнозирования спроса.
    Ваш магазин "{store_name}" успешно добавлен.
    
    Что дальше?
    - Загрузите данные о продажах
    - Получите прогнозы спроса
    - Оптимизируйте закупки
    
    С уважением,
    Команда Forecast System
    """
    
    message = MessageSchema(
        subject="🎉 Добро пожаловать в систему прогнозирования!",
        recipients=[email],
        body=text_content,
        html=html_content,
        subtype=MessageType.html
    )
    
    fm = FastMail(conf)
    await fm.send_message(message)
