from logging import Logger
import logging
import os
import uuid
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from freedompay.freedompay_kg import FreedomPayClient

from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies import get_transaction_service, get_user_service
from src.core.config import BOT_LINK, get_package_amounts
from src.core.db import get_db
from src.schemas import (
    PaymentCreate,
    TransactionCreate,
    TransactionStatus,
    TransactionUpdate,
    UserCreate,
    UserResponse,
)
from src.services.transaction import TransactionService
from src.services.user import UserService
from src.utils import create_transaction, create_user, get_transaction, get_transactions

load_dotenv()

router = APIRouter()

MERCHANT_ID = os.getenv("FREEDOMPAY_MERCHANT_ID", "560402")
SECRET_KEY = os.getenv("FREEDOMPAY_SECRET_KEY", "HZHObNVZSc8oMxLQ")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-webhook-url.com")


# Инициализация клиента FreedomPay
freedompay_client = FreedomPayClient(
    merchant_id=MERCHANT_ID,
    receive_key=SECRET_KEY,
    webhook_url=WEBHOOK_URL,
    test_mode=True,
)

# Настройка шаблонов
templates_dir = Path("templates")
templates_dir.mkdir(exist_ok=True)

# Создадим HTML шаблоны в реальном приложении
with open(templates_dir / "payment_result.html", "w") as f:
    f.write(
        """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        :root {
            --primary-color: {% if success %}#4CAF50{% else %}#f44336{% endif %};
            --secondary-color: #2196F3;
            --background-color: #f5f5f5;
            --text-color: #333;
            --card-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }
        
        body {
            font-family: 'Roboto', Arial, sans-serif;
            background-color: var(--background-color);
            color: var(--text-color);
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        
        .container {
            width: 90%;
            max-width: 400px;
            background-color: white;
            border-radius: 12px;
            box-shadow: var(--card-shadow);
            padding: 2rem;
            text-align: center;
        }
        
        .icon {
            font-size: 5rem;
            margin-bottom: 1rem;
            color: var(--primary-color);
        }
        
        h1 {
            color: var(--primary-color);
            margin-bottom: 1rem;
            font-size: 1.8rem;
        }
        
        p {
            margin-bottom: 2rem;
            line-height: 1.6;
            font-size: 1.1rem;
        }
        
        .btn {
            display: inline-block;
            background-color: var(--secondary-color);
            color: white;
            text-decoration: none;
            padding: 0.8rem 1.5rem;
            border-radius: 50px;
            font-weight: 500;
            transition: transform 0.3s, background-color 0.3s;
            border: none;
            outline: none;
            cursor: pointer;
            font-size: 1rem;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        }
        
        .btn:hover {
            background-color: #0b7dda;
            transform: translateY(-2px);
        }
        
        .btn:active {
            transform: translateY(0);
        }
        
        @media (max-width: 480px) {
            .container {
                width: 85%;
                padding: 1.5rem;
            }
            
            h1 {
                font-size: 1.5rem;
            }
            
            p {
                font-size: 1rem;
            }
            
            .icon {
                font-size: 4rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">
            {% if success %}
            ✅
            {% else %}
            ❌
            {% endif %}
        </div>
        <h1>{{ title }}</h1>
        <p>{{ message }}</p>
        <a href="{{ bot_link }}" class="btn">Вернуться в бот</a>
    </div>
    
</body>
</html>
    """
    )

templates = Jinja2Templates(directory=templates_dir)


@router.get("/success", response_class=HTMLResponse)
async def success(request: Request):
    """
    Страница успешной оплаты, куда FreedomPay перенаправляет пользователя.
    Отображает HTML страницу с сообщением об успешной оплате и кнопкой для возврата в бот.
    """
    return templates.TemplateResponse(
        "payment_result.html",
        {
            "request": request,
            "success": True,
            "title": "Оплата успешно завершена!",
            "message": "Ваш платеж был успешно обработан. Вы можете вернуться в бот и продолжить использование сервиса.",
            "bot_link": BOT_LINK,
        },
    )


@router.get("/failure", response_class=HTMLResponse)
async def failure(request: Request):
    """
    Страница неудачной оплаты, куда FreedomPay перенаправляет пользователя.
    Отображает HTML страницу с сообщением о неудачной оплате и кнопкой для возврата в бот.
    """
    return templates.TemplateResponse(
        "payment_result.html",
        {
            "request": request,
            "success": False,
            "title": "Оплата не завершена",
            "message": "К сожалению, ваш платеж не был обработан. Пожалуйста, проверьте данные карты или выберите другой способ оплаты.",
            "bot_link": "https://t.me/ai_cmaker_bot",
        },
    )


@router.post("/check")
async def check_payment(
    pg_order_id: str = Form(None),
    pg_amount: str = Form(None),
    pg_currency: str = Form(None),
    pg_description: str = Form(None),
    transaction_service: TransactionService = Depends(get_transaction_service),
):
    """
    Вебхук для проверки платежа FreedomPay. 
    Вызывается перед списанием средств для валидации заказа.
    
    Проверяет существование транзакции с указанным order_id
    и соответствие суммы платежа.
    """
    logging.info(f"Получен запрос на проверку платежа: {pg_order_id}, {pg_amount}, {pg_currency}, {pg_description}")
    
    # Проверка наличия обязательных параметров
    if not pg_order_id or not pg_amount:
        logging.error("Отсутствуют обязательные параметры в запросе на проверку платежа")
        return {"pg_status": "rejected", "pg_description": "Missing required parameters"}
    
    try:
        # Получаем транзакцию по order_id
        transaction = await transaction_service.get_transaction(order_id=pg_order_id)
        
        # Проверяем существование транзакции
        if not transaction:
            logging.error(f"Транзакция с order_id={pg_order_id} не найдена")
            return {"pg_status": "rejected", "pg_description": f"Transaction with order_id={pg_order_id} not found"}
        
        # Проверяем статус транзакции (должен быть PENDING или PROCESSING)
        if transaction.status not in [TransactionStatus.PENDING, TransactionStatus.PROCESSING]:
            logging.error(f"Некорректный статус транзакции: {transaction.status}")
            return {
                "pg_status": "rejected", 
                "pg_description": f"Invalid transaction status: {transaction.status}. Expected PENDING or PROCESSING"
            }
        
        # Проверяем соответствие суммы платежа (с округлением до 2 знаков)
        transaction_amount = float(transaction.amount)
        payment_amount = float(pg_amount)
        
        if abs(transaction_amount - payment_amount) > 0.01:  # допустимая погрешность 0.01
            logging.error(f"Несоответствие суммы платежа: ожидалось {transaction_amount}, получено {payment_amount}")
            return {
                "pg_status": "rejected", 
                "pg_description": f"Amount mismatch: expected {transaction_amount}, got {payment_amount}"
            }
        
        # Обновляем статус транзакции на PROCESSING
        if transaction.status == TransactionStatus.PENDING:
            update_data = TransactionUpdate(status=TransactionStatus.PROCESSING)
            await transaction_service.update_transaction(
                transaction_id=transaction.transaction_id, 
                update_data=update_data
            )
            logging.info(f"Статус транзакции {pg_order_id} обновлен на PROCESSING")
        
        # Всё в порядке, разрешаем продолжить обработку платежа
        return {"pg_status": "ok"}
        
    except ValueError as e:
        logging.error(f"Ошибка валидации при проверке платежа: {e}")
        return {"pg_status": "rejected", "pg_description": str(e)}
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при проверке платежа: {e}")
        return {"pg_status": "rejected", "pg_description": "Internal server error"}


@router.post("/result")
async def payment_result(
    request: Request,
    transaction_service: TransactionService = Depends(get_transaction_service),
    user_service: UserService = Depends(get_user_service),
):
    """
    Вебхук для получения результата платежа от FreedomPay.
    Вызывается после обработки платежа.
    
    Обновляет статус транзакции на COMPLETED или FAILED
    в зависимости от результата оплаты.
    """
    try:
        # Получаем данные от FreedomPay
        form_data = await request.form()
        
        # Логируем полученные данные
        logging.info(f"Получен результат платежа: {dict(form_data)}")
        
        # Извлекаем необходимые параметры
        pg_order_id = form_data.get("pg_order_id")
        pg_payment_id = form_data.get("pg_payment_id")
        pg_result = form_data.get("pg_result", "0")  # 1 - успешно, 0 - неуспешно
        
        # Проверяем наличие обязательных параметров
        if not pg_order_id:
            logging.error("Отсутствует order_id в запросе результата платежа")
            return {"pg_status": "rejected", "pg_description": "Missing order_id parameter"}
        
        # Получаем транзакцию по order_id
        transaction = await transaction_service.get_transaction(order_id=pg_order_id)
        
        # Проверяем существование транзакции
        if not transaction:
            logging.error(f"Транзакция с order_id={pg_order_id} не найдена")
            return {"pg_status": "rejected", "pg_description": f"Transaction with order_id={pg_order_id} not found"}
        
        # Определяем новый статус транзакции
        new_status = TransactionStatus.COMPLETED if pg_result == "1" else TransactionStatus.FAILED
        
        # Обновляем транзакцию
        update_data = TransactionUpdate(
            status=new_status,
            payment_id=pg_payment_id or transaction.payment_id  # Обновляем payment_id, если он предоставлен
        )
        
        updated_transaction = await transaction_service.update_transaction(
            transaction_id=transaction.transaction_id,
            update_data=update_data
        )
        
        # Если платеж успешный, обновляем пользовательские данные (кредиты)
        if new_status == TransactionStatus.COMPLETED:
            logging.info(f"Платеж {pg_order_id} успешно завершен")
             
            telegram_id = transaction.user_id 
            package_type = updated_transaction.package_type 
            updated_user = await user_service.add_credits(telegram_id=telegram_id, credits=int(package_type))
            
        else:
            logging.warning(f"Платеж {pg_order_id} не выполнен, статус обновлен на FAILED")
        
        # Возвращаем успешный ответ FreedomPay
        return {"pg_status": "ok"}
        
    except ValueError as e:
        logging.error(f"Ошибка валидации при обработке результата платежа: {e}")
        return {"pg_status": "rejected", "pg_description": str(e)}
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при обработке результата платежа: {e}")
        return {"pg_status": "rejected", "pg_description": "Internal server error"}
