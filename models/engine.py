from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from configs import config

engine = create_engine(config.DATABASE_URI,pool_size=config.POOL_SIZE)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency
def get_session()-> Optional[Session]:
    session  = SessionLocal()
    return session

@contextmanager
def get_db() -> Generator[Session, None, None]:
    with get_session() as session:
        try:
            yield session
        finally:
            session.close()