from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, UploadFile, File
from loguru import logger as LOG
from openai.types import image

from models.chat import *
from services import conversationService as con
from services.db import get_session
from services.ai import modelService as ai

DBSession = Annotated[Session, Depends(get_session)]

chat_router = APIRouter(prefix='/chat', tags=['chat'])

@chat_router.post('/')
def chat(messageBody: CreateMessage):
    
    message_response = Message(**messageBody.model_dump())
    return MessageResponse(**message_response.model_dump())


@chat_router.post('/attach_file')
def attach_file():
    ...

@chat_router.post('/ask_once')
async def ask_once(
        image: Optional[UploadFile] = File(default=None),
        system_prompt: str = Form(...),
        user_msg: str = Form(...),
):
    if image:
        return await ai.ask_about_image(system_prompt, image.file.read(), user_msg)
    else:
        return await ai.send_once(messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_msg}
        ])

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



