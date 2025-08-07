from sqlalchemy import inspect
from sqlalchemy.orm import declarative_base

from .engine import engine

inspector = inspect(engine)
Base = declarative_base()