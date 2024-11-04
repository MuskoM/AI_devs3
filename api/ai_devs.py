from os import environ

from fastapi import APIRouter
from httpx import AsyncClient
from loguru import logger as LOG

from models import ai_devs
from modules.ai_devs.task_api_v3 import send_answer

router = APIRouter(tags=['ai_devs'], prefix='/ai_devs')
try:
    API_TASK_KEY = environ['AI_DEVS_TASK_KEY']
except KeyError:
    raise EnvironmentError('AI_DEVS_TASK_KEY not found, have you provided a key?')

@router.get('/poligon')
async def poligon_task():
    LOG.info('Executing Poligon Task')
    task_data_url = 'https://poligon.aidevs.pl/dane.txt'
    async with AsyncClient() as client:
        raw_data = await client.get(task_data_url)
        data_array = [t for t in raw_data.text.split('\n') if t]
        LOG.info('Fetched data and put into array {}', data_array)
        task_api_response = await send_answer(
            ai_devs.AiDevsAnswer(task='POLIGON', apikey=API_TASK_KEY, answer=data_array)
        )
        return task_api_response



