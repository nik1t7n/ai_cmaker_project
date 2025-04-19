import os
from uuid import UUID
import logging
import uuid
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException

from freedompay.freedompay_kg import FreedomPayClient
from src.api.dependencies import get_transaction_service, get_user_service
from src.core.config import BOT_LINK, get_package_amounts
from src.schemas import (
    PackageType,
    PaymentCreate,
    TransactionCreate,
    TransactionStatus,
    TransactionUpdate,
)
from src.services.transaction import TransactionService


MERCHANT_ID = os.getenv("FREEDOMPAY_MERCHANT_ID", "560402")
SECRET_KEY = os.getenv("FREEDOMPAY_SECRET_KEY", "HZHObNVZSc8oMxLQ")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-webhook-url.com")

freedompay_client = FreedomPayClient(
    merchant_id=MERCHANT_ID,
    receive_key=SECRET_KEY,
    webhook_url=WEBHOOK_URL,
    test_mode=True,
)


router = APIRouter()


@router.post("/payments", status_code=201)
async def create_payment_api(
    payment_create: PaymentCreate,
    transaction_service: TransactionService = Depends(get_transaction_service),
):
    """
    Create a new payment and initialize it in FreedomPay.
    
    Parameters:
    - **payment_create**: Payment creation data with user_id, package, user_phone, and user_email
    
    Returns:
    - Payment information with order_id, payment_url, and transaction details
    
    Raises:
    - 500 Internal Server Error: If payment creation fails
    """
    order_id = f"order-{payment_create.user_id}-{uuid.uuid4().hex[:8]}"

    package_amounts = await get_package_amounts()

    amount = package_amounts[payment_create.package]["price"]
    description = package_amounts[payment_create.package]["description"]

    transaction_create = TransactionCreate(
        user_id=payment_create.user_id,
        amount=amount,
        status=TransactionStatus.PENDING,
        # payment_id will be added later after FreedomPay response
        order_id=order_id,
        package_type=payment_create.package,
    )

    transaction = await transaction_service.create_transaction(transaction_create)

    try:

        # Payment Response looks like this:
        # {
        #     'status': 'ok',
        #     'payment_id': '1423102060',
        #     'redirect_url': 'https://customer.freedompay.kg/pay.html?customer=01961090-5367-7094-b203-0390b2c4c49b&lang=ru',
        #     'redirect_url_type': 'need data',
        #     'salt': '6JgiySI9Q61eZcDT',
        #     'sig': '123d0ea5505ba48137e0fcb7f1fe04ae'
        # }

        payment_response = await freedompay_client.init_payment(
            order_id=order_id,
            amount=amount,
            description=description,
            user_phone=payment_create.user_phone,
            user_email=payment_create.user_email,
        )

        payment_id = payment_response["payment_id"]

        update_data = TransactionUpdate(payment_id=payment_id)
        await transaction_service.update_transaction(
            transaction_id=transaction.transaction_id, update_data=update_data
        )

        payment_url = payment_response.get("redirect_url", "")

        return {
            "success": True,
            "order_id": order_id,
            "payment_url": payment_url,
            "transaction": transaction,
        }

    except Exception as e:
        logging.error(f"Error creating payment: {str(e)}")
        # Update transaction status to "failed"
        update_data = TransactionUpdate(status=TransactionStatus.FAILED)
        await transaction_service.update_transaction(
            transaction_id=transaction.transaction_id, update_data=update_data
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to create payment: {str(e)}"
        )


@router.post("/payments/status")
async def check_payment_status_api(
    order_id: str,
    transaction_service: TransactionService = Depends(get_transaction_service),
):
    """
    Check the status of a payment by order ID.
    
    Parameters:
    - **order_id**: The order ID to check
    
    Returns:
    - Payment status and transaction information
    
    Raises:
    - 500 Internal Server Error: If status check fails
    """
    try:
        transaction = await transaction_service.get_transaction(order_id=order_id)

        if transaction.status in [
            TransactionStatus.COMPLETED,
            TransactionStatus.FAILED,
        ]:
            return {"status": transaction.status, "transaction": transaction}

        status_response = await freedompay_client.get_payment_status(order_id=order_id)

        if status_response == 1:
            update_data = TransactionUpdate(status=TransactionStatus.COMPLETED)
            await transaction_service.update_transaction(
                transaction_id=transaction.transaction_id, update_data=update_data
            )

            return {"status": TransactionStatus.COMPLETED, "transaction": transaction}
        else:
            update_data = TransactionUpdate(status=TransactionStatus.PROCESSING)
            await transaction_service.update_transaction(
                transaction_id=transaction.transaction_id, update_data=update_data
            )

            return {"status": TransactionStatus.PROCESSING, "transaction": transaction}
    except Exception as e:
        logging.error(f"Error checking payment status: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to check payment status: {str(e)}"
        )


@router.get("/users/{user_id}/transactions")
async def get_user_transactions(
    user_id: int,
    transaction_service: TransactionService = Depends(get_transaction_service),
    page: int = 1,
    page_size: int = 20,
):
    """
    Get a user's transaction history.
    
    Parameters:
    - **user_id**: The user ID
    - **page**: Page number for pagination
    - **page_size**: Number of transactions per page
    
    Returns:
    - List of transactions
    """
    transactions = await transaction_service.get_transactions(
        user_id=user_id, page=page, page_size=page_size
    )
    return {"transactions": transactions}


@router.delete("/transactions/{transaction_id}")
async def delete_transaction_api(
    transaction_id: UUID,
    transaction_service: TransactionService = Depends(get_transaction_service),
):
    """
    Soft delete a transaction.
    
    Parameters:
    - **transaction_id**: UUID of the transaction to delete
    
    Returns:
    - Success status
    
    Raises:
    - 404 Not Found: If transaction not found
    - 500 Internal Server Error: If deletion fails
    """
    try:
        result = await transaction_service.delete_transaction(transaction_id)
        return {"success": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logging.error(f"Error deleting transaction: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete transaction: {str(e)}"
        )


@router.post("/transactions/{transaction_id}/restore")
async def restore_transaction_api(
    transaction_id: UUID,
    transaction_service: TransactionService = Depends(get_transaction_service),
):
    """
    Restore a soft-deleted transaction.
    
    Parameters:
    - **transaction_id**: UUID of the transaction to restore
    
    Returns:
    - Restored transaction
    
    Raises:
    - 404 Not Found: If transaction not found
    - 500 Internal Server Error: If restoration fails
    """
    try:
        transaction = await transaction_service.restore_transaction(transaction_id)
        return {"success": True, "transaction": transaction}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logging.error(f"Error restoring transaction: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to restore transaction: {str(e)}"
        )


@router.get("/transactions")
async def get_transactions_api(
    user_id: Optional[int] = None,
    order_id: Optional[str] = None,
    payment_id: Optional[str] = None,
    status: Optional[TransactionStatus] = None,
    package_type: Optional[PackageType] = None,
    include_deleted: bool = False,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    transaction_service: TransactionService = Depends(get_transaction_service),
):
    """
    Get transactions with filtering options.
    
    Parameters:
    - **user_id**: Filter by user ID
    - **order_id**: Filter by order ID
    - **payment_id**: Filter by payment ID
    - **status**: Filter by transaction status
    - **package_type**: Filter by package type
    - **include_deleted**: Whether to include soft-deleted transactions
    - **page**: Page number for pagination
    - **page_size**: Number of transactions per page
    - **sort_by**: Field to sort by
    - **sort_order**: Sort order ('asc' or 'desc')
    
    Returns:
    - List of transactions with pagination information
    
    Raises:
    - 400 Bad Request: If invalid parameters are provided
    - 500 Internal Server Error: If query fails
    """
    try:
        transactions = await transaction_service.get_transactions(
            user_id=user_id,
            order_id=order_id,
            payment_id=payment_id,
            status=status,
            package_type=package_type,
            include_deleted=include_deleted,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return {"transactions": transactions}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"Error getting transactions: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get transactions: {str(e)}"
        )


@router.get("/transactions/{transaction_id}")
async def get_transaction_by_id_api(
    transaction_id: UUID,
    include_deleted: bool = False,
    transaction_service: TransactionService = Depends(get_transaction_service),
):
    """
    Get a transaction by ID.
    
    Parameters:
    - **transaction_id**: UUID of the transaction
    - **include_deleted**: Whether to include soft-deleted transactions
    
    Returns:
    - Transaction details
    
    Raises:
    - 404 Not Found: If transaction not found
    - 500 Internal Server Error: If query fails
    """
    try:
        transaction = await transaction_service.get_transaction(
            transaction_id=transaction_id,
            include_deleted=include_deleted,
        )
        return {"transaction": transaction}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logging.error(f"Error getting transaction: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get transaction: {str(e)}"
        )



