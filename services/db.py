from typing import Generator
from langfuse.client import os
from sqlmodel import SQLModel, Session, create_engine

from models.chat import *

DB_URL = os.environ['DB_URL']

class DBError(BaseException):
    ...

engine = create_engine(DB_URL, echo=True)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session() -> Session:
    return Session(engine)
