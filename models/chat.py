from pytz import utc
from typing import Annotated, Literal
from uuid import uuid4, UUID

from sqlmodel import Field, Session, SQLModel, create_engine, select, Relationship
from datetime import datetime
from pydantic import BaseModel

AttachmentType = Literal['image','document','website','audio','video']

# Database models

class ThreadAttachmentLink(SQLModel, table=True):
    attachment_id: UUID | None = Field(default=None, foreign_key='attachment.id', primary_key=True)
    thread_id: UUID | None = Field(default=None, foreign_key='thread.id', primary_key=True)


class AttachmentBase(SQLModel):
    _type: AttachmentType
    url: str | None = Field(default=None)
    data: bytes | None = Field(default=None)


class Attachment(AttachmentBase, table=True):
    id: UUID | None  = Field(default_factory=uuid4, primary_key=True)
    threads: list['Thread'] = Relationship(back_populates='attachments', link_model=ThreadAttachmentLink) 


class AssistantBase(SQLModel):
    name: str = Field(index=True)
    prompt: str | None = Field(default=None)
    avatar: bytes | None = Field(default=None)


class Assistant(AssistantBase, table=True):
    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    threads: list['Thread'] | None = Relationship(back_populates='assistant')

class CreateAssistant(AssistantBase):
    ...


class ThreadBase(SQLModel):
    name: str
    created_at: datetime | None = Field(default_factory=datetime.now)


class Thread(ThreadBase, table=True):
    id: UUID | None  = Field(default_factory=uuid4, primary_key=True)
    assistant_id: UUID = Field(foreign_key='assistant.id')
    assistant: Assistant = Relationship(back_populates='threads')
    attachments: list[Attachment] = Relationship(back_populates='threads', link_model=ThreadAttachmentLink)
    messages: list['Message'] = Relationship(back_populates='thread')


class CreateThread(ThreadBase):
    name: str
    assistant_id: UUID


class MessageBase(SQLModel):
    timestamp: datetime | None = Field(default_factory=datetime.now, index=True)
    content: str


class Message(MessageBase, table=True):
    id: UUID | None  = Field(default_factory=uuid4, primary_key=True)
    thread_id: UUID = Field(foreign_key='thread.id')
    thread: Thread = Relationship(back_populates='messages')

class CreateMessage(MessageBase):
    chat_model: str 


class MessageResponse(MessageBase): 
    id: UUID
    thread: Thread
