from httpx import AsyncClient, HTTPStatusError
from loguru import logger as LOG

from models.ai_devs import AiDevsAnswer, AiDevsResponse

VERIFICATION_URL = 'https://poligon.aidevs.pl/verify'

async def send_answer(answer: AiDevsAnswer):
    LOG.info('Sending task answer, {}', answer.model_dump_json())
    async with AsyncClient() as client:
        api_response = await client.post(url=VERIFICATION_URL, json=answer.model_dump())
        try:
            api_response.raise_for_status()
        except HTTPStatusError:
            return AiDevsResponse(code=2137, message='Ungodly answer')
        return AiDevsResponse(**api_response.json())
