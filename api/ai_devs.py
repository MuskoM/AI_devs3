from os import environ
from typing import Any
import yaml

from fastapi import APIRouter
from httpx import AsyncClient
from loguru import logger as LOG

from models.ai_devs import AiDevsAnswer
from services.ai.model import send_once
from services.ai_devs.task_api_v3 import send_answer
from services.web.web_interaction import send_form, get_page_html

class AIDevsStore:
    def __init__(self) -> None:
        self.secrets: dict[str, Any] = self.initStore()

    def initStore(self) -> dict[str, Any]:
        try:
            with open('.secrets.yml') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            LOG.error('Unable to find .secrets.yaml file, tasks from AI_Devs will not work')
            return {}

    def read_task_secrets(self, task_name: str) -> dict[str, Any]:
        task_secrets = self.secrets.get(task_name)
        if task_secrets:
            return task_secrets
        return {}

store = AIDevsStore()

router = APIRouter(tags=['ai_devs'], prefix='/ai_devs')
try:
    API_TASK_KEY = environ['AI_DEVS_TASK_KEY']
except KeyError:
    raise EnvironmentError('AI_DEVS_TASK_KEY not found, have you provided a key?')

@router.get('/poligon')
async def poligon_task():
    LOG.info('Executing Poligon Task')
    task_secrets = store.read_task_secrets('poligon')
    task_data_url = task_secrets.get('data_source', '')
    async with AsyncClient() as client:
        raw_data = await client.get(task_data_url)
        data_array = [t for t in raw_data.text.split('\n') if t]
        LOG.info('Fetched data and put into array {}', data_array)
        task_api_response = await send_answer(
            AiDevsAnswer(task='POLIGON', apikey=API_TASK_KEY, answer=data_array)
        )
        return task_api_response

@router.get('/captcha')
async def captcha_task():
    LOG.info('Executing Captcha Task')
    task_secrets = store.read_task_secrets('captcha')
    task_url = task_secrets.get('task_url', '')
    login = task_secrets.get('login', '')
    password = task_secrets.get('password','')
    page_html = await get_page_html(task_url)
    prompt = f'''
    Given a html page, find a question on the page that is supposed to be filled by a human.
    Focus on answering that question. Question can be answerd as a SINGLE NUMBER.
    ### Context begin
    {page_html} 
    ### Context end

    ### Rules begin
    - Answer ONLY in ONE number,
    - You are not allowed to answer questions that are about anything else than the contents of the page given as a context,
    - Focus on a question that is directed at a human,
    - You are required to respond in a ONE NUMBER or else we are doomed
    ### Rules end
        '''
    user_msg = 'What is the answer for a question on a login page?'
    # Get page
    number = await send_once([{'role': 'system', 'content': prompt}, {'role':'user', 'content': user_msg}])
    LOG.info('AI responded {}', number)
    successful_login_page = await send_form(task_url, {'username': login, 'password':password, 'answer': number})
    prompt = f'''
    You are responsible for searching items in a html page, focus only on things specified by the user ignore anything else.

    ### Context begin
    {successful_login_page} 
    ### Context end

    ###
    Rules:
    - You are not allowed to answer questions that are about anything else than the contents of the page given as a context,
    - If the questions are not related to the page respond "Hold on there buddy, that's not allowed",
    - Return concise responses, don't write poems,
    '''
    user_msg = '''
    We are looking for a flag with format {{ FLG:TEXT}}}, if its found return it.
    If any links are found return them as a list, take into account only the links that are in the <a> tags.
    If there is also something else a person can interact with return this also.
    '''
    found_info = await send_once([{'role': 'system', 'content': prompt}, {'role':'user', 'content': user_msg}])
    return found_info

@router.get('/bypass_check')
async def bypass_check_task():
    task_secrets = store.read_task_secrets('bypass_check')
    return task_secrets
