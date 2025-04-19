from typing import Any, Dict, Optional

# Базовый класс для всех доменных исключений
class AppException(Exception):
    """Базовый класс для всех исключений приложения"""
    def __init__(
        self, 
        message: str, 
        status_code: int = 400, 
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


# Исключения для бизнес-логики
class ResourceAlreadyExistsError(AppException):
    """Исключение, когда ресурс уже существует"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=409, details=details)

class ResourceNotFoundError(AppException):
    """Исключение, когда ресурс не найден"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=404, details=details)

class InsufficientCreditsError(AppException):
    """Исключение, когда недостаточно кредитов"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=402, details=details)

class CustomIntegrityError(AppException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)

class CustomValidationError(AppException):
    """ Handle validation """
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=403, details=details)

class DatabaseError(AppException):
    """Исключение ошибок базы данных"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)
