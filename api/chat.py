from typing import Optional

from fastapi import APIRouter, Depends
from loguru import logger as LOG

from models.chat import *
from services import conversationService as con
from services.db import get_session

DBSession = Annotated[Session, Depends(get_session)]

chat_router = APIRouter(prefix='/chat', tags=['chat'])

@chat_router.post('/')
def chat(messageBody: CreateMessage):
    
    message_response = Message(**messageBody.model_dump())
    return MessageResponse(**message_response.model_dump())


@chat_router.post('/attach_file')
def attach_file():
    ...


conversational_router = APIRouter(prefix='/conversational')

# Assistants
@conversational_router.get('/assistant', response_model=list[Assistant])
def get_assistants(session: DBSession, name: Optional[str] = None):
    if name:
        return []
    else:
        assistants = con.get_all_assistants(session)
        return assistants


@conversational_router.post('/assistant', response_model=Assistant)
def create_assistant(session: DBSession, assistantBody: CreateAssistant):
    return con.create_assistant(assistantBody, session)

# Threads
@conversational_router.get('/thread', response_model=list[Thread])
def get_threads(session: DBSession, name: Optional[str] = None):
    if name:
        return []
    else:
        return con.get_all_threds(session)


@conversational_router.post('/thread', response_model=Thread)
def create_thread(session: DBSession, threadBody: CreateThread):
    return con.create_thread(threadBody, session)



