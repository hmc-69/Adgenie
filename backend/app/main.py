from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine, ensure_creative_image_columns, test_database_connection
from app.models.user import User  # Ensure models are loaded before create_all
from app.models.campaign import Campaign
from app.models.creative import Creative
from app.models.audience_analysis import AudienceAnalysisRun
from app.routers.auth import router as auth_router
from app.routers.campaigns import router as campaigns_router
from app.routers.creative import router as creative_router
from app.routers.audience_analysis import router as audience_analysis_router

_REGISTERED_MODELS = (User, Campaign, Creative, AudienceAnalysisRun)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup if they do not exist
    try:
        Base.metadata.create_all(bind=engine)
        ensure_creative_image_columns()
        print("Database tables verified/created successfully.")
    except Exception as error:
        print(f"Error during database table initialization: {error}")
    yield


app = FastAPI(
    title="AdGenie API",
    description="AI-Powered Marketing Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(auth_router)
app.include_router(campaigns_router)
app.include_router(creative_router)
app.include_router(audience_analysis_router)


@app.get("/")
def root():
    return {
        "message": "Welcome to AdGenie API",
        "status": "running"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AdGenie Backend"
    }


@app.get("/api/health/database")
def database_health_check():
    database_connected = test_database_connection()

    if database_connected:
        return {
            "status": "connected",
            "database": "MySQL",
            "message": "Database connection successful"
        }

    return {
        "status": "error",
        "database": "MySQL",
        "message": "Database connection failed"
    }
