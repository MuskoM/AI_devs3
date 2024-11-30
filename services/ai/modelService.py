import base64
import io
from typing import Literal
from langfuse.client import os
from loguru import logger as LOG
from langfuse.openai import AsyncOpenAI

from exceptions import ApiException

async def complete_task(
        system_prompt: str,
        data_prompt: str,
        model: str = 'gpt-4o-mini',
        local_model: str = '',
        **kwargs
) -> str:
    LOG.info('Sending to {}, sys=({}), usr=({})', model, system_prompt, data_prompt)
    client_args = {}
    if local_model:
        client_args['base_url'] = 'http://localhost:11434/v1'
        model = local_model
    async with AsyncOpenAI(**client_args) as ai:
        response = await ai.chat.completions.create( # type: ignore
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': data_prompt}
            ],
            model=model,
            **kwargs
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

async def ask_about_image(
        system_prompt: str,
        image: bytes,
        user_msg: str,
        model: Literal['gpt-4o', 'gpt-4o-mini'] = 'gpt-4o-mini'
):
    img_base64 = base64.b64encode(image).decode()
    async with AsyncOpenAI() as ai:
        response = await ai.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': [ # type: ignore
                    {'type': 'text', 'text': user_msg},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img_base64}'}}
                ]}
            ]
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
            LOG.info('Trying to transcribe the data {}',audio_file[:10])
            response = await ai.audio.transcriptions.create(
                model='whisper-large-v3',
                file=file_buffer
            )
            LOG.info('Transcription endpoint responded with {}', response.model_dump_json())
            return response.model_dump()['text']
        except Exception as err:
            err_msg = 'Error occured when trying to transcribe the audio file {}'
            LOG.error(err_msg, str(err))
            raise ApiException(err_msg.replace('{}', str(err)))

async def generate_image(
        prompt: str,
        model: str = 'dall-e-3',
        response_format: Literal['url','b64_json'] = 'url',
        **opts):
    async with AsyncOpenAI() as ai:
        response = await ai.images.generate(
            model=model,
            prompt=prompt,
            response_format=response_format,
            **opts
        )
        image_response = response.data[0].url if response_format == 'url' else response.data[0].b64_json
        if image_response:
            return image_response
        else:
            raise ApiException()
