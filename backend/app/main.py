import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.infrastructure.db.session import async_engine
from app.presentation.api.auth import router as auth_router
from app.presentation.api.chat import router as chat_router
from app.presentation.api.memories import router as memories_router


# Setup standard logging configuration
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ame_backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup events
    logger.info("Initializing Adaptive Memory Engine (AME) Backend services...")
    # Attempt to verify database connectivity without blocking server startup if it fails
    logger.info(f"Target Database URL: {settings.DATABASE_URL}")
    try:
        # We perform a soft test to see if pg_isready or similar.
        # Since the database might not be running in this phase, we catch exceptions and log them as a warning.
        async with async_engine.connect() as conn:
            await conn.execute("SELECT 1")
        logger.info("Database connection verified successfully.")
    except Exception as e:
        logger.warning(
            f"Database connection verification failed during startup (server will still start): {e}"
        )
    
    yield
    
    # Shutdown events
    logger.info("Shutting down AME Backend services...")
    try:
        await async_engine.dispose()
        logger.info("Database engine pool disposed.")
    except Exception as e:
        logger.error(f"Error during database engine disposal: {e}")


# Initialize FastAPI App
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Cognitive long-term memory engine foundation backend.",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Configure CORS policies to allow local frontend compilation requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health_check():
    """Confirms application is loaded and basic database connections compile."""
    db_status = "healthy"
    try:
        async with async_engine.connect() as conn:
            await conn.execute("SELECT 1")
    except Exception:
        db_status = "unreachable"

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "project": settings.PROJECT_NAME,
            "version": "0.1.0",
            "environment": settings.ENV,
            "database": db_status
        }
    )


# Exception handler hooks
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Formats standard HTTPExceptions into unified API error payload format."""
    error_codes = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "RESOURCE_NOT_FOUND",
        422: "VALIDATION_ERROR",
    }
    error_code = error_codes.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": error_code,
            "message": exc.detail,
            "details": None
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """Formats request schema Pydantic validation errors into unified API error payload format."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Request validation failed.",
            "details": {"errors": exc.errors()}
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    """Fallback handler catching unhandled exceptions and wrapping them in standard JSON structure."""
    logger.error(f"Unhandled error occurred at request {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred. Please consult backend logs.",
            "details": str(exc) if settings.DEBUG else {}
        }
    )


# Register presentation API routers
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(chat_router, prefix=settings.API_V1_PREFIX)
app.include_router(memories_router, prefix=settings.API_V1_PREFIX)

