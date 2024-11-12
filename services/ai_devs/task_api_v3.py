import os
from httpx import AsyncClient, HTTPStatusError
from loguru import logger as LOG

from models.ai_devs import AiDevsAnswer, AiDevsResponse

VERIFICATION_URL = os.environ.get('AI_DEVS_TASK_URL','https://poligon.aidevs.pl/verify')

async def send_answer(answer: AiDevsAnswer, url: str = VERIFICATION_URL):
    LOG.info('Sending task answer, {} to {}', answer.model_dump_json(), url)
    async with AsyncClient() as client:
        api_response = await client.post(url=url, json=answer.model_dump())
        try:
            api_response.raise_for_status()
        except HTTPStatusError as err:
            return AiDevsResponse(code=err.response.status_code, message=err.response.json())
        return AiDevsResponse(**api_response.json())
