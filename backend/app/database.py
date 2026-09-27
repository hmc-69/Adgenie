import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not configured in .env")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_database_connection():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as error:
        print(f"Database connection failed: {error}")
        return False


def ensure_creative_image_columns():
    """Add image metadata columns to databases created before image generation."""
    image_columns = {
        "image_url": "VARCHAR(500) NULL",
        "image_path": "VARCHAR(500) NULL",
        "image_aspect_ratio": "VARCHAR(20) NULL",
        "image_style": "VARCHAR(50) NULL",
        "image_resolution": "VARCHAR(20) NULL",
        "generated_at": "DATETIME NULL",
    }

    inspector = inspect(engine)
    existing_columns = {column["name"] for column in inspector.get_columns("creatives")}
    missing_columns = {
        name: definition
        for name, definition in image_columns.items()
        if name not in existing_columns
    }

    if not missing_columns:
        return

    with engine.begin() as connection:
        for name, definition in missing_columns.items():
            connection.execute(text(f"ALTER TABLE creatives ADD COLUMN {name} {definition}"))