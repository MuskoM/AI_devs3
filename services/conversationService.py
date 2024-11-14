from typing import Sequence
from sqlmodel import select, Session

from models.chat import *

def get_all_assistants(session: Session) -> Sequence[Assistant]:
    return session.exec(
        select(Assistant)
    ).all()

def create_assistant(assistant_data: CreateAssistant, session: Session) -> Assistant:
    new_assistant = Assistant.model_validate(assistant_data)
    session.add(new_assistant)
    session.commit()
    session.refresh(new_assistant)
    return new_assistant

def get_all_threds(session: Session) -> Sequence[Thread]:
    return session.exec(
        select(Thread)
    ).all()

def create_thread(thread_data: CreateThread, session: Session) -> Thread:
    new_thread = Thread.model_validate(thread_data)
    session.add(new_thread)
    session.commit()
    session.refresh(new_thread)
    return new_thread
