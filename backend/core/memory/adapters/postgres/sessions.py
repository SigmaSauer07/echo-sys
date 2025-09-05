import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def make_engine():
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "alsaniamcp")
    user = os.getenv("POSTGRES_USER", "alsania")
    pwd = os.getenv("POSTGRES_PASSWORD", "alsania")
    url = f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}"
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)

SessionLocal = sessionmaker(bind=make_engine(), autocommit=False, autoflush=False)
