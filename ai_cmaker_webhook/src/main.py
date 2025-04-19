import asyncio
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from uvicorn import Config, Server

from src.core.db import create_all, engine
from src.api.main import api_router
from src.exceptions import AppException, CustomIntegrityError, CustomValidationError, ResourceAlreadyExistsError, ResourceNotFoundError

# i am funny haha

# FastAPI initialization
@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_all()
    try:
        yield
    finally:
        await engine.dispose()

app = FastAPI(
    lifespan=lifespan,
    root_path="/",
)
app.include_router(api_router)

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """
    Handler for all app's excpetions 
    """

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            **({"extra": exc.details} if exc.details else {})
        },
    )

@app.exception_handler(ResourceNotFoundError)
async def not_found_exception_handler(request: Request, exc: ResourceNotFoundError):
    """
    Handler for all 404 errors 
    """

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message
        }
    )

@app.exception_handler(ResourceAlreadyExistsError)
async def already_exists_exception_handler(request: Request, exc: ResourceNotFoundError):
    """
    Handler for all 409 errors 
    """

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message
        }
    )

@app.exception_handler(CustomIntegrityError)
async def integrity_error_exception_handler(request: Request, exc: CustomIntegrityError):
    """
    Handler for all kinds of integrity errors in database
    """

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message
        }
    )

@app.exception_handler(CustomValidationError)
async def validation_error_exception_handler(request: Request, exc: CustomValidationError):
    """
    Handler for all kind of validation errors
    """

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message
        }
    )

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def start_fastapi():
    print("Запуск FastAPI сервера...")
    config = Config(app=app, host="0.0.0.0", port=8000, log_level="info", reload=True)
    server = Server(config)
    return server

async def main():
    server = await start_fastapi()
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nForced stop")
    except Exception as e:
        print(f"Error: {e}")
