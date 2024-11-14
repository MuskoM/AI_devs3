import io
from langfuse.client import os
from loguru import logger as LOG
from langfuse.openai import AsyncOpenAI

from exceptions import ApiException

async def complete_task(system_prompt: str, data_prompt: str) -> str:
    async with AsyncOpenAI() as ai:
        response = await ai.chat.completions.create( # type: ignore
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': data_prompt}
            ]
        )
        return str(response.choices[0].message.content)

async def complete_task_local(system_prompt: str, data_prompt: str) -> str:
    async with AsyncOpenAI() as ai:
        response = await ai.chat.completions.create( # type: ignore
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': data_prompt}
            ]
        )
        return str(response.choices[0].message.content)

async def send_once(messages: list, model = 'gpt-4o-mini', **kwargs) -> str:
    async with AsyncOpenAI() as ai:
        response = await ai.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
        )
        return str(response.choices[0].message.content)

async def transcribe(audio_file: bytes):
    file_buffer = io.BytesIO(audio_file)
    file_buffer.name = 'audio.m4a'
    async with AsyncOpenAI(
        base_url='https://api.groq.com/openai/v1',
        api_key=os.environ['GROQ_API_KEY']
    ) as ai:
        try:
            response = await ai.audio.transcriptions.create(
                model='whisper-large-v3',
                file=file_buffer
            )
            return response.model_dump()['text']
        except Exception as err:
            err_msg = 'Error occured when trying to transcribe the audio file {}'
            LOG.error(err_msg, str(err))
            raise ApiException(err_msg.replace('{}', str(err)))
