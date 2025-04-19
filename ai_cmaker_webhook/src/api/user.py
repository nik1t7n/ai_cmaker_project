import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException

from src.schemas import (
    UserCreate,
    UserFilterParams,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from src.services.user import UserService
from src.api.dependencies import get_user_service


router = APIRouter()


@router.post("", response_model=UserResponse, status_code=201)
async def create_user_api(
    user_create: UserCreate, user_service: UserService = Depends(get_user_service)
):
    """
    Create a new user or return an existing one.
    
    Parameters:
    - **user_create**: User data for creation
    
    Returns:
    - User information
    """
    user_data = await user_service.create_user(user_create=user_create)
    return user_data


@router.get("/{telegram_id}", response_model=UserResponse)
async def get_user_api(
    telegram_id: int, user_service: UserService = Depends(get_user_service)
):
    """
    Get user data by telegram_id.
    
    Parameters:
    - **telegram_id**: Telegram user ID
    
    Returns:
    - User information
    """
    user = await user_service.get_user(telegram_id)
    return user

@router.get("", response_model=UserListResponse)
async def get_users_api(
    is_paid: Optional[bool] = None,
    min_credits: Optional[int] = None,
    max_credits: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "telegram_id",
    sort_order: str = "asc",
    user_service: UserService = Depends(get_user_service),
):
    """
    Get a list of users with filtering options.
    
    Parameters:
    - **is_paid**: Filter by payment status
    - **min_credits**: Minimum number of credits
    - **max_credits**: Maximum number of credits
    - **page**: Page number for pagination
    - **page_size**: Number of users per page
    - **sort_by**: Field to sort by
    - **sort_order**: Sort order ('asc' or 'desc')
    
    Returns:
    - List of users with pagination information
    """
    filters = UserFilterParams(
        is_paid=is_paid, min_credits=min_credits, max_credits=max_credits
    )
    users = await user_service.get_users(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return users


@router.patch("/{telegram_id}", response_model=UserResponse)
async def update_user_api(
    telegram_id: int,
    update_data: UserUpdate,
    user_service: UserService = Depends(get_user_service),
):
    """
    Update user data.
    
    Parameters:
    - **telegram_id**: Telegram user ID
    - **update_data**: Fields to update
    
    Returns:
    - Updated user information
    """
    try:
        user = await user_service.update_user(telegram_id, update_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")


@router.post("/{telegram_id}/credits/add", response_model=UserResponse)
async def add_user_credits_api(
    telegram_id: int,
    credits: int,
    update_purchase_time: bool = True,
    user_service: UserService = Depends(get_user_service),
):
    """
    Add credits to a user.
    
    Parameters:
    - **telegram_id**: Telegram user ID
    - **credits**: Number of credits to add
    - **update_purchase_time**: Whether to update the purchase time
    
    Returns:
    - Updated user information
    """
    try:
        user = await user_service.add_credits(
            telegram_id, credits, update_purchase_time
        )
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add credits: {str(e)}")


@router.post("/{telegram_id}/credits/deduct", response_model=UserResponse)
async def deduct_user_credits_api(
    telegram_id: int,
    credits: int,
    user_service: UserService = Depends(get_user_service),
):
    """
    Deduct credits from a user.
    
    Parameters:
    - **telegram_id**: Telegram user ID
    - **credits**: Number of credits to deduct
    
    Returns:
    - Updated user information
    
    Raises:
    - 402 Payment Required: If the user doesn't have enough credits
    """
    try:
        user = await user_service.deduct_credits(telegram_id, credits)
        return user
    except ValueError as e:
        if "not enough credits" in str(e):
            raise HTTPException(status_code=402, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to deduct credits: {str(e)}"
        )


@router.post("/{telegram_id}/stats/update", response_model=UserResponse)
async def update_user_stats_api(
    telegram_id: int,
    generations: Optional[int] = None,
    prompt_tokens: Optional[int] = None,
    response_tokens: Optional[int] = None,
    video_duration: Optional[int] = None,
    user_service: UserService = Depends(get_user_service),
):
    """
    Update user usage statistics.
    
    Parameters:
    - **telegram_id**: Telegram user ID
    - **generations**: Number of generations to add
    - **prompt_tokens**: Number of prompt tokens to add
    - **response_tokens**: Number of response tokens to add
    - **video_duration**: Video duration to add
    
    Returns:
    - Updated user information
    """
    try:
        user = await user_service.update_usage_stats(
            telegram_id, generations, prompt_tokens, response_tokens, video_duration
        )
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update user stats: {str(e)}"
        )


@router.post("/{telegram_id}/data", response_model=UserResponse)
async def set_user_data_api(
    telegram_id: int,
    key: str,
    value: Any,
    user_service: UserService = Depends(get_user_service),
):
    """
    Set arbitrary data in the user's other_data field.
    
    Parameters:
    - **telegram_id**: Telegram user ID
    - **key**: Key to set
    - **value**: Value to set
    
    Returns:
    - Updated user information
    """
    try:
        user = await user_service.set_user_data(telegram_id, key, value)
        return user
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to set user data: {str(e)}"
        )


@router.delete("/{telegram_id}", response_model=Dict[str, bool])
async def delete_user_api(
    telegram_id: int, user_service: UserService = Depends(get_user_service)
):
    """
    Delete a user.
    
    Parameters:
    - **telegram_id**: Telegram user ID
    
    Returns:
    - Success status
    """
    try:
        result = await user_service.delete_user(telegram_id)
        return {"success": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")


@router.get("/filter/paid", response_model=UserListResponse)
async def get_paid_users_api(
    page: int = 1,
    page_size: int = 20,
    user_service: UserService = Depends(get_user_service),
):
    """
    Get a list of users who have paid for services.
    
    Parameters:
    - **page**: Page number for pagination
    - **page_size**: Number of users per page
    
    Returns:
    - List of paid users with pagination information
    """
    try:
        users = await user_service.get_paid_users(page, page_size)
        return users
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get paid users: {str(e)}"
        )


@router.get("/filter/with-credits", response_model=UserListResponse)
async def get_users_with_credits_api(
    page: int = 1,
    page_size: int = 20,
    user_service: UserService = Depends(get_user_service),
):
    """
    Get a list of users who have credits remaining.
    
    Parameters:
    - **page**: Page number for pagination
    - **page_size**: Number of users per page
    
    Returns:
    - List of users with credits
    """
    try:
        users = await user_service.get_users_with_credits_left(page, page_size)
        return users
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get users with credits: {str(e)}"
        )


@router.get("/filter/credits-range", response_model=UserListResponse)
async def get_users_by_credits_range_api(
    min_credits: int,
    max_credits: int,
    page: int = 1,
    page_size: int = 20,
    user_service: UserService = Depends(get_user_service),
):
    """
    Get users within a specified credit range.
    
    Parameters:
    - **min_credits**: Minimum number of credits
    - **max_credits**: Maximum number of credits
    - **page**: Page number for pagination
    - **page_size**: Number of users per page
    
    Returns:
    - List of users in the credits range
    """
    try:
        users = await user_service.get_users_by_credits_range(
            min_credits, max_credits, page, page_size
        )
        return users
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get users by credits range: {str(e)}"
        )
