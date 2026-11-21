import logging
import sys
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.presentation.api.auth import router as auth_router
from app.presentation.api.chat import router as chat_router
from app.presentation.api.agents import router as agents_router
from app.presentation.api.extractions import router as extractions_router
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

# Initialize FastAPI App
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Cognitive long-term memory engine foundation backend.",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
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
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "project": settings.PROJECT_NAME,
            "version": "0.1.0",
            "environment": settings.ENV
        }
    )


# Exception handler hooks
@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
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
app.include_router(agents_router, prefix=settings.API_V1_PREFIX)
app.include_router(extractions_router, prefix=settings.API_V1_PREFIX)
app.include_router(memories_router, prefix=settings.API_V1_PREFIX)
